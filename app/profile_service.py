
from __future__ import annotations
from sqlalchemy import select
from .data_model import SessionLocal, FinancialProfile, Transaction, Account, AuditEvent

PROFILE_DEFAULTS = {
    "personal": {
        "entity_type": "individual",
        "activity_type": "personal",
        "tax_regime": "personal_finance",
        "gst_hst_registered": False,
    },
    "sole_proprietor": {
        "entity_type": "individual",
        "activity_type": "business_or_professional",
        "tax_regime": "T2125",
        "gst_hst_registered": False,
    },
    "corporation": {
        "entity_type": "corporation",
        "activity_type": "business",
        "tax_regime": "T2_GIFI",
        "gst_hst_registered": False,
    },
    "rental": {
        "entity_type": "individual",
        "activity_type": "rental_property",
        "tax_regime": "T776",
        "gst_hst_registered": False,
    },
}

def create_profile(household_id:int,name:str,profile_type:str,province:str|None=None,gst_hst_registered:bool|None=None):
    if profile_type not in PROFILE_DEFAULTS:
        raise ValueError("unsupported_profile_type")
    d=PROFILE_DEFAULTS[profile_type].copy()
    if gst_hst_registered is not None:
        d["gst_hst_registered"]=gst_hst_registered
    with SessionLocal() as s:
        p=FinancialProfile(
            household_id=household_id,name=name,profile_type=profile_type,
            entity_type=d["entity_type"],activity_type=d["activity_type"],
            tax_regime=d["tax_regime"],province=province,
            gst_hst_registered=d["gst_hst_registered"]
        )
        s.add(p); s.flush()
        s.add(AuditEvent(
            household_id=household_id,event_type="profile_created",
            entity_type="financial_profile",entity_id=str(p.id),
            detail_json=f'{{"profile_type":"{profile_type}","tax_regime":"{d["tax_regime"]}"}}'
        ))
        s.commit(); s.refresh(p)
        return p

def list_profiles(household_id:int):
    with SessionLocal() as s:
        rows=s.scalars(select(FinancialProfile).where(
            FinancialProfile.household_id==household_id,
            FinancialProfile.active==True
        ).order_by(FinancialProfile.id)).all()
        return [{
            "id":p.id,"name":p.name,"profile_type":p.profile_type,
            "entity_type":p.entity_type,"activity_type":p.activity_type,
            "tax_regime":p.tax_regime,"province":p.province,
            "gst_hst_registered":p.gst_hst_registered
        } for p in rows]

def assign_transaction_profile(household_id:int,transaction_id:int,profile_id:int):
    with SessionLocal() as s:
        tx=s.get(Transaction,transaction_id)
        p=s.get(FinancialProfile,profile_id)
        if not tx or tx.household_id!=household_id: raise KeyError("transaction")
        if not p or p.household_id!=household_id: raise KeyError("profile")
        old=tx.profile_id
        tx.profile_id=profile_id
        s.add(AuditEvent(
            household_id=household_id,event_type="transaction_profile_assigned",
            entity_type="transaction",entity_id=str(tx.id),
            detail_json=f'{{"old_profile_id":{repr(old)},"new_profile_id":{profile_id},"tax_regime":"{p.tax_regime}"}}'
        ))
        s.commit()
        return {"transaction_id":tx.id,"profile_id":profile_id,"profile_name":p.name,"tax_regime":p.tax_regime}

def profile_context(profile):
    return {
        "profile_id": profile.id,
        "profile_type": profile.profile_type,
        "entity_type": profile.entity_type,
        "activity_type": profile.activity_type,
        "tax_regime": profile.tax_regime,
        "gst_hst_registered": profile.gst_hst_registered,
        "province": profile.province,
    }

def treatment_boundary(profile_type:str):
    if profile_type=="personal":
        return {
            "engine_mode":"personal_finance",
            "bookkeeping_required":False,
            "tax_form":None,
            "capital_vs_current":False,
            "business_use_allocation":False,
        }
    if profile_type=="sole_proprietor":
        return {
            "engine_mode":"business_accounting",
            "bookkeeping_required":True,
            "tax_form":"T2125",
            "capital_vs_current":True,
            "business_use_allocation":True,
        }
    if profile_type=="corporation":
        return {
            "engine_mode":"corporate_accounting",
            "bookkeeping_required":True,
            "tax_form":"T2_GIFI",
            "capital_vs_current":True,
            "business_use_allocation":"shareholder_or_employee_context",
        }
    if profile_type=="rental":
        return {
            "engine_mode":"rental_accounting",
            "bookkeeping_required":True,
            "tax_form":"T776",
            "capital_vs_current":True,
            "business_use_allocation":"property_specific",
        }
    raise ValueError("unsupported_profile_type")
