
from __future__ import annotations
from dataclasses import dataclass, asdict
from sqlalchemy import select
from .data_model import SessionLocal, Transaction, Evidence, FinancialProfile
from .streamlining_engine import recurring_match

@dataclass
class EnrichmentResult:
    transaction_id:int
    inferred_profile_id:int|None
    inferred_profile_name:str|None
    profile_confidence:float
    category:str|None
    category_confidence:float
    facts:dict
    evidence_quality:float
    reasons:list[str]
    changed:bool

def _ev_quality(evidence):
    if not evidence: return .35
    score=.45
    if any(e.amount is not None for e in evidence): score+=.18
    if any(e.evidence_date is not None for e in evidence): score+=.12
    if any(bool(e.subject) for e in evidence): score+=.10
    if any(bool(e.excerpt) for e in evidence): score+=.15
    return min(1.0,round(score,3))

def enrich_transaction(household_id:int, transaction_id:int, persist:bool=True):
    reasons=[]
    changed=False
    with SessionLocal() as s:
        tx=s.get(Transaction,transaction_id)
        if not tx or tx.household_id!=household_id: raise KeyError("transaction")
        evidence=s.scalars(select(Evidence).where(Evidence.transaction_id==tx.id)).all()
        recurring=recurring_match(household_id,tx)
        rr=recurring[0] if recurring else None

        profile_id=tx.profile_id
        profile_conf=1.0 if profile_id else 0.0

        # Recurring rule can supply profile when transaction itself is not assigned.
        if not profile_id and rr:
            profile_id=rr["profile_id"]; profile_conf=rr["confidence"]
            reasons.append("profile inferred from recurring rule")
            if persist and profile_conf>=.98:
                tx.profile_id=profile_id; changed=True

        text=" ".join([
            tx.description or "", tx.category or "",
            " ".join([(e.subject or "")+" "+(e.excerpt or "") for e in evidence])
        ]).lower()

        category=tx.category
        cat_conf=float(tx.category_confidence or 0)
        if rr and rr.get("category"):
            category=rr["category"]; cat_conf=max(cat_conf,rr["confidence"])
            reasons.append("category supplied by recurring rule")
        elif any(k in text for k in ["toner","printer paper","office supplies","stationery"]):
            category="Office Supplies"; cat_conf=max(cat_conf,.94); reasons.append("office-supply evidence")
        elif any(k in text for k in ["mobile service","wireless","internet","phone"]):
            category="Utilities"; cat_conf=max(cat_conf,.90); reasons.append("telecom evidence")
        elif any(k in text for k in ["plumbing","repair","shingle","maintenance"]):
            category="Repairs"; cat_conf=max(cat_conf,.90); reasons.append("repair evidence")
        elif any(k in text for k in ["client payment","consulting income","invoice paid"]):
            category="Revenue"; cat_conf=max(cat_conf,.94); reasons.append("revenue evidence")

        if persist and category and category != tx.category:
            tx.category=category; tx.category_confidence=cat_conf; changed=True
        elif persist and cat_conf > float(tx.category_confidence or 0):
            tx.category_confidence=cat_conf; changed=True

        facts={
            "item_type":None,
            "business_use_pct":None,
            "personal_component_present":False,
            "lasting_benefit":False,
            "restores_original_condition":False,
            "improves_beyond_original_condition":False,
        }

        if any(k in text for k in ["toner","printer paper","office supplies","stationery"]):
            facts["item_type"]="consumable"
        elif any(k in text for k in ["mobile service","wireless","internet","phone"]):
            facts["item_type"]="service"
        elif any(k in text for k in ["repair","plumbing","shingle","maintenance"]):
            facts["item_type"]="repair"
            if any(k in text for k in ["restore original","same material","same materials","damaged shingles"]):
                facts["restores_original_condition"]=True
        elif any(k in text for k in ["renovation","upgrade","improvement","improved finishes"]):
            facts["item_type"]="repair"
            facts["lasting_benefit"]=True
            facts["improves_beyond_original_condition"]=True

        if rr and rr.get("business_use_pct") is not None:
            facts["business_use_pct"]=rr["business_use_pct"]
            facts["personal_component_present"]=rr["business_use_pct"]<1
            reasons.append("business-use allocation supplied by recurring rule")

        if profile_id:
            p=s.get(FinancialProfile,profile_id)
            profile_name=p.name if p else None
        else:
            profile_name=None

        if persist and changed:
            s.commit()

        return EnrichmentResult(
            transaction_id=tx.id,
            inferred_profile_id=profile_id,
            inferred_profile_name=profile_name,
            profile_confidence=round(profile_conf,3),
            category=category,
            category_confidence=round(cat_conf,3),
            facts=facts,
            evidence_quality=_ev_quality(evidence),
            reasons=reasons,
            changed=changed
        )

def enrich_household(household_id:int,persist:bool=True):
    with SessionLocal() as s:
        ids=s.scalars(select(Transaction.id).where(Transaction.household_id==household_id)).all()
    rows=[enrich_transaction(household_id,i,persist=persist) for i in ids]
    return {
        "processed":len(rows),
        "changed":sum(1 for r in rows if r.changed),
        "profile_inferred":sum(1 for r in rows if r.inferred_profile_id is not None),
        "high_conf_category":sum(1 for r in rows if r.category_confidence>=.90),
        "rows":[asdict(r) for r in rows]
    }
