
from __future__ import annotations
from dataclasses import dataclass, asdict
from sqlalchemy import select
from .data_model import SessionLocal, FinancialProfile, Account, Transaction, Evidence, ProfileAssignmentRule, AuditEvent
from .contextual_profile_memory import score_contextual_memories, learn_contextual_profile

@dataclass
class ProfileAssignmentDecision:
    transaction_id:int
    proposed_profile_id:int|None
    proposed_profile_name:str|None
    confidence:float
    action:str
    reasons:list[str]
    question:str|None

def _profile_map(session, household_id):
    rows=session.scalars(select(FinancialProfile).where(
        FinancialProfile.household_id==household_id,
        FinancialProfile.active==True
    )).all()
    return {p.id:p for p in rows}

def _match_rules(session, household_id, tx):
    merchant=(tx.merchant_normalized or tx.merchant_raw or "").strip().lower()
    desc=(tx.description or "").strip().lower()
    rules=session.scalars(select(ProfileAssignmentRule).where(
        ProfileAssignmentRule.household_id==household_id,
        ProfileAssignmentRule.active==True
    )).all()
    candidates=[]
    for r in rules:
        mv=(r.match_value or "").lower()
        sv=(r.secondary_value or "").lower() if r.secondary_value else None
        if r.rule_type=="merchant" and mv and merchant==mv:
            candidates.append((r.confidence,r.profile_id,f"Confirmed merchant rule: {r.match_value}"))
        elif r.rule_type=="merchant_descriptor" and mv and merchant==mv and sv and sv in desc:
            candidates.append((min(.99,r.confidence+.02),r.profile_id,f"Confirmed merchant + descriptor rule: {r.match_value} / {r.secondary_value}"))
    return sorted(candidates, reverse=True)

def propose_profile(household_id:int, transaction_id:int)->ProfileAssignmentDecision:
    with SessionLocal() as s:
        tx=s.get(Transaction,transaction_id)
        if not tx or tx.household_id!=household_id:
            raise KeyError("transaction")
        profiles=_profile_map(s,household_id)
        reasons=[]
        candidates=[]

        # 1) Explicit existing assignment is authoritative.
        if tx.profile_id and tx.profile_id in profiles:
            p=profiles[tx.profile_id]
            return ProfileAssignmentDecision(tx.id,p.id,p.name,1.0,"keep_assigned",["Transaction already has an explicit profile assignment."],None)

        # 2) Account ownership is strong evidence, but only if account is explicitly profile-bound.
        if tx.account_id:
            acct=s.get(Account,tx.account_id)
            if acct and acct.profile_id in profiles:
                candidates.append((.98,acct.profile_id,f"Source account is assigned to {profiles[acct.profile_id].name}."))

        # 3) Contextual user-confirmed memory.
        contextual=score_contextual_memories(household_id,tx)
        for cm in contextual:
            candidates.append((cm["score"],cm["profile_id"],"Contextual memory: "+", ".join(cm["reasons"])))
        # 4) Legacy merchant rules remain low-priority compatibility evidence.
        for conf,pid,reason in _match_rules(s,household_id,tx):
            candidates.append((min(conf,.72),pid,"Legacy "+reason))

        # 5) Linked evidence can provide explicit profile/property/business text.
        evs=s.scalars(select(Evidence).where(Evidence.transaction_id==tx.id)).all()
        evidence_text=" ".join([(e.subject or "")+" "+(e.excerpt or "") for e in evs]).lower()
        for p in profiles.values():
            pname=p.name.lower()
            if pname and pname in evidence_text:
                candidates.append((.96,p.id,f"Linked evidence explicitly references profile name '{p.name}'."))
            if p.profile_type=="rental" and ("rental" in evidence_text or "tenant" in evidence_text):
                candidates.append((.82,p.id,"Linked evidence contains rental/property context."))
            if p.profile_type=="sole_proprietor" and ("business" in evidence_text or "client" in evidence_text):
                candidates.append((.78,p.id,"Linked evidence contains business/client context."))

        # Consolidate by profile, highest confidence.
        best={}
        why={}
        for conf,pid,reason in candidates:
            if pid not in best or conf>best[pid]:
                best[pid]=conf; why[pid]=[reason]
            elif abs(conf-best[pid])<1e-9:
                why[pid].append(reason)

        ranked=sorted([(c,pid) for pid,c in best.items()], reverse=True)
        if not ranked:
            return ProfileAssignmentDecision(
                tx.id,None,None,0.0,"owner_question",[],
                "Which financial profile does this transaction belong to?"
            )

        top_conf,top_pid=ranked[0]
        second_conf=ranked[1][0] if len(ranked)>1 else 0.0
        p=profiles[top_pid]
        reasons=why[top_pid]

        # Require separation from competing profile candidates.
        if top_conf>=.95 and (top_conf-second_conf)>=.10:
            return ProfileAssignmentDecision(tx.id,p.id,p.name,top_conf,"auto_assign",reasons,None)
        if top_conf>=.80:
            return ProfileAssignmentDecision(
                tx.id,p.id,p.name,top_conf,"confirm_profile",reasons,
                f"Does this transaction belong to {p.name}?"
            )
        return ProfileAssignmentDecision(
            tx.id,None,None,top_conf,"owner_question",reasons,
            "Which financial profile does this transaction belong to?"
        )

def apply_profile_decision(household_id:int, transaction_id:int, profile_id:int, learn:bool=True):
    with SessionLocal() as s:
        tx=s.get(Transaction,transaction_id)
        p=s.get(FinancialProfile,profile_id)
        if not tx or tx.household_id!=household_id: raise KeyError("transaction")
        if not p or p.household_id!=household_id: raise KeyError("profile")
        old=tx.profile_id
        tx.profile_id=profile_id
        merchant=(tx.merchant_normalized or tx.merchant_raw or "").strip()
        s.add(AuditEvent(
            household_id=household_id,event_type="profile_assignment_confirmed",
            entity_type="transaction",entity_id=str(tx.id),
            detail_json=f'{{"old_profile_id":{repr(old)},"new_profile_id":{profile_id},"learn":{str(learn).lower()}}}'
        ))
        s.commit()
        if learn and merchant:
            learn_contextual_profile(household_id,transaction_id,profile_id)
        return {"transaction_id":tx.id,"profile_id":profile_id,"profile_name":p.name,"learned":bool(learn and merchant)}

def auto_assign_safe(household_id:int, transaction_id:int):
    d=propose_profile(household_id,transaction_id)
    if d.action=="auto_assign" and d.proposed_profile_id:
        result=apply_profile_decision(household_id,transaction_id,d.proposed_profile_id,learn=False)
        return {"decision":asdict(d),"applied":True,"result":result}
    return {"decision":asdict(d),"applied":False}
