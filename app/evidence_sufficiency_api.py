
from fastapi import APIRouter,HTTPException
from .personal_service import ensure_demo_household
from .evidence_sufficiency import evaluate_evidence,payload

router=APIRouter(prefix="/api/v020/evidence",tags=["LedgerMind v0.20 evidence"])

@router.get("/transactions/{transaction_id}")
def evaluate(transaction_id:int):
    try: return payload(evaluate_evidence(ensure_demo_household(),transaction_id))
    except KeyError: raise HTTPException(404,"Transaction not found")
