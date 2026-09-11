
from fastapi import APIRouter
from datetime import date
from sqlalchemy import select, delete
from .data_model import (
    SessionLocal, Base, engine, Household, Account, Transaction, Evidence,
    MerchantMemory, ProfileAssignmentRule, Correction, Insight, RecurringObligation, Goal, AuditEvent
)
from .personal_service import ensure_demo_household, dashboard, list_transactions, wealth
from .ingestion_pipeline import match_unlinked_evidence, detect_anomalies

router=APIRouter(prefix="/api/v09",tags=["LedgerMind v0.9 sandbox"])

@router.post("/reset")
def reset_sandbox():
    # Sandbox-only destructive reset.
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    hh=ensure_demo_household()
    return {
        "reset": True,
        "household_id": hh,
        "dashboard": dashboard(hh),
        "transactions": list_transactions(hh),
        "wealth": wealth(hh),
    }

@router.get("/state")
def state():
    hh=ensure_demo_household()
    with SessionLocal() as s:
        evidence_count=len(s.scalars(select(Evidence).where(Evidence.household_id==hh)).all())
        correction_count=len(s.scalars(select(Correction).where(Correction.household_id==hh)).all())
        insight_count=len(s.scalars(select(Insight).where(Insight.household_id==hh)).all())
        memory_count=len(s.scalars(select(MerchantMemory).where(MerchantMemory.household_id==hh)).all())
        audit_count=len(s.scalars(select(AuditEvent).where(AuditEvent.household_id==hh)).all())
        profile_rule_count=len(s.scalars(select(ProfileAssignmentRule).where(ProfileAssignmentRule.household_id==hh)).all())
    return {
        "household_id":hh,
        "dashboard":dashboard(hh),
        "wealth":wealth(hh),
        "transactions":list_transactions(hh),
        "counts":{
            "evidence":evidence_count,
            "corrections":correction_count,
            "insights":insight_count,
            "merchant_memory":memory_count,
            "audit_events":audit_count,
            "profile_assignment_rules":profile_rule_count,
        }
    }

@router.post("/demo-cycle")
def demo_cycle():
    hh=ensure_demo_household()
    with SessionLocal() as s:
        existing=s.scalar(select(Evidence).where(
            Evidence.household_id==hh,
            Evidence.provider=="demo_cycle",
            Evidence.subject=="Amazon receipt"
        ))
        if not existing:
            s.add(Evidence(
                household_id=hh,provider="demo_cycle",evidence_type="receipt",
                merchant="Amazon",amount=119.99,evidence_date=date(2026,9,5),
                subject="Amazon receipt",excerpt="Order total CAD 119.99"
            ))
            s.commit()
    matches=match_unlinked_evidence(hh)
    anomalies=detect_anomalies(hh)
    return {
        "cycle_complete":True,
        "evidence_matches":matches,
        "anomaly_result":anomalies,
        "dashboard":dashboard(hh),
    }
