
from __future__ import annotations
from dataclasses import dataclass, asdict
from .autonomy_router import decide_autonomy
from .journal_engine_v027 import build_journal, payload as journal_payload

@dataclass
class JournalGatedDecision:
    transaction_id:int
    base_route:str
    final_route:str
    safe_to_finish:bool
    journal_status:str
    journal:dict
    missing_facts:list[str]
    review_reasons:list[str]
    owner_question:str|None
    professional_review_reason:str|None
    proposed_treatment:str|None
    confidence:dict

def decide_with_journal(household_id:int, tx, facts:dict|None=None):
    facts=facts or {}
    base=decide_autonomy(household_id,tx.id,facts)

    # If accounting/evidence/profile routing already requires a person, preserve it.
    if base.route!="AUTO_FINISH":
        return JournalGatedDecision(
            transaction_id=tx.id,base_route=base.route,final_route=base.route,
            safe_to_finish=False,journal_status="not_attempted",
            journal={},missing_facts=[],review_reasons=[],
            owner_question=base.owner_question,
            professional_review_reason=base.professional_review_reason,
            proposed_treatment=base.proposed_treatment,
            confidence=base.confidence
        )

    jf=dict(facts)
    if base.proposed_treatment and "capital" in str(base.proposed_treatment).lower():
        jf.setdefault("transaction_type","fixed_asset")

    journal=build_journal({
        "amount":tx.amount,
        "description":tx.description,
        "category":tx.category,
        "source_account":"Cash/Bank"
    },jf)
    jp=journal_payload(journal)

    if journal.missing_facts:
        q="Provide the missing accounting facts needed to complete the journal: "+", ".join(journal.missing_facts)+"."
        return JournalGatedDecision(
            transaction_id=tx.id,base_route=base.route,final_route="OWNER_QUESTION",
            safe_to_finish=False,journal_status="missing_facts",
            journal=jp,missing_facts=journal.missing_facts,
            review_reasons=[],owner_question=q,
            professional_review_reason=None,
            proposed_treatment=base.proposed_treatment,
            confidence=base.confidence
        )

    if not journal.balanced:
        return JournalGatedDecision(
            transaction_id=tx.id,base_route=base.route,final_route="PROFESSIONAL_REVIEW",
            safe_to_finish=False,journal_status="unbalanced",
            journal=jp,missing_facts=[],
            review_reasons=["Journal is not balanced."],
            owner_question=None,
            professional_review_reason="Proposed journal failed debit/credit balance validation.",
            proposed_treatment=base.proposed_treatment,
            confidence=base.confidence
        )

    if journal.review_required:
        reasons=list(journal.warnings or [])
        return JournalGatedDecision(
            transaction_id=tx.id,base_route=base.route,final_route="PROFESSIONAL_REVIEW",
            safe_to_finish=False,journal_status="review_required",
            journal=jp,missing_facts=[],
            review_reasons=reasons,
            owner_question=None,
            professional_review_reason="Journal-level accounting review is required. "+(" ".join(reasons) if reasons else ""),
            proposed_treatment=base.proposed_treatment,
            confidence=base.confidence
        )

    return JournalGatedDecision(
        transaction_id=tx.id,base_route=base.route,final_route="AUTO_FINISH",
        safe_to_finish=True,journal_status="ready",
        journal=jp,missing_facts=[],review_reasons=[],
        owner_question=None,professional_review_reason=None,
        proposed_treatment=base.proposed_treatment,
        confidence=base.confidence
    )
