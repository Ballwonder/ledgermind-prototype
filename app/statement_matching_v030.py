
from dataclasses import dataclass
from datetime import date
from sqlalchemy import select
from .data_model import SessionLocal,BankStatement,StatementLine,StatementMatch,Transaction

@dataclass
class MatchResult:
    statement_id:int
    matched_count:int
    bank_only_count:int
    book_only_count:int
    ambiguous_count:int
    duplicate_statement_line_count:int
    statement_total:float
    book_total:float
    difference:float
    close_blocking:bool
    reasons:list[str]
    matches:list[dict]

def ingest_statement_lines(hh,statement_id,lines):
    with SessionLocal() as s:
        st=s.get(BankStatement,statement_id)
        if not st or st.household_id!=hh: raise KeyError("statement")
        ids=[]
        for x in lines:
            ext=x.get("external_id")
            existing=s.scalar(select(StatementLine).where(
                StatementLine.statement_id==statement_id,
                StatementLine.external_id==ext
            )) if ext else None
            if existing:
                ids.append(existing.id); continue
            row=StatementLine(statement_id=statement_id,household_id=hh,external_id=ext,
                line_date=date.fromisoformat(str(x["date"])[:10]),
                description=x.get("description") or "Statement line",
                amount=float(x["amount"]),
                balance=float(x["balance"]) if x.get("balance") is not None else None)
            s.add(row); s.flush(); ids.append(row.id)
        s.commit()
        return ids

def _norm(v): return " ".join((v or "").lower().split())

def _score(line,tx):
    score=0.0
    if round(float(line.amount),2)==round(float(tx.amount),2): score+=0.62
    days=abs((line.line_date-tx.tx_date).days)
    if days==0: score+=0.20
    elif days<=2: score+=0.12
    elif days<=5: score+=0.05
    lt=set(_norm(line.description).split())
    tt=set(_norm((tx.merchant_normalized or tx.merchant_raw or "")+" "+(tx.description or "")).split())
    if lt and tt:
        score+=min(.18,(len(lt & tt)/max(1,len(lt)))*.18)
    return round(min(score,1.0),3)

def _duplicate_ids(lines):
    groups={}
    for l in lines:
        key=(str(l.line_date),round(float(l.amount),2),_norm(l.description))
        groups.setdefault(key,[]).append(l.id)
    groups=[ids for ids in groups.values() if len(ids)>1]
    return groups,{x for g in groups for x in g[1:]}

def match_statement(hh,statement_id,persist=True):
    with SessionLocal() as s:
        st=s.get(BankStatement,statement_id)
        if not st or st.household_id!=hh: raise KeyError("statement")
        lines=s.scalars(select(StatementLine).where(StatementLine.statement_id==statement_id).order_by(StatementLine.id)).all()
        in_period=s.scalars(select(Transaction).where(
            Transaction.household_id==hh,
            Transaction.tx_date>=st.period_start,
            Transaction.tx_date<=st.period_end
        ).order_by(Transaction.id)).all()
        try:
            from .data_model import OutstandingItem
            prior_ids=[x.transaction_id for x in s.scalars(select(OutstandingItem).where(
                OutstandingItem.household_id==hh,
                OutstandingItem.status=="OUTSTANDING"
            )).all()]
            prior=s.scalars(select(Transaction).where(Transaction.id.in_(prior_ids))).all() if prior_ids else []
        except Exception:
            prior=[]
        seen=set()
        txs=[]
        for tx in list(in_period)+list(prior):
            if tx.id not in seen:
                txs.append(tx); seen.add(tx.id)

    dup_groups,dup_ids=_duplicate_ids(lines)
    assigned=set()
    rows=[]
    for line in lines:
        if line.id in dup_ids:
            rows.append({"statement_line_id":line.id,"transaction_id":None,"status":"DUPLICATE_STATEMENT_LINE","score":0.0,
                         "reason":"Duplicate statement line."})
            continue
        candidates=sorted([(tx,_score(line,tx)) for tx in txs if tx.id not in assigned], key=lambda x:x[1], reverse=True)
        top=candidates[0] if candidates else None
        second=candidates[1] if len(candidates)>1 else None
        if top and top[1]>=0.82 and (second is None or top[1]-second[1]>=0.10):
            assigned.add(top[0].id)
            rows.append({"statement_line_id":line.id,"transaction_id":top[0].id,"status":"MATCHED","score":top[1],
                         "reason":"High-confidence bank-to-book match."})
        elif top and top[1]>=0.65:
            rows.append({"statement_line_id":line.id,"transaction_id":top[0].id,"status":"AMBIGUOUS","score":top[1],
                         "reason":"Candidate exists but confidence or margin is insufficient."})
        else:
            rows.append({"statement_line_id":line.id,"transaction_id":None,"status":"BANK_ONLY","score":top[1] if top else 0.0,
                         "reason":"Statement line has no reliable ledger match."})

    for tx in txs:
        if tx.id not in assigned and not any(r["transaction_id"]==tx.id and r["status"]=="AMBIGUOUS" for r in rows):
            rows.append({"statement_line_id":None,"transaction_id":tx.id,"status":"BOOK_ONLY","score":0.0,
                         "reason":"Ledger transaction is not present on the statement."})

    statement_total=round(sum(float(l.amount) for l in lines if l.id not in dup_ids),2)
    book_total=round(sum(float(t.amount) for t in txs),2)
    diff=round(statement_total-book_total,2)
    blockers={"BANK_ONLY","BOOK_ONLY","AMBIGUOUS","DUPLICATE_STATEMENT_LINE"}
    reasons=[]
    if any(r["status"]=="BANK_ONLY" for r in rows): reasons.append("Statement line missing from ledger.")
    if any(r["status"]=="BOOK_ONLY" for r in rows): reasons.append("Ledger transaction not present on statement.")
    if any(r["status"]=="AMBIGUOUS" for r in rows): reasons.append("Ambiguous statement-to-ledger match.")
    if dup_groups: reasons.append("Duplicate statement lines require resolution.")
    if abs(diff)>=0.01: reasons.append(f"Statement-line total differs from book total by {diff:.2f}.")

    if persist:
        with SessionLocal() as s:
            s.query(StatementMatch).filter(StatementMatch.statement_id==statement_id).delete()
            for r in rows:
                s.add(StatementMatch(household_id=hh,statement_id=statement_id,
                    statement_line_id=r["statement_line_id"],transaction_id=r["transaction_id"],
                    status=r["status"],score=r["score"],reason=r["reason"]))
            s.commit()

    return MatchResult(statement_id,
        sum(r["status"]=="MATCHED" for r in rows),
        sum(r["status"]=="BANK_ONLY" for r in rows),
        sum(r["status"]=="BOOK_ONLY" for r in rows),
        sum(r["status"]=="AMBIGUOUS" for r in rows),
        sum(r["status"]=="DUPLICATE_STATEMENT_LINE" for r in rows),
        statement_total,book_total,diff,
        any(r["status"] in blockers for r in rows) or abs(diff)>=0.01,
        reasons,rows)
