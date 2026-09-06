
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from .personal_service import ensure_demo_household
from .profile_service import create_profile, list_profiles, assign_transaction_profile, treatment_boundary

router=APIRouter(prefix="/api/v010/profiles",tags=["LedgerMind v0.10 profiles"])

class ProfileIn(BaseModel):
    name:str
    profile_type:str
    province:str|None="Ontario"
    gst_hst_registered:bool|None=None

class AssignProfile(BaseModel):
    profile_id:int

@router.get("")
def get_profiles():
    hh=ensure_demo_household()
    return {"profiles":list_profiles(hh)}

@router.post("")
def add_profile(payload:ProfileIn):
    hh=ensure_demo_household()
    try:
        p=create_profile(hh,payload.name,payload.profile_type,payload.province,payload.gst_hst_registered)
    except ValueError:
        raise HTTPException(400,"Unsupported profile type")
    return {
        "id":p.id,"name":p.name,"profile_type":p.profile_type,
        "entity_type":p.entity_type,"activity_type":p.activity_type,
        "tax_regime":p.tax_regime,"gst_hst_registered":p.gst_hst_registered,
        "treatment_boundary":treatment_boundary(p.profile_type)
    }

@router.post("/transactions/{transaction_id}/assign")
def assign(transaction_id:int,payload:AssignProfile):
    hh=ensure_demo_household()
    try:
        return assign_transaction_profile(hh,transaction_id,payload.profile_id)
    except KeyError as e:
        raise HTTPException(404,str(e))
