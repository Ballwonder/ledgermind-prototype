
from __future__ import annotations
import re
from datetime import datetime
from sqlalchemy import select
from .data_model import SessionLocal, AccountingPrecedent, Transaction, Evidence, FinancialProfile

AUTHORITY_RANK = {
    "statute_regulation": 1,
    "cra_guidance": 2,
    "accounting_standard": 3,
    "firm_policy": 4,
    "client_policy": 5,
    "reviewer_precedent": 6,
    "model_inference": 7,
}

STOPWORDS={"the","and","for","with","from","your","invoice","receipt","payment","order","purchase"}

def toks(text):
    if not text: return set()
    return {x for x in re.findall(r"[a-z0-9]{3,}", text.lower()) if x not in STOPWORDS}

def evidence_tokens(evidence):
    out=set()
    for e in evidence:
        out |= toks((e.subject or "")+" "+(e.excerpt or ""))
    return out

def amount_band(amount):
    a=abs(float(amount))
    if a<100: return (a*.5,a*1.75)
    if a<1000: return (a*.6,a*1.5)
    return (a*.7,a*1.4)

def learn_precedent(household_id:int, transaction_id:int, final_treatment:str,
                     facts:dict, rationale:str="", authority_level:str="reviewer_precedent",
                     account_or_category:str|None=None):
    with SessionLocal() as s:
        tx=s.get(Transaction,transaction_id)
        if not tx or tx.household_id!=household_id: raise KeyError("transaction")
        if not tx.profile_id: raise ValueError("profile_required")
        ev=s.scalars(select(Evidence).where(Evidence.transaction_id==tx.id)).all()
        lo,hi=amount_band(tx.amount)
        merchant=(tx.merchant_normalized or tx.merchant_raw or "").strip().lower() or None
        kw=" ".join(sorted(evidence_tokens(ev))) or None
        p=AccountingPrecedent(
            household_id=household_id, profile_id=tx.profile_id,
            treatment=final_treatment, account_or_category=account_or_category,
            item_type=facts.get("item_type"), merchant_normalized=merchant,
            min_amount=lo,max_amount=hi,business_use_pct=facts.get("business_use_pct"),
            restores_original_condition=facts.get("restores_original_condition"),
            improves_beyond_original_condition=facts.get("improves_beyond_original_condition"),
            lasting_benefit=facts.get("lasting_benefit"),
            personal_component_present=facts.get("personal_component_present"),
            evidence_keywords=kw,rationale=rationale,
            authority_level=authority_level,confidence=.95
        )
        s.add(p);s.commit();s.refresh(p)
        return p

def _bool_match(expected, actual):
    if expected is None: return None
    return bool(expected)==bool(actual)

def score_precedent(p, tx, facts, ev_tokens):
    # Critical scope: profile must match exactly.
    if p.profile_id != tx.profile_id:
        return None
    score=.0; reasons=[]
    # Item type is highly material.
    if p.item_type:
        if p.item_type != facts.get("item_type"):
            return None
        score+=.28; reasons.append("same item type")
    # Material current-vs-capital facts: mismatches invalidate rather than merely lower score.
    for field,label in [
        ("restores_original_condition","same restoration fact"),
        ("improves_beyond_original_condition","same improvement fact"),
        ("lasting_benefit","same lasting-benefit fact"),
        ("personal_component_present","same personal-component fact")
    ]:
        exp=getattr(p,field)
        if exp is not None:
            if bool(exp)!=bool(facts.get(field)):
                return None
            score+=.12;reasons.append(label)
    if p.business_use_pct is not None:
        actual=facts.get("business_use_pct")
        if actual is None or abs(float(actual)-float(p.business_use_pct))>.10:
            return None
        score+=.10;reasons.append("similar business-use allocation")
    # Merchant is supporting context, never sufficient.
    merchant=(tx.merchant_normalized or tx.merchant_raw or "").strip().lower()
    if p.merchant_normalized and merchant==p.merchant_normalized:
        score+=.08;reasons.append("same merchant")
    a=abs(tx.amount)
    if p.min_amount is not None and p.max_amount is not None and p.min_amount<=a<=p.max_amount:
        score+=.08;reasons.append("amount within precedent band")
    pkw=toks(p.evidence_keywords)
    if pkw and ev_tokens:
        overlap=len(pkw & ev_tokens)/max(1,len(pkw | ev_tokens))
        score+=min(.14,overlap*.25)
        if overlap>0: reasons.append(f"evidence overlap {overlap:.0%}")
    # Authority confidence caps final similarity.
    score=min(score,p.confidence)
    return {"precedent_id":p.id,"score":round(score,3),"treatment":p.treatment,
            "account_or_category":p.account_or_category,"authority_level":p.authority_level,
            "reasons":reasons,"rationale":p.rationale}

def find_precedents(household_id:int, transaction_id:int, facts:dict):
    with SessionLocal() as s:
        tx=s.get(Transaction,transaction_id)
        if not tx or tx.household_id!=household_id: raise KeyError("transaction")
        ev=s.scalars(select(Evidence).where(Evidence.transaction_id==tx.id)).all()
        evt=evidence_tokens(ev)
        rows=s.scalars(select(AccountingPrecedent).where(
            AccountingPrecedent.household_id==household_id,
            AccountingPrecedent.active==True
        )).all()
        scored=[]
        for p in rows:
            sp=score_precedent(p,tx,facts,evt)
            if sp: scored.append(sp)
        # Higher authority first, then similarity.
        scored.sort(key=lambda x:(AUTHORITY_RANK.get(x["authority_level"],99),-x["score"]))
        return scored

def precedent_decision(household_id:int, transaction_id:int, facts:dict):
    matches=find_precedents(household_id,transaction_id,facts)
    if not matches:
        return {"action":"no_precedent","match":None}
    best=matches[0]
    competing=[m for m in matches[1:] if m["authority_level"]==best["authority_level"] and m["treatment"]!=best["treatment"]]
    if best["score"]>=.90 and not competing:
        return {"action":"apply_precedent","match":best}
    if best["score"]>=.75:
        return {"action":"review_precedent","match":best}
    return {"action":"no_precedent","match":best}
