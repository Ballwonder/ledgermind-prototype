
from sqlalchemy import select
from .data_model import SessionLocal, ProfileSourceMap, RecurringTreatmentRule, FinancialProfile, Transaction

TRUST_CAP={"dedicated":.995,"strong":.98,"supporting":.85,"weak":.65}

def source_profile_candidates(household_id:int, source_type:str, source_value:str, folder_or_label:str|None=None):
    with SessionLocal() as s:
        rows=s.scalars(select(ProfileSourceMap).where(
            ProfileSourceMap.household_id==household_id,
            ProfileSourceMap.source_type==source_type,
            ProfileSourceMap.active==True
        )).all()
        out=[]
        for r in rows:
            score=0
            reasons=[]
            if r.source_value.strip().lower()==source_value.strip().lower():
                score=min(r.confidence,TRUST_CAP.get(r.trust_level,.85)); reasons.append("mapped source")
                if r.folder_or_label:
                    if folder_or_label and r.folder_or_label.strip().lower()==folder_or_label.strip().lower():
                        score=min(.995,score+.015); reasons.append("mapped folder/label")
                    else:
                        score=min(score,.70); reasons.append("folder/label not confirmed")
            if score:
                p=s.get(FinancialProfile,r.profile_id)
                out.append({"profile_id":r.profile_id,"profile_name":p.name if p else None,
                            "confidence":round(score,3),"reasons":reasons})
        return sorted(out,key=lambda x:x["confidence"],reverse=True)

def recurring_match(household_id:int, tx:Transaction):
    with SessionLocal() as s:
        merchant=(tx.merchant_normalized or tx.merchant_raw or "").strip().lower()
        rules=s.scalars(select(RecurringTreatmentRule).where(
            RecurringTreatmentRule.household_id==household_id,
            RecurringTreatmentRule.active==True,
            RecurringTreatmentRule.merchant_normalized==merchant
        )).all()
        matches=[]
        for r in rules:
            if tx.profile_id and r.profile_id!=tx.profile_id: continue
            desc=(tx.description or "").lower()
            if r.descriptor_contains and r.descriptor_contains.lower() not in desc: continue
            if r.expected_amount:
                delta=abs(abs(tx.amount)-abs(r.expected_amount))/abs(r.expected_amount)
                if delta>r.amount_tolerance_pct: continue
            matches.append({"rule_id":r.id,"profile_id":r.profile_id,"category":r.category,
                            "treatment":r.treatment,"business_use_pct":r.business_use_pct,
                            "confidence":r.confidence})
        return sorted(matches,key=lambda x:x["confidence"],reverse=True)

def create_source_map(household_id,profile_id,source_type,source_value,folder_or_label=None,trust_level="strong"):
    with SessionLocal() as s:
        confidence=TRUST_CAP.get(trust_level,.85)
        row=ProfileSourceMap(household_id=household_id,profile_id=profile_id,
            source_type=source_type,source_value=source_value,folder_or_label=folder_or_label,
            trust_level=trust_level,confidence=confidence)
        s.add(row);s.commit();s.refresh(row);return row

def create_recurring_rule(household_id,profile_id,merchant,category=None,treatment=None,
                          business_use_pct=None,expected_amount=None,amount_tolerance_pct=.20,
                          descriptor_contains=None,cadence=None):
    with SessionLocal() as s:
        row=RecurringTreatmentRule(household_id=household_id,profile_id=profile_id,
            merchant_normalized=merchant.strip().lower(),descriptor_contains=descriptor_contains,
            category=category,treatment=treatment,business_use_pct=business_use_pct,
            expected_amount=expected_amount,amount_tolerance_pct=amount_tolerance_pct,
            cadence=cadence,confidence=.98)
        s.add(row);s.commit();s.refresh(row);return row
