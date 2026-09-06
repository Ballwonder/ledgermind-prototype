
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from .personal_service import ensure_demo_household
from .data_model import SessionLocal, Transaction, FinancialProfile
from .streamlining_engine import create_source_map, create_recurring_rule, source_profile_candidates, recurring_match
from .autonomy_router import decide_autonomy, as_payload

router=APIRouter(prefix="/api/v016",tags=["LedgerMind v0.16 streamlining"])

class SourceMapIn(BaseModel):
    profile_id:int
    source_type:str
    source_value:str
    folder_or_label:str|None=None
    trust_level:str="strong"

class SourceResolveIn(BaseModel):
    source_type:str
    source_value:str
    folder_or_label:str|None=None

class RecurringIn(BaseModel):
    profile_id:int
    merchant:str
    category:str|None=None
    treatment:str|None=None
    business_use_pct:float|None=None
    expected_amount:float|None=None
    amount_tolerance_pct:float=.20
    descriptor_contains:str|None=None
    cadence:str|None=None

@router.post("/source-maps")
def add_source(payload:SourceMapIn):
    hh=ensure_demo_household()
    row=create_source_map(hh,**payload.model_dump())
    return {"id":row.id,"confidence":row.confidence}

@router.post("/source-maps/resolve")
def resolve_source(payload:SourceResolveIn):
    hh=ensure_demo_household()
    return {"candidates":source_profile_candidates(hh,**payload.model_dump())}

@router.post("/recurring-rules")
def add_recurring(payload:RecurringIn):
    hh=ensure_demo_household()
    row=create_recurring_rule(hh,**payload.model_dump())
    return {"id":row.id,"confidence":row.confidence}

@router.get("/recurring-rules/match/{transaction_id}")
def match_recurring(transaction_id:int):
    hh=ensure_demo_household()
    with SessionLocal() as s:
        tx=s.get(Transaction,transaction_id)
        if not tx or tx.household_id!=hh: raise HTTPException(404,"Transaction not found")
        return {"matches":recurring_match(hh,tx)}

@router.get("/exception-queue")
def exception_queue():
    hh=ensure_demo_household()
    rows=[]
    with SessionLocal() as s:
        txs=s.scalars(select(Transaction).where(Transaction.household_id==hh).order_by(Transaction.tx_date.desc())).all()
        for tx in txs:
            d=decide_autonomy(hh,tx.id,{})
            if d.route!="AUTO_FINISH":
                rows.append({
                    "transaction_id":tx.id,"date":str(tx.tx_date),
                    "merchant":tx.merchant_normalized or tx.merchant_raw,
                    "amount":tx.amount,"route":d.route,
                    "weakest_material_factor":d.weakest_material_factor,
                    "question":d.owner_question,
                    "review_reason":d.professional_review_reason
                })
    priority={"PROFESSIONAL_REVIEW":0,"OWNER_QUESTION":1}
    rows.sort(key=lambda x:(priority.get(x["route"],9),x["date"]))
    return {"count":len(rows),"exceptions":rows}
