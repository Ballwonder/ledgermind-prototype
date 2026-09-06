
from __future__ import annotations
from dataclasses import dataclass,asdict
from sqlalchemy import select
from .data_model import SessionLocal,Transaction,SourceDocument,ProfileSourceMap
from .document_extraction import extract_document_fields,match_document_to_transactions,ingest_document
from .evidence_sufficiency import evaluate_evidence

@dataclass
class RetrievalAttempt:
    transaction_id:int
    searched_documents:int
    candidate_documents:int
    auto_linked_documents:int
    status:str
    evidence_sufficient:bool
    evidence_confidence:float
    owner_question_required:bool
    reasons:list[str]

def _mapped_sources(household_id:int,profile_id:int|None):
    with SessionLocal() as s:
        q=select(ProfileSourceMap).where(
            ProfileSourceMap.household_id==household_id,
            ProfileSourceMap.active==True
        )
        if profile_id:
            q=q.where(ProfileSourceMap.profile_id==profile_id)
        return s.scalars(q).all()

def retrieve_for_transaction(household_id:int,transaction_id:int,max_docs:int=50):
    reasons=[]
    with SessionLocal() as s:
        tx=s.get(Transaction,transaction_id)
        if not tx or tx.household_id!=household_id:
            raise KeyError("transaction")
        profile_id=tx.profile_id
        docs=s.scalars(select(SourceDocument).where(
            SourceDocument.household_id==household_id,
            SourceDocument.processed==False
        ).order_by(SourceDocument.received_at.desc()).limit(max_docs)).all()

    maps=_mapped_sources(household_id,profile_id)
    allowed=[]
    for d in docs:
        if not maps:
            allowed.append(d)
            continue
        for m in maps:
            if m.source_type!=d.source_type:
                continue
            if m.source_value and d.source_value and m.source_value!=d.source_value:
                continue
            if m.folder_or_label and d.folder_or_label!=m.folder_or_label:
                continue
            allowed.append(d);break

    candidates=[]
    linked=0
    for d in allowed:
        extracted=extract_document_fields(d.subject,d.body)
        matches=match_document_to_transactions(household_id,extracted,max_candidates=3)
        hit=next((x for x in matches if x["transaction_id"]==transaction_id),None)
        if hit and hit["score"]>=.55:
            candidates.append((d,hit))
        if hit and hit["score"]>=.85:
            result=ingest_document(household_id,d.subject,d.body,auto_link_threshold=.85)
            if result["auto_linked_transaction_id"]==transaction_id:
                linked+=1
                with SessionLocal() as s:
                    row=s.get(SourceDocument,d.id)
                    if row:
                        row.processed=True
                        row.matched_transaction_id=transaction_id
                        s.commit()

    ev=evaluate_evidence(household_id,transaction_id)
    if ev.sufficient_for_autonomy:
        reasons.append("Available evidence sources were exhausted and sufficient support was found.")
        status="resolved"
    else:
        if candidates and linked==0:
            reasons.append("Candidate supporting documents were found, but none were safe to auto-link.")
            status="candidate_needs_confirmation"
        else:
            reasons.append("Available mapped evidence sources were exhausted without sufficient support.")
            status="unresolved"

    return RetrievalAttempt(
        transaction_id=transaction_id,
        searched_documents=len(allowed),
        candidate_documents=len(candidates),
        auto_linked_documents=linked,
        status=status,
        evidence_sufficient=ev.sufficient_for_autonomy,
        evidence_confidence=ev.confidence,
        owner_question_required=not ev.sufficient_for_autonomy,
        reasons=reasons+ev.reasons
    )

def retrieve_all_unresolved(household_id:int):
    with SessionLocal() as s:
        ids=s.scalars(select(Transaction.id).where(Transaction.household_id==household_id)).all()
    rows=[retrieve_for_transaction(household_id,i) for i in ids]
    return {
        "processed":len(rows),
        "resolved":sum(1 for r in rows if r.status=="resolved"),
        "candidate_needs_confirmation":sum(1 for r in rows if r.status=="candidate_needs_confirmation"),
        "unresolved":sum(1 for r in rows if r.status=="unresolved"),
        "auto_linked_documents":sum(r.auto_linked_documents for r in rows),
        "rows":[asdict(r) for r in rows]
    }
