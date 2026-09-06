
from datetime import datetime
from sqlalchemy import select
from .data_model import SessionLocal,BankStatement,StatementMatch,Transaction,OutstandingItem
from .reconciliation_actions_v031 import propose_actions

def sync_outstanding_items(hh:int,statement_id:int):
    proposals=propose_actions(hh,statement_id,persist=True)
    with SessionLocal() as s:
        st=s.get(BankStatement,statement_id)
        if not st or st.household_id!=hh: raise KeyError("statement")
        created=[];updated=[]
        for p in proposals:
            if p["action_type"]!="MARK_OUTSTANDING" or p["confidence"]<0.90: continue
            txid=p["transaction_id"]
            row=s.scalar(select(OutstandingItem).where(
                OutstandingItem.household_id==hh,
                OutstandingItem.transaction_id==txid,
                OutstandingItem.status=="OUTSTANDING"))
            if row:
                row.last_checked_period_end=st.period_end
                row.updated_at=datetime.utcnow()
                updated.append(row.id)
            else:
                row=OutstandingItem(
                    household_id=hh,statement_id=statement_id,transaction_id=txid,
                    classification=p["payload"]["classification"],status="OUTSTANDING",
                    confidence=p["confidence"],first_period_end=st.period_end,
                    last_checked_period_end=st.period_end,reason=p["reason"])
                s.add(row);s.flush();created.append(row.id)
        s.commit()
    return {"created":created,"updated":updated}

def carry_forward_and_clear(hh:int,new_statement_id:int):
    with SessionLocal() as s:
        st=s.get(BankStatement,new_statement_id)
        if not st or st.household_id!=hh: raise KeyError("statement")
        open_items=s.scalars(select(OutstandingItem).where(
            OutstandingItem.household_id==hh,
            OutstandingItem.status=="OUTSTANDING")).all()
        matches=s.scalars(select(StatementMatch).where(
            StatementMatch.household_id==hh,
            StatementMatch.statement_id==new_statement_id,
            StatementMatch.status=="MATCHED")).all()
        matched_tx={m.transaction_id for m in matches if m.transaction_id}
        cleared=[];carried=[];stale=[]
        for item in open_items:
            if item.transaction_id in matched_tx:
                item.status="CLEARED"
                item.cleared_statement_id=new_statement_id
                item.last_checked_period_end=st.period_end
                item.updated_at=datetime.utcnow()
                cleared.append(item.id)
            else:
                item.last_checked_period_end=st.period_end
                item.updated_at=datetime.utcnow()
                age=(st.period_end-item.first_period_end).days
                if age>90:
                    item.status="STALE_REVIEW"
                    stale.append(item.id)
                else:
                    carried.append(item.id)
        s.commit()
    return {"cleared":cleared,"carried_forward":carried,"stale_review":stale}

def close_readiness_v032(hh:int,statement_id:int):
    with SessionLocal() as s:
        st=s.get(BankStatement,statement_id)
        if not st or st.household_id!=hh: raise KeyError("statement")
        matches=s.scalars(select(StatementMatch).where(
            StatementMatch.household_id==hh,
            StatementMatch.statement_id==statement_id)).all()
        outstanding=s.scalars(select(OutstandingItem).where(
            OutstandingItem.household_id==hh,
            OutstandingItem.status=="OUTSTANDING")).all()
        acceptable_tx={x.transaction_id for x in outstanding}
        blocking=[]
        accepted=[]
        for m in matches:
            if m.status=="MATCHED": continue
            if m.status=="BOOK_ONLY" and m.transaction_id in acceptable_tx:
                accepted.append({"transaction_id":m.transaction_id,"status":"ACCEPTABLE_OUTSTANDING"})
            else:
                blocking.append({"statement_line_id":m.statement_line_id,"transaction_id":m.transaction_id,"status":m.status})
        stale=s.scalars(select(OutstandingItem).where(
            OutstandingItem.household_id==hh,
            OutstandingItem.status=="STALE_REVIEW")).all()
        for x in stale:
            blocking.append({"transaction_id":x.transaction_id,"status":"STALE_OUTSTANDING_REVIEW"})
        return {
            "close_ready":len(blocking)==0,
            "accepted_timing_differences":accepted,
            "blocking_items":blocking,
            "open_outstanding_count":len(outstanding),
            "reason":None if not blocking else "Unresolved reconciliation items remain."
        }
