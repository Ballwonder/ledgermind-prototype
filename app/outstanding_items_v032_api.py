
from fastapi import APIRouter,HTTPException
from .personal_service import ensure_demo_household
from .outstanding_items_v032 import sync_outstanding_items,carry_forward_and_clear,close_readiness_v032

router=APIRouter(prefix="/api/v032/outstanding",tags=["LedgerMind v0.32 outstanding items"])
@router.post("/statements/{statement_id}/sync")
def sync(statement_id:int):
    try:return sync_outstanding_items(ensure_demo_household(),statement_id)
    except KeyError:raise HTTPException(404,"Statement not found")
@router.post("/statements/{statement_id}/carry-forward")
def carry(statement_id:int):
    try:return carry_forward_and_clear(ensure_demo_household(),statement_id)
    except KeyError:raise HTTPException(404,"Statement not found")
@router.get("/statements/{statement_id}/close-readiness")
def close(statement_id:int):
    try:return close_readiness_v032(ensure_demo_household(),statement_id)
    except KeyError:raise HTTPException(404,"Statement not found")
