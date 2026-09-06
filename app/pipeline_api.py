
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import date
from sqlalchemy import select
from .data_model import SessionLocal, Evidence, Transaction
from .personal_service import ensure_demo_household
from .ingestion_pipeline import match_unlinked_evidence, detect_anomalies

router=APIRouter(prefix="/api/v08",tags=["LedgerMind v0.8 pipeline"])

class EvidenceIn(BaseModel):
    provider:str="manual"
    evidence_type:str="receipt"
    merchant:str|None=None
    amount:float|None=None
    evidence_date:date|None=None
    subject:str|None=None
    excerpt:str|None=None

@router.post("/evidence")
def add_evidence(payload:EvidenceIn):
    hh=ensure_demo_household()
    with SessionLocal() as s:
        ev=Evidence(household_id=hh,**payload.model_dump())
        s.add(ev);s.commit();s.refresh(ev)
        return {"id":ev.id}

@router.post("/evidence/match")
def match_evidence():
    hh=ensure_demo_household()
    return {"matches":match_unlinked_evidence(hh)}

@router.post("/insights/anomalies")
def anomalies():
    hh=ensure_demo_household()
    return detect_anomalies(hh)

@router.get("/evidence")
def evidence():
    hh=ensure_demo_household()
    with SessionLocal() as s:
        rows=s.scalars(select(Evidence).where(Evidence.household_id==hh).order_by(Evidence.id.desc())).all()
        return [{
            "id":e.id,"transaction_id":e.transaction_id,"provider":e.provider,
            "type":e.evidence_type,"merchant":e.merchant,"amount":e.amount,
            "date":e.evidence_date.isoformat() if e.evidence_date else None,
            "subject":e.subject,"match_score":e.match_score
        } for e in rows]
