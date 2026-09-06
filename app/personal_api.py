
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from .data_model import create_schema
from .personal_service import ensure_demo_household, dashboard, list_transactions, correct_category, wealth

router=APIRouter(prefix="/api/v07",tags=["LedgerMind Personal v0.7"])

class CategoryCorrection(BaseModel):
    category:str
    note:str|None=None

def init_v07():
    create_schema()
    return ensure_demo_household()

@router.get("/dashboard")
def get_dashboard():
    hh=ensure_demo_household()
    return dashboard(hh)

@router.get("/transactions")
def get_transactions():
    hh=ensure_demo_household()
    return list_transactions(hh)

@router.post("/transactions/{transaction_id}/category")
def set_category(transaction_id:int,payload:CategoryCorrection):
    hh=ensure_demo_household()
    try:
        return correct_category(hh,transaction_id,payload.category,payload.note)
    except KeyError:
        raise HTTPException(404,"Transaction not found")

@router.get("/wealth")
def get_wealth():
    hh=ensure_demo_household()
    return wealth(hh)
