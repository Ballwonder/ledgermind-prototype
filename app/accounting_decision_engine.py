
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, Optional

@dataclass
class AccountingDecision:
    profile_type: str
    tax_regime: str
    treatment: str
    bookkeeping_required: bool
    deductible_candidate: bool | None
    business_use_pct: float | None
    gst_hst_review: bool
    capital_review: bool
    journal_template: list[dict[str,Any]]
    review_required: bool
    owner_question: str | None
    rationale: list[str]
    confidence: float

def _base(profile:dict):
    return {
        "profile_type":profile["profile_type"],
        "tax_regime":profile["tax_regime"],
        "bookkeeping_required": profile["profile_type"]!="personal",
        "gst_hst_review": bool(profile.get("gst_hst_registered")),
    }

def evaluate_transaction(profile:dict, tx:dict, facts:dict|None=None)->AccountingDecision:
    facts=facts or {}
    amount=abs(float(tx.get("amount",0)))
    category=tx.get("category","Other")
    item_type=facts.get("item_type") or tx.get("item_type")
    business_use=facts.get("business_use_pct")
    lasting=bool(facts.get("lasting_benefit"))
    improvement=bool(facts.get("improves_beyond_original_condition"))
    restores=bool(facts.get("restores_original_condition"))
    personal_component=bool(facts.get("personal_component_present"))
    ptype=profile["profile_type"]
    rationale=[]
    review=False
    question=None
    journal=[]

    if ptype=="personal":
        rationale.append("Personal profile: transaction is analyzed for household cash flow/net worth, not business deductibility.")
        return AccountingDecision(
            profile_type=ptype,tax_regime=profile["tax_regime"],treatment="personal_spending",
            bookkeeping_required=False,deductible_candidate=None,business_use_pct=None,
            gst_hst_review=False,capital_review=False,journal_template=[],
            review_required=False,owner_question=None,rationale=rationale,confidence=.99
        )

    # Shared business/rental capital screen
    capital_candidate = item_type in {"durable_asset","capital_asset"} or lasting or improvement
    if capital_candidate and not restores:
        rationale.append("Facts indicate a lasting benefit, separate asset, or improvement beyond original condition.")
        review=True

    if ptype=="sole_proprietor":
        if business_use is None and personal_component:
            question="What percentage of this purchase was for business use?"
            rationale.append("Sole-proprietor expenses must exclude the personal portion.")
        elif business_use is None:
            business_use=1.0
        deductible=not capital_candidate
        treatment="capital_asset_candidate" if capital_candidate else "current_business_expense_candidate"
        rationale.append("Sole proprietor profile routes business/professional expenses through the T2125-oriented ruleset.")
        if capital_candidate:
            rationale.append("Capital property is not treated as an ordinary current expense; CCA/capital treatment must be evaluated.")
        if profile.get("gst_hst_registered"):
            rationale.append("GST/HST registration is active, so ITC/documentary support must be evaluated separately.")
        if not capital_candidate:
            pct=business_use if business_use is not None else 1.0
            journal=[
                {"debit":category or "Business Expense","amount":"business_portion_net_of_recoverable_tax"},
                {"credit":"Cash / Credit Card","amount":amount},
            ]
        return AccountingDecision(
            profile_type=ptype,tax_regime=profile["tax_regime"],treatment=treatment,
            bookkeeping_required=True,deductible_candidate=deductible,
            business_use_pct=business_use,gst_hst_review=bool(profile.get("gst_hst_registered")),
            capital_review=capital_candidate, journal_template=journal,
            review_required=review,owner_question=question,rationale=rationale,
            confidence=.82 if question or review else .94
        )

    if ptype=="rental":
        treatment="rental_current_expense_candidate"
        deductible=True
        if capital_candidate:
            treatment="rental_capital_candidate"
            deductible=False
            review=True
            rationale.append("Rental-property improvements or separate capital assets require capital-vs-current review.")
        elif restores:
            rationale.append("Restoration to original condition supports current repair treatment.")
        else:
            rationale.append("Rental profile routes property-level expenses through the T776-oriented ruleset.")
        journal=[
            {"debit":"Rental Expense" if not capital_candidate else "Rental Capital Asset","amount":amount},
            {"credit":"Cash / Credit Card","amount":amount},
        ]
        return AccountingDecision(
            profile_type=ptype,tax_regime=profile["tax_regime"],treatment=treatment,
            bookkeeping_required=True,deductible_candidate=deductible,business_use_pct=None,
            gst_hst_review=bool(profile.get("gst_hst_registered")),capital_review=capital_candidate,
            journal_template=journal,review_required=review,owner_question=None,
            rationale=rationale,confidence=.88 if review else .95
        )

    if ptype=="corporation":
        if personal_component:
            review=True
            treatment="shareholder_or_employee_benefit_review"
            rationale.append("A corporation paying a personal expense requires review of shareholder/employee benefit treatment rather than ordinary expense treatment.")
            return AccountingDecision(
                profile_type=ptype,tax_regime=profile["tax_regime"],treatment=treatment,
                bookkeeping_required=True,deductible_candidate=False,business_use_pct=None,
                gst_hst_review=bool(profile.get("gst_hst_registered")),capital_review=capital_candidate,
                journal_template=[],review_required=True,owner_question="Was the benefit received in the person's capacity as an employee or shareholder?",
                rationale=rationale,confidence=.80
            )
        treatment="corporate_capital_asset_candidate" if capital_candidate else "corporate_business_expense_candidate"
        rationale.append("Corporate profile uses corporate bookkeeping and T2/GIFI-oriented reporting context.")
        if capital_candidate:
            rationale.append("Capital-vs-current treatment must be resolved before final posting.")
        journal=[
            {"debit":"Corporate Expense" if not capital_candidate else "Capital Asset","amount":amount},
            {"credit":"Cash / Credit Card","amount":amount},
        ]
        return AccountingDecision(
            profile_type=ptype,tax_regime=profile["tax_regime"],treatment=treatment,
            bookkeeping_required=True,deductible_candidate=not capital_candidate,business_use_pct=None,
            gst_hst_review=bool(profile.get("gst_hst_registered")),capital_review=capital_candidate,
            journal_template=journal,review_required=review,owner_question=None,
            rationale=rationale,confidence=.88 if review else .94
        )

    raise ValueError("unsupported_profile_type")

def as_payload(decision:AccountingDecision):
    return asdict(decision)
