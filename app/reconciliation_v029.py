
from __future__ import annotations
from dataclasses import dataclass,asdict
from datetime import date
from sqlalchemy import select,and_,or_
from .data_model import SessionLocal,Transaction,BankStatement,ReconciliationRecord

@dataclass
class ReconciliationResult:
    statement_id:int
    account_name:str
    opening_balance:float
    closing_balance:float
    transaction_total:float
    calculated_closing_balance:float
    difference:float
    ties:bool
    cleared_count:int
    unmatched_count:int
    duplicate_count:int
    transfer_pair_count:int
    outstanding_transaction_ids:list[int]
    duplicate_groups:list[list[int]]
    transfer_pairs:list[list[int]]
    close_blocking:bool
    reasons:list[str]

def create_statement(hh:int,account_name:str,period_start:date,period_end:date,opening_balance:float,closing_balance:float,currency="CAD"):
    with SessionLocal() as s:
        st=BankStatement(household_id=hh,account_name=account_name,period_start=period_start,period_end=period_end,
                         opening_balance=float(opening_balance),closing_balance=float(closing_balance),currency=currency)
        s.add(st);s.commit();s.refresh(st);return st.id

def _txs_for_statement(s,hh,st):
    return s.scalars(select(Transaction).where(
        Transaction.household_id==hh,
        Transaction.tx_date>=st.period_start,
        Transaction.tx_date<=st.period_end
    )).all()

def _duplicates(txs):
    groups={}
    for t in txs:
        key=(str(t.tx_date),round(float(t.amount),2),(t.merchant_normalized or t.merchant_raw or "").strip().lower())
        groups.setdefault(key,[]).append(t.id)
    return [ids for ids in groups.values() if len(ids)>1]

def _transfer_pairs(txs):
    used=set();pairs=[]
    for i,a in enumerate(txs):
        if a.id in used: continue
        adesc=(a.description or "").lower()
        for b in txs[i+1:]:
            if b.id in used: continue
            bdesc=(b.description or "").lower()
            if round(float(a.amount)+float(b.amount),2)==0 and abs((a.tx_date-b.tx_date).days)<=3:
                if "transfer" in adesc or "transfer" in bdesc:
                    pairs.append([a.id,b.id]);used.add(a.id);used.add(b.id);break
    return pairs

def reconcile_statement(hh:int,statement_id:int,persist=True):
    with SessionLocal() as s:
        st=s.get(BankStatement,statement_id)
        if not st or st.household_id!=hh: raise KeyError("statement")
        txs=_txs_for_statement(s,hh,st)

    dup_groups=_duplicates(txs)
    dup_ids={x for g in dup_groups for x in g[1:]}  # first occurrence retained, repeats suspicious
    pairs=_transfer_pairs(txs)
    paired_ids={x for p in pairs for x in p}

    # Current prototype treats imported transactions in-period as cleared candidates unless duplicate-suspect.
    cleared=[t for t in txs if t.id not in dup_ids]
    total=round(sum(float(t.amount) for t in cleared),2)
    calc=round(float(st.opening_balance)+total,2)
    diff=round(float(st.closing_balance)-calc,2)
    ties=abs(diff)<0.01

    outstanding=[]
    reasons=[]
    if dup_groups:
        reasons.append(f"{len(dup_groups)} duplicate transaction group(s) require resolution.")
    if not ties:
        reasons.append(f"Statement does not tie; difference is {diff:.2f}.")
        # all non-duplicate tx remain visible, but difference itself represents unresolved reconciliation.
    close_blocking=(not ties) or bool(dup_groups)

    if persist:
        with SessionLocal() as s:
            s.query(ReconciliationRecord).filter(ReconciliationRecord.statement_id==statement_id).delete()
            for t in txs:
                status="DUPLICATE_SUSPECT" if t.id in dup_ids else ("TRANSFER_PAIRED" if t.id in paired_ids else "CLEARED")
                reason=None
                match=None
                if status=="TRANSFER_PAIRED":
                    pair=next(p for p in pairs if t.id in p);match=pair[1] if pair[0]==t.id else pair[0]
                if status=="DUPLICATE_SUSPECT": reason="Same date/amount/merchant as another transaction."
                s.add(ReconciliationRecord(household_id=hh,statement_id=statement_id,transaction_id=t.id,status=status,
                                           matched_transaction_id=match,reason=reason))
            s.commit()

    return ReconciliationResult(
        statement_id=statement_id,account_name=st.account_name,
        opening_balance=float(st.opening_balance),closing_balance=float(st.closing_balance),
        transaction_total=total,calculated_closing_balance=calc,difference=diff,ties=ties,
        cleared_count=len(cleared),unmatched_count=0 if ties else 1,
        duplicate_count=len(dup_ids),transfer_pair_count=len(pairs),
        outstanding_transaction_ids=outstanding,duplicate_groups=dup_groups,transfer_pairs=pairs,
        close_blocking=close_blocking,reasons=reasons
    )

def reconciliation_history(hh:int,statement_id:int):
    with SessionLocal() as s:
        rows=s.scalars(select(ReconciliationRecord).where(
            ReconciliationRecord.household_id==hh,
            ReconciliationRecord.statement_id==statement_id
        ).order_by(ReconciliationRecord.id)).all()
        return [{"transaction_id":r.transaction_id,"status":r.status,
                 "matched_transaction_id":r.matched_transaction_id,"reason":r.reason} for r in rows]
