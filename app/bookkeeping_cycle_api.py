
from fastapi import APIRouter
from sqlalchemy import select
from .personal_service import ensure_demo_household
from .bookkeeping_cycle import process_household,close_readiness,exception_rows
from .data_model import SessionLocal,ProcessingRun,TransactionProcessingResult,Transaction

router=APIRouter(prefix="/api/v017/cycle",tags=["LedgerMind v0.17 bookkeeping cycle"])

@router.post("/run")
def run_cycle(reset_results:bool=False):
    hh=ensure_demo_household()
    return process_household(hh,reset_results=reset_results)

@router.get("/close-readiness")
def readiness():
    hh=ensure_demo_household()
    return close_readiness(hh)

@router.get("/exceptions")
def exceptions():
    hh=ensure_demo_household()
    return {"exceptions":exception_rows(hh)}

@router.get("/results")
def results():
    hh=ensure_demo_household()
    with SessionLocal() as s:
        run=s.scalar(select(ProcessingRun).where(ProcessingRun.household_id==hh).order_by(ProcessingRun.id.desc()))
        if not run: return {"results":[]}
        rows=s.scalars(select(TransactionProcessingResult).where(TransactionProcessingResult.run_id==run.id)).all()
        out=[]
        for r in rows:
            tx=s.get(Transaction,r.transaction_id)
            out.append({
                "transaction_id":r.transaction_id,
                "merchant":tx.merchant_normalized or tx.merchant_raw if tx else None,
                "amount":tx.amount if tx else None,
                "route":r.route,
                "treatment":r.treatment,
                "journal_balanced":r.journal_balanced,
                "reconciled":r.reconciled
            })
        return {"run_id":run.id,"results":out}
