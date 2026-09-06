
from fastapi import APIRouter
from sqlalchemy import select
from .personal_service import ensure_demo_household
from .data_model import SessionLocal, ContextProfileMemory, FinancialProfile

router=APIRouter(prefix="/api/v013/context-memory",tags=["LedgerMind v0.13 contextual learning"])

@router.get("")
def memories():
    hh=ensure_demo_household()
    with SessionLocal() as s:
        profiles={p.id:p.name for p in s.scalars(select(FinancialProfile).where(FinancialProfile.household_id==hh)).all()}
        rows=s.scalars(select(ContextProfileMemory).where(
            ContextProfileMemory.household_id==hh,
            ContextProfileMemory.active==True
        ).order_by(ContextProfileMemory.id.desc())).all()
        return {"memories":[{
            "id":m.id,"profile_id":m.profile_id,"profile_name":profiles.get(m.profile_id),
            "merchant":m.merchant_normalized,"descriptor_signature":m.descriptor_signature,
            "account_id":m.account_id,"min_amount":m.min_amount,"max_amount":m.max_amount,
            "evidence_keywords":m.evidence_keywords,"confidence":m.confidence,
            "times_confirmed":m.times_confirmed,"source":m.source
        } for m in rows]}
