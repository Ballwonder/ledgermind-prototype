
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any
from sqlalchemy import select
from .data_model import SessionLocal, Transaction, FinancialProfile, Evidence
from .profile_assignment_engine import propose_profile
from .accounting_decision_engine import evaluate_transaction
from .accounting_precedent_engine import precedent_decision
from .evidence_sufficiency import evaluate_evidence

@dataclass
class AutonomyDecision:
    transaction_id:int
    route:str
    safe_to_finish:bool
    profile_status:str
    accounting_status:str
    evidence_status:str
    precedent_status:str
    weakest_material_factor:str
    reasons:list[str]
    owner_question:str|None
    professional_review_reason:str|None
    confidence:dict[str,float]
    proposed_profile_id:int|None
    proposed_profile_name:str|None
    proposed_treatment:str|None

def _evidence_quality(evidence):
    if not evidence:
        return .35,"missing"
    score=.45
    has_amount=any(e.amount is not None for e in evidence)
    has_date=any(e.evidence_date is not None for e in evidence)
    has_subject=any(bool(e.subject) for e in evidence)
    has_excerpt=any(bool(e.excerpt) for e in evidence)
    if has_amount: score+=.18
    if has_date: score+=.12
    if has_subject: score+=.10
    if has_excerpt: score+=.15
    score=min(score,1.0)
    status="strong" if score>=.85 else "partial" if score>=.65 else "weak"
    return round(score,3),status

