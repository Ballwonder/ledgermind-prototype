
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel
from datetime import date
from dataclasses import asdict
from .personal_service import ensure_demo_household
from .reconciliation_v029 import create_statement,reconcile_statement,reconciliation_history

router=APIRouter(prefix="/api/v029/reconciliation",tags=["LedgerMind v0.29 reconciliation"])

class StatementIn(BaseModel):
    account_name:str
    period_start:date
    period_end:date
    opening_balance:float
    closing_balance:float
    currency:str="CAD"

@router.post("/statements")
def statement(x:StatementIn):
    return {"statement_id":create_statement(ensure_demo_household(),**x.model_dump())}

@router.post("/statements/{statement_id}/run")
def run(statement_id:int):
    try:return asdict(reconcile_statement(ensure_demo_household(),statement_id))
    except KeyError:raise HTTPException(404,"Statement not found")

@router.get("/statements/{statement_id}/records")
def records(statement_id:int):
    return {"records":reconciliation_history(ensure_demo_household(),statement_id)}
