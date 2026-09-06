
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from .data_model import SessionLocal, Transaction, FinancialProfile
from .personal_service import ensure_demo_household
from .accounting_decision_engine import evaluate_transaction, as_payload
from .accounting_precedent_engine import precedent_decision

router=APIRouter(prefix="/api/v011/accounting",tags=["LedgerMind v0.11 profile-aware accounting"])

class FactsIn(BaseModel):
    item_type:str|None=None
    business_use_pct:float|None=None
    personal_component_present:bool=False
    lasting_benefit:bool=False
    restores_original_condition:bool=False
    improves_beyond_original_condition:bool=False

@router.post("/transactions/{transaction_id}/evaluate")
def evaluate(transaction_id:int,facts:FactsIn):
    hh=ensure_demo_household()
    with SessionLocal() as s:
        tx=s.get(Transaction,transaction_id)
        if not tx or tx.household_id!=hh: raise HTTPException(404,"Transaction not found")
        if not tx.profile_id: raise HTTPException(409,"Assign a financial profile first")
        p=s.get(FinancialProfile,tx.profile_id)
        profile={
            "profile_type":p.profile_type,"tax_regime":p.tax_regime,
            "gst_hst_registered":p.gst_hst_registered,"province":p.province
        }
        txp={"amount":tx.amount,"category":tx.category,"merchant":tx.merchant_normalized or tx.merchant_raw}
        fact_payload=facts.model_dump()
        precedent=precedent_decision(hh,transaction_id,fact_payload)
        result=as_payload(evaluate_transaction(profile,txp,fact_payload))
        result["precedent"]=precedent
        # Precedent can inform treatment only when strong, but review-sensitive fields still survive.
        if precedent["action"]=="apply_precedent":
            result["precedent_recommended_treatment"]=precedent["match"]["treatment"]
            result["precedent_account_or_category"]=precedent["match"]["account_or_category"]
        return result