def decide_autonomy(household_id:int, transaction_id:int, facts:dict|None=None):
    facts=facts or {}
    reasons=[]
    owner_q=None
    pro_reason=None

    with SessionLocal() as s:
        tx=s.get(Transaction,transaction_id)
        if not tx or tx.household_id!=household_id:
            raise KeyError("transaction")

        # PROFILE
        pdecision=propose_profile(household_id,transaction_id)
        proposed_profile_id=pdecision.proposed_profile_id
        proposed_profile_name=pdecision.proposed_profile_name
        profile_conf=pdecision.confidence

        # If already assigned, use it. If auto-assignable, use proposed context for decision support
        # but do not mutate here.
        profile=None
        if tx.profile_id:
            profile=s.get(FinancialProfile,tx.profile_id)
            profile_status="assigned"
            profile_conf=1.0
        elif pdecision.action=="auto_assign" and proposed_profile_id:
            profile=s.get(FinancialProfile,proposed_profile_id)
            profile_status="auto_assignable"
        elif pdecision.action=="confirm_profile":
            profile_status="needs_confirmation"
        else:
            profile_status="unknown"

        # Evidence is evaluated by purpose after accounting treatment is known.
        evidence=s.scalars(select(Evidence).where(Evidence.transaction_id==tx.id)).all()
        ev_conf, ev_status=_evidence_quality(evidence)

        # No profile = cannot safely continue to accounting treatment.
        if not profile:
            owner_q=pdecision.question or "Which financial profile does this transaction belong to?"
            return AutonomyDecision(
                transaction_id=tx.id,route="OWNER_QUESTION",safe_to_finish=False,
                profile_status=profile_status,accounting_status="blocked",
                evidence_status=ev_status,precedent_status="not_evaluated",
                weakest_material_factor="profile_assignment",
                reasons=(pdecision.reasons or [])+["Accounting/tax treatment cannot be finalized until the correct financial profile is known."],
                owner_question=owner_q,professional_review_reason=None,
                confidence={"profile":round(profile_conf,3),"evidence":ev_conf,"accounting":0.0,"precedent":0.0},
                proposed_profile_id=proposed_profile_id,proposed_profile_name=proposed_profile_name,
                proposed_treatment=None
            )

        profile_payload={
            "profile_type":profile.profile_type,
            "tax_regime":profile.tax_regime,
            "gst_hst_registered":profile.gst_hst_registered,
            "province":profile.province
        }
        tx_payload={
            "amount":tx.amount,
            "category":tx.category,
            "merchant":tx.merchant_normalized or tx.merchant_raw,
            "item_type":facts.get("item_type")
        }

        adecision=evaluate_transaction(profile_payload,tx_payload,facts)
        accounting_conf=adecision.confidence
        accounting_status="review_required" if adecision.review_required else ("needs_fact" if adecision.owner_question else "resolved_candidate")

        # PRECEDENT
        pred=precedent_decision(household_id,transaction_id,facts)
        pred_action=pred["action"]
        pred_conf=pred["match"]["score"] if pred.get("match") else 0.0

        # Owner question from accounting facts wins over review if it can resolve uncertainty first.
        if adecision.owner_question:
            reasons.extend(adecision.rationale)
            reasons.append("A factual owner answer may resolve the accounting uncertainty without professional review.")
            return AutonomyDecision(
                tx.id,"OWNER_QUESTION",False,profile_status,accounting_status,ev_status,pred_action,
                "missing_owner_fact",reasons,adecision.owner_question,None,
                {"profile":round(profile_conf,3),"evidence":ev_conf,"accounting":round(accounting_conf,3),"precedent":round(pred_conf,3)},
                profile.id,profile.name,adecision.treatment
            )

        # Explicit accounting review triggers are material.
        if adecision.review_required:
            # Strong precedent can reduce uncertainty, but doesn't override a material review gate by itself.
            reasons.extend(adecision.rationale)
            if pred_action=="apply_precedent":
                reasons.append("A strong scoped precedent exists, but the underlying issue is still marked review-sensitive.")
            pro_reason="Material accounting/tax judgment remains after available facts and precedents."
            return AutonomyDecision(
                tx.id,"PROFESSIONAL_REVIEW",False,profile_status,accounting_status,ev_status,pred_action,
                "professional_judgment",reasons,None,pro_reason,
                {"profile":round(profile_conf,3),"evidence":ev_conf,"accounting":round(accounting_conf,3),"precedent":round(pred_conf,3)},
                profile.id,profile.name,adecision.treatment
            )

        # Purpose-specific evidence sufficiency.
        ev_result=evaluate_evidence(household_id,tx.id,adecision.treatment,facts)
        ev_conf=ev_result.confidence
        ev_status=ev_result.status
        if not ev_result.sufficient_for_autonomy:
            reasons.extend(adecision.rationale)
            reasons.extend(ev_result.reasons)
            q="Please provide or confirm: " + "; ".join(ev_result.missing) if ev_result.missing else "Please provide the supporting information needed for this transaction."
            return AutonomyDecision(
                tx.id,"OWNER_QUESTION",False,profile_status,accounting_status,ev_status,pred_action,
                "evidence_sufficiency",reasons,q,None,
                {"profile":round(profile_conf,3),"evidence":round(ev_conf,3),"accounting":round(accounting_conf,3),"precedent":round(pred_conf,3)},
                profile.id,profile.name,adecision.treatment
            )

        # Confidence gate: do not average away weak components.
        material_conf={
            "profile":profile_conf,
            "evidence":ev_conf,
            "accounting":accounting_conf
        }
        if pred_action=="apply_precedent":
            material_conf["precedent"]=pred_conf
        weakest=min(material_conf,key=material_conf.get)
        weakest_value=material_conf[weakest]

        # Autonomous finish requires all core components >= .90
        if weakest_value >= .90:
            reasons.extend(adecision.rationale)
            if pred_action=="apply_precedent":
                reasons.append("A strong, scoped accounting precedent supports the treatment.")
            reasons.append("All material confidence components meet the autonomous completion threshold.")
            return AutonomyDecision(
                tx.id,"AUTO_FINISH",True,profile_status,accounting_status,ev_status,pred_action,
                weakest,reasons,None,None,
                {k:round(v,3) for k,v in material_conf.items()},
                profile.id,profile.name,adecision.treatment
            )

        # Mid-confidence case: ask owner only if fact confirmation is the likely cheapest resolution.
        reasons.extend(adecision.rationale)
        reasons.append(f"The weakest material component is {weakest} at {weakest_value:.2f}.")
        return AutonomyDecision(
            tx.id,"OWNER_QUESTION",False,profile_status,accounting_status,ev_status,pred_action,
            weakest,reasons,"Can you confirm the purpose and treatment context for this transaction?",None,
            {k:round(v,3) for k,v in material_conf.items()},
            profile.id,profile.name,adecision.treatment
        )

def as_payload(d:AutonomyDecision):
    return asdict(d)
