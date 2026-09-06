
from fastapi import APIRouter,HTTPException
from dataclasses import asdict
from .personal_service import ensure_demo_household
from .data_model import SessionLocal,Transaction
from .journal_gated_autonomy import decide_with_journal

router=APIRouter(prefix="/api/v028/autonomy",tags=["LedgerMind v0.28 journal-gated autonomy"])

@router.post("/transactions/{transaction_id}")
def evaluate(transaction_id:int,facts:dict={}):
    hh=ensure_demo_household()
    with SessionLocal() as s:
        tx=s.get(Transaction,transaction_id)
        if not tx or tx.household_id!=hh: raise HTTPException(404,"Transaction not found")
    return asdict(decide_with_journal(hh,tx,facts))
