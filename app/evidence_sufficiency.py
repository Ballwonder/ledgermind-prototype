
from __future__ import annotations
from dataclasses import dataclass, asdict
from sqlalchemy import select
from .data_model import SessionLocal, Transaction, Evidence, FinancialProfile
from .document_validator import latest_validation

@dataclass
class EvidenceSufficiency:
    transaction_id:int
    purpose:str
    status:str
    sufficient_for_autonomy:bool
    confidence:float
    evidence_types:list[str]
    missing:list[str]
    reasons:list[str]
    tax_documentation_required:bool
    itc_documentation_required:bool

def evaluate_evidence(household_id:int, transaction_id:int, treatment:str|None=None, facts:dict|None=None):
    facts=facts or {}
    with SessionLocal() as s:
        tx=s.get(Transaction,transaction_id)
        if not tx or tx.household_id!=household_id: raise KeyError("transaction")
        profile=s.get(FinancialProfile,tx.profile_id) if tx.profile_id else None
        evidence=s.scalars(select(Evidence).where(Evidence.transaction_id==tx.id)).all()

        ptype=profile.profile_type if profile else None
        bank_feed=bool(tx.provider_transaction_id)
        docs=[e for e in evidence]
        types=sorted(set([e.evidence_type for e in docs if e.evidence_type]))
        desc=((tx.description or "")+" "+(tx.category or "")+" "+(tx.merchant_normalized or tx.merchant_raw or "")).lower()
        reasons=[]; missing=[]
        tax_doc=False; itc_doc=False

        # Personal-finance classification is not a tax deduction claim.
        if ptype=="personal":
            if bank_feed:
                return EvidenceSufficiency(tx.id,"personal_finance_classification","sufficient",True,.97,
                    ["bank_feed"]+types,[],["Linked financial-account transaction is sufficient for ordinary personal categorization."],
                    False,False)
            return EvidenceSufficiency(tx.id,"personal_finance_classification","insufficient",False,.45,
                    types,["transaction source"],["No reliable transaction source is available."],False,False)

        # Specialized non-expense cash movements: the account transaction can establish the movement,
        # while the accounting engine still decides whether treatment itself is safe.
        specialized=any(k in desc for k in ["transfer","mortgage payment","loan payment","payroll deposit","client payment"])
        if specialized and bank_feed:
            purpose="cash_movement_or_income_support"
            conf=.90 if tx.merchant_normalized or tx.merchant_raw else .82
            reasons.append("Linked account record supports the occurrence, amount and date of the cash movement.")
            if tx.amount>0:
                reasons.append("Income/source support may still need stronger documentation where tax reporting requires it.")
            return EvidenceSufficiency(tx.id,purpose,"sufficient" if conf>=.90 else "partial",conf>=.90,conf,
                ["bank_feed"]+types,[] if conf>=.90 else ["source detail"],reasons,tx.amount>0,False)

        # Business/rental/corporate spending: require supporting business records for autonomous tax/bookkeeping completion.
        if tx.amount < 0 and ptype in {"sole_proprietor","rental","corporation"}:
            tax_doc=True
            itc_doc=bool(profile.gst_hst_registered)
            if not docs:
                missing.append("receipt/invoice/contract/other supporting business record")
                if itc_doc:
                    missing.append("GST/HST documentary support before any ITC claim")
                reasons.append("The bank/card transaction proves payment but does not by itself fully support the business expense/tax claim.")
                return EvidenceSufficiency(tx.id,"business_expense_support","insufficient",False,.55,
                    ["bank_feed"] if bank_feed else [],missing,reasons,tax_doc,itc_doc)

            # Generic document completeness floor. Detailed statutory field validation is a later layer.
            quality=.55
            if any(e.amount is not None for e in docs): quality+=.15
            if any(e.evidence_date is not None for e in docs): quality+=.10
            if any(bool(e.subject or e.excerpt) for e in docs): quality+=.15
            if any(bool(e.merchant) for e in docs): quality+=.05
            quality=min(1.0,quality)
            if quality>=.90:
                reasons.append("Supporting business document is linked with amount/date/context.")
                if itc_doc:
                    validation=latest_validation(household_id,tx.id)
                    if not validation:
                        reasons.append("GST/HST registration is active, but the linked document has not yet passed the ITC field validator.")
                        return EvidenceSufficiency(tx.id,"business_expense_support","partial",False,.82,
                            types,["validated GST/HST document fields before autonomous ITC treatment"],reasons,tax_doc,itc_doc)
                    if not validation.valid_for_itc_support:
                        reasons.append("The document failed the deterministic ITC information check.")
                        return EvidenceSufficiency(tx.id,"business_expense_support","partial",False,.80,
                            types,["ITC fields: "+", ".join(validation.missing_fields)],reasons,tax_doc,itc_doc)
                    reasons.append("The linked document passed the deterministic ITC information check.")
                return EvidenceSufficiency(tx.id,"business_expense_support","sufficient",True,round(quality,3),
                    types,[],reasons,tax_doc,itc_doc)
            missing.append("more complete supporting document fields")
            return EvidenceSufficiency(tx.id,"business_expense_support","partial",False,round(quality,3),
                types,missing,["Supporting document exists but is incomplete for autonomous completion."],tax_doc,itc_doc)

        # Business income: bank record plus identifiable payer/source can support bookkeeping occurrence;
        # tax/audit support should still be retained.
        if tx.amount > 0 and ptype in {"sole_proprietor","rental","corporation"}:
            tax_doc=True
            if bank_feed and (tx.merchant_normalized or tx.merchant_raw):
                return EvidenceSufficiency(tx.id,"business_income_support","sufficient",True,.92,
                    ["bank_feed"]+types,[],["Account record identifies date, amount and source for bookkeeping; supporting source documents should be retained."],
                    True,False)
            return EvidenceSufficiency(tx.id,"business_income_support","partial",False,.65,types,
                ["identifiable income source"],["Income source is not sufficiently identified."],True,False)

        # Conservative fallback.
        if docs:
            return EvidenceSufficiency(tx.id,"general_support","sufficient",True,.90,types,[],
                ["Supporting evidence is linked."],False,False)
        if bank_feed:
            return EvidenceSufficiency(tx.id,"general_support","partial",False,.70,["bank_feed"],
                ["purpose-specific support"],["Transaction exists, but purpose-specific evidence requirements are unresolved."],False,False)
        return EvidenceSufficiency(tx.id,"general_support","insufficient",False,.35,[],
            ["transaction support"],["No supporting evidence is available."],False,False)

def payload(x): return asdict(x)
