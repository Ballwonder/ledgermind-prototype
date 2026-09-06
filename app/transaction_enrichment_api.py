
from fastapi import APIRouter,HTTPException
from .personal_service import ensure_demo_household
from .transaction_enrichment import enrich_transaction,enrich_household
from dataclasses import asdict

router=APIRouter(prefix="/api/v018/enrichment",tags=["LedgerMind v0.18 enrichment"])

@router.post("/transactions/{transaction_id}")
def enrich_one(transaction_id:int,persist:bool=True):
    hh=ensure_demo_household()
    try: return asdict(enrich_transaction(hh,transaction_id,persist=persist))
    except KeyError: raise HTTPException(404,"Transaction not found")

@router.post("/run")
def enrich_all(persist:bool=True):
    hh=ensure_demo_household()
    return enrich_household(hh,persist=persist)
