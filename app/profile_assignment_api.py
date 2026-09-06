
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from .personal_service import ensure_demo_household
from .profile_assignment_engine import propose_profile, apply_profile_decision, auto_assign_safe
from dataclasses import asdict

router=APIRouter(prefix="/api/v012/profile-assignment",tags=["LedgerMind v0.12 profile assignment"])

class ConfirmIn(BaseModel):
    profile_id:int
    learn:bool=True

@router.get("/transactions/{transaction_id}")
def propose(transaction_id:int):
    hh=ensure_demo_household()
    try:
        return asdict(propose_profile(hh,transaction_id))
    except KeyError:
        raise HTTPException(404,"Transaction not found")

@router.post("/transactions/{transaction_id}/auto")
def auto(transaction_id:int):
    hh=ensure_demo_household()
    try:
        return auto_assign_safe(hh,transaction_id)
    except KeyError:
        raise HTTPException(404,"Transaction not found")

@router.post("/transactions/{transaction_id}/confirm")
def confirm(transaction_id:int,payload:ConfirmIn):
    hh=ensure_demo_household()
    try:
        return apply_profile_decision(hh,transaction_id,payload.profile_id,payload.learn)
    except KeyError:
        raise HTTPException(404,"Transaction or profile not found")
