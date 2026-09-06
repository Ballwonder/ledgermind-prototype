
from __future__ import annotations
import re
from dataclasses import dataclass, asdict
from datetime import datetime
from sqlalchemy import select
from .data_model import SessionLocal, ContextProfileMemory, Transaction, Evidence, FinancialProfile

STOPWORDS={"the","and","for","with","from","your","order","purchase","payment","invoice","receipt","online","store"}

def tokenize(text:str|None):
    if not text: return []
    toks=re.findall(r"[a-z0-9]{3,}",text.lower())
    return [t for t in toks if t not in STOPWORDS]

def descriptor_signature(tx:Transaction, evidence:list[Evidence]|None=None):
    parts=[tx.description or "", tx.merchant_raw or "", tx.merchant_normalized or ""]
    for ev in evidence or []:
        parts.extend([ev.subject or "",ev.excerpt or ""])
    toks=[]
    for p in parts:
        toks.extend(tokenize(p))
    # Keep unique tokens in stable order and cap to keep rules understandable.
    seen=[]
    for t in toks:
        if t not in seen:
            seen.append(t)
    return " ".join(seen[:12]) or None

def evidence_keywords(evidence:list[Evidence]):
    toks=[]
    for ev in evidence:
        toks.extend(tokenize((ev.subject or "")+" "+(ev.excerpt or "")))
    seen=[]
    for t in toks:
        if t not in seen:
            seen.append(t)
    return seen[:10]

def amount_band(amount:float):
    a=abs(float(amount))
    # Broad enough for repeated purchases, narrow enough to avoid universal vendor rules.
    if a<25: return (0,35)
    if a<100: return (a*.55,a*1.65)
    if a<500: return (a*.65,a*1.45)
    return (a*.75,a*1.30)

def learn_contextual_profile(household_id:int,transaction_id:int,profile_id:int):
    with SessionLocal() as s:
        tx=s.get(Transaction,transaction_id)
        profile=s.get(FinancialProfile,profile_id)
        if not tx or tx.household_id!=household_id: raise KeyError("transaction")
        if not profile or profile.household_id!=household_id: raise KeyError("profile")
        evidence=s.scalars(select(Evidence).where(Evidence.transaction_id==tx.id)).all()
        merchant=(tx.merchant_normalized or tx.merchant_raw or "").strip().lower()
        if not merchant: return None
        sig=descriptor_signature(tx,evidence)
        kws=evidence_keywords(evidence)
        lo,hi=amount_band(tx.amount)
        # Match exact contextual signature + account + merchant. Do not collapse to merchant only.
        mem=s.scalar(select(ContextProfileMemory).where(
            ContextProfileMemory.household_id==household_id,
            ContextProfileMemory.merchant_normalized==merchant,
            ContextProfileMemory.descriptor_signature==sig,
            ContextProfileMemory.account_id==tx.account_id,
            ContextProfileMemory.active==True
        ))
        if mem:
            if mem.profile_id==profile_id:
                mem.times_confirmed+=1
                mem.confidence=min(.99,mem.confidence+.01)
                mem.min_amount=min(mem.min_amount if mem.min_amount is not None else lo,lo)
                mem.max_amount=max(mem.max_amount if mem.max_amount is not None else hi,hi)
                mem.last_confirmed_at=datetime.utcnow()
            else:
                # Preserve conflicting memory as a separate rule rather than overwriting.
                mem=ContextProfileMemory(
                    household_id=household_id,profile_id=profile_id,
                    merchant_normalized=merchant,descriptor_signature=sig,
                    account_id=tx.account_id,min_amount=lo,max_amount=hi,
                    evidence_keywords=" ".join(kws) or None,confidence=.90,
                    source="conflicting_user_confirmation"
                )
                s.add(mem)
        else:
            mem=ContextProfileMemory(
                household_id=household_id,profile_id=profile_id,
                merchant_normalized=merchant,descriptor_signature=sig,
                account_id=tx.account_id,min_amount=lo,max_amount=hi,
                evidence_keywords=" ".join(kws) or None,confidence=.95
            )
            s.add(mem)
        s.commit();s.refresh(mem)
        return mem

def score_contextual_memories(household_id:int,tx:Transaction):
    with SessionLocal() as s:
        evidence=s.scalars(select(Evidence).where(Evidence.transaction_id==tx.id)).all()
        sig_tokens=set(tokenize(descriptor_signature(tx,evidence)))
        ev_tokens=set(evidence_keywords(evidence))
        merchant=(tx.merchant_normalized or tx.merchant_raw or "").strip().lower()
        memories=s.scalars(select(ContextProfileMemory).where(
            ContextProfileMemory.household_id==household_id,
            ContextProfileMemory.merchant_normalized==merchant,
            ContextProfileMemory.active==True
        )).all()
        scored=[]
        for m in memories:
            score=.33  # merchant match alone is deliberately weak
            reasons=["merchant match"]
            if m.account_id and tx.account_id==m.account_id:
                score+=.25;reasons.append("same account")
            msig=set(tokenize(m.descriptor_signature))
            if msig and sig_tokens:
                overlap=len(msig & sig_tokens)/max(1,len(msig | sig_tokens))
                score+=min(.30,overlap*.45)
                if overlap>0: reasons.append(f"descriptor overlap {overlap:.0%}")
            mkws=set(tokenize(m.evidence_keywords))
            if mkws and ev_tokens:
                overlap=len(mkws & ev_tokens)/max(1,len(mkws | ev_tokens))
                score+=min(.20,overlap*.35)
                if overlap>0: reasons.append(f"evidence overlap {overlap:.0%}")
            a=abs(tx.amount)
            if m.min_amount is not None and m.max_amount is not None and m.min_amount<=a<=m.max_amount:
                score+=.12;reasons.append("amount within learned band")
            score=min(score,m.confidence)
            scored.append({
                "memory_id":m.id,"profile_id":m.profile_id,
                "score":round(score,3),"reasons":reasons,
                "times_confirmed":m.times_confirmed
            })
        return sorted(scored,key=lambda x:x["score"],reverse=True)
