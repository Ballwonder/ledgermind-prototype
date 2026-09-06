
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from .personal_service import ensure_demo_household
from .data_model import SessionLocal, AccountingPrecedent, FinancialProfile
from .accounting_precedent_engine import learn_precedent, precedent_decision

router=APIRouter(prefix="/api/v014/accounting-precedent",tags=["LedgerMind v0.14 accounting precedent"])

class Facts(BaseModel):
    item_type:str|None=None
    business_use_pct:float|None=None
    personal_component_present:bool|None=None
    lasting_benefit:bool|None=None
    restores_original_condition:bool|None=None
    improves_beyond_original_condition:bool|None=None

class LearnIn(Facts):
    final_treatment:str
    rationale:str=""
    authority_level:str="reviewer_precedent"
    account_or_category:str|None=None

@router.post("/transactions/{transaction_id}/match")
def match(transaction_id:int,payload:Facts):
    hh=ensure_demo_household()
    try:
        return precedent_decision(hh,transaction_id,payload.model_dump())
    except KeyError:
        raise HTTPException(404,"Transaction not found")

@router.post("/transactions/{transaction_id}/learn")
def learn(transaction_id:int,payload:LearnIn):
    hh=ensure_demo_household()
    try:
        p=learn_precedent(
            hh,transaction_id,payload.final_treatment,payload.model_dump(),
            payload.rationale,payload.authority_level,payload.account_or_category
        )
        return {"precedent_id":p.id,"treatment":p.treatment,"confidence":p.confidence}
    except KeyError:
        raise HTTPException(404,"Transaction not found")
    except ValueError:
        raise HTTPException(409,"Transaction must have a financial profile first")

@router.get("")
def list_all():
    hh=ensure_demo_household()
    with SessionLocal() as s:
        profiles={p.id:p.name for p in s.scalars(select(FinancialProfile).where(FinancialProfile.household_id==hh)).all()}
        rows=s.scalars(select(AccountingPrecedent).where(AccountingPrecedent.household_id==hh).order_by(AccountingPrecedent.id.desc())).all()
        return {"precedents":[{
            "id":p.id,"profile_name":profiles.get(p.profile_id),"treatment":p.treatment,
            "item_type":p.item_type,"merchant":p.merchant_normalized,
            "authority_level":p.authority_level,"confidence":p.confidence,
            "rationale":p.rationale
        } for p in rows]}
