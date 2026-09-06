
from fastapi import APIRouter,HTTPException
from .personal_service import ensure_demo_household
from .reconciliation_actions_v031 import propose_actions,apply_safe_actions

router=APIRouter(prefix="/api/v031/reconciliation-actions",tags=["LedgerMind v0.31 reconciliation actions"])

@router.post("/statements/{statement_id}/propose")
def propose(statement_id:int):
    try:return {"actions":propose_actions(ensure_demo_household(),statement_id)}
    except KeyError:raise HTTPException(404,"Statement not found")

@router.post("/statements/{statement_id}/apply-safe")
def apply(statement_id:int):
    try:return apply_safe_actions(ensure_demo_household(),statement_id)
    except KeyError:raise HTTPException(404,"Statement not found")
