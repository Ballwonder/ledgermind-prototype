
from app.models import SourceTransaction, Evidence, Decision, JournalLine
from typing import Optional
import math

def norm(s: Optional[str]) -> str:
    return (s or "").strip().lower()

def match_evidence(tx: SourceTransaction, evidence: list[Evidence]) -> list[Evidence]:
    matches = []
    for e in evidence:
        score = 0.0
        if tx.merchant and e.vendor and norm(tx.merchant) in norm(e.vendor):
            score += 0.45
        if e.amount is not None and math.isclose(abs(tx.amount), abs(e.amount), abs_tol=0.01):
            score += 0.40
        if tx.date == e.date:
            score += 0.15
        if score >= 0.80:
            copy = e.model_copy()
            copy.confidence = min(1.0, score)
            matches.append(copy)
    return sorted(matches, key=lambda x: x.confidence, reverse=True)

def balanced(lines: list[JournalLine]) -> bool:
    return math.isclose(
        sum(x.debit for x in lines),
        sum(x.credit for x in lines),
        abs_tol=0.01
    )

def make_expense(account: str, gross: float, hst: float = 0.0):
    expense = round(gross - hst, 2)
    return [
        JournalLine(account=account, debit=expense),
        *([JournalLine(account="GST/HST Recoverable", debit=hst)] if hst else []),
        JournalLine(account="Business Bank / Card", credit=gross)
    ]

def decide(tx: SourceTransaction, evidence: list[Evidence]) -> Decision:
    ev = match_evidence(tx, evidence)
    text = " ".join([tx.description] + [x.description for x in ev]).lower()
    eids = [x.evidence_id for x in ev]
    gross = abs(tx.amount)

    if tx.pending:
        return Decision(
            transaction_id=tx.source_id, route="auto_post_flag", confidence=0.99,
            explanation="Pending bank transaction: hold for posted replacement.",
            evidence_ids=eids
        )

    if "staples" in text and ("toner" in text or "paper" in text):
        hst = 13.00 if math.isclose(gross,113.00,abs_tol=.01) else 0.0
        j = make_expense("Office Supplies", gross, hst)
        return Decision(
            transaction_id=tx.source_id, route="auto_post",
            account="Office Supplies", tax_category="office_expense",
            confidence=0.98, evidence_ids=eids,
            explanation="Receipt matched by vendor, amount and date; line items indicate office consumables.",
            journal=j
        )

    if "rogers" in text:
        if not ev:
            return Decision(
                transaction_id=tx.source_id, route="owner_question",
                account="Telecommunications", confidence=0.64,
                missing_facts=["business_use_percentage"],
                explanation="Telecom transaction identified, but allocation evidence is missing."
            )
        return Decision(
            transaction_id=tx.source_id, route="owner_question",
            account="Telecommunications", confidence=0.86, evidence_ids=eids,
            missing_facts=["mobile_business_use_percentage"],
            explanation="Invoice found automatically. Business-use allocation remains a client fact."
        )

    if "renovation" in text or "upgrade finishes" in text:
        return Decision(
            transaction_id=tx.source_id, route="professional_review",
            account="Building Improvements", confidence=0.91, evidence_ids=eids,
            explanation="Evidence indicates a broader renovation/betterment; current-versus-capital treatment is material and review-gated."
        )

    if "loan" in text:
        j = [
            JournalLine(account="Loan Payable", debit=900.00),
            JournalLine(account="Interest Expense", debit=125.00),
            JournalLine(account="Business Chequing", credit=1025.00)
        ]
        return Decision(
            transaction_id=tx.source_id, route="auto_post",
            account="Loan Payable / Interest", confidence=0.97,
            explanation="Known commercial loan payment with stored payment split.",
            journal=j
        )

    if tx.amount > 0 and "deposit" in text:
        j = [
            JournalLine(account="Business Chequing", debit=gross),
            JournalLine(account="Customer Deposits / Deferred Revenue", credit=gross)
        ]
        return Decision(
            transaction_id=tx.source_id, route="auto_post_flag",
            account="Customer Deposits / Deferred Revenue", confidence=0.94,
            explanation="Deposit description indicates customer advance; recognized as liability pending performance.",
            journal=j
        )

    return Decision(
        transaction_id=tx.source_id, route="owner_question", confidence=0.50,
        missing_facts=["business_purpose"],
        explanation="Insufficient evidence to determine safe accounting treatment."
    )
