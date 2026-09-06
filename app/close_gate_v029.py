
from sqlalchemy import select
from .data_model import SessionLocal,BankStatement
from .reconciliation_v029 import reconcile_statement

def close_readiness_from_reconciliation(hh:int):
    with SessionLocal() as s:
        ids=s.scalars(select(BankStatement.id).where(BankStatement.household_id==hh)).all()
    if not ids:
        return {"close_ready":False,"reason":"No bank statements have been reconciled.","statements":[]}
    rows=[reconcile_statement(hh,i,persist=False) for i in ids]
    blocking=[r for r in rows if r.close_blocking]
    return {
        "close_ready":len(blocking)==0,
        "reason":None if not blocking else "One or more statements do not reconcile.",
        "statements":[{"statement_id":r.statement_id,"ties":r.ties,"difference":r.difference,
                       "duplicate_count":r.duplicate_count,"close_blocking":r.close_blocking} for r in rows]
    }
