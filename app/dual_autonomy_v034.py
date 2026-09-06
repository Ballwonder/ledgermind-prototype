
from dataclasses import dataclass, asdict
from .journal_gated_autonomy import decide_with_journal

@dataclass
class DualAutonomyDecision:
    transaction_id:int
    bookkeeping_route:str
    tax_route:str
    bookkeeping_safe:bool
    tax_safe:bool
    tax_hold_reason:str|None
    journal:dict|None
    overall_status:str

def decide_dual(hh,tx,facts=None):
    facts=facts or {}
    base=decide_with_journal(hh,tx,facts)
    bookkeeping_route=base.final_route
    bookkeeping_safe=base.safe_to_finish

    tax_required=bool(facts.get("gst_hst_registered") or facts.get("tax_review_required"))
    tax_docs_ok=bool(facts.get("tax_document_validated",False))
    tax_hold_reason=None
    if tax_required and not tax_docs_ok:
        tax_route="TAX_HOLD"
        tax_safe=False
        tax_hold_reason="Bookkeeping may proceed, but tax/ITC treatment is held until documentary support is sufficient."
    elif bookkeeping_route=="PROFESSIONAL_REVIEW":
        tax_route="PROFESSIONAL_REVIEW"
        tax_safe=False
    else:
        tax_route="TAX_READY"
        tax_safe=True

    if bookkeeping_safe and tax_safe:
        overall="FULLY_READY"
    elif bookkeeping_safe and not tax_safe:
        overall="BOOKS_READY_TAX_HOLD"
    else:
        overall=bookkeeping_route

    return DualAutonomyDecision(
        transaction_id=tx.id,
        bookkeeping_route=bookkeeping_route,
        tax_route=tax_route,
        bookkeeping_safe=bookkeeping_safe,
        tax_safe=tax_safe,
        tax_hold_reason=tax_hold_reason,
        journal=base.journal,
        overall_status=overall
    )
