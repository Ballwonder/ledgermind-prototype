
from __future__ import annotations
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional
from sqlalchemy import select
from .data_model import (
    SessionLocal, Account, Transaction, MerchantMemory, Evidence,
    RecurringObligation, Insight, AuditEvent
)

PFC_MAP = {
    "INCOME": "Income",
    "TRANSFER_IN": "Transfers",
    "TRANSFER_OUT": "Transfers",
    "LOAN_PAYMENTS": "Debt Payments",
    "BANK_FEES": "Fees",
    "ENTERTAINMENT": "Entertainment",
    "FOOD_AND_DRINK": "Restaurants",
    "GENERAL_MERCHANDISE": "Shopping",
    "HOME_IMPROVEMENT": "Home",
    "MEDICAL": "Health",
    "PERSONAL_CARE": "Personal Care",
    "GENERAL_SERVICES": "Services",
    "GOVERNMENT_AND_NON_PROFIT": "Government / Charity",
    "TRANSPORTATION": "Transportation",
    "TRAVEL": "Travel",
    "RENT_AND_UTILITIES": "Utilities",
}

MERCHANT_RULES = [
    (r"\b(hydro one|hydro|enbridge|utility|rogers|bell)\b", "Utilities"),
    (r"\b(food basics|metro|loblaws|no frills|costco|grocery)\b", "Groceries"),
    (r"\b(netflix|spotify|disney|prime video)\b", "Subscriptions"),
    (r"\b(shell|esso|petro[- ]?can|ultramar)\b", "Transportation"),
    (r"\b(restaurant|cafe|coffee|pizza|doordash|uber eats)\b", "Restaurants"),
    (r"\b(mortgage)\b", "Housing"),
    (r"\b(insurance)\b", "Insurance"),
    (r"\b(payroll|salary|pay deposit)\b", "Income"),
    (r"\b(interac transfer|e-transfer|transfer)\b", "Transfers"),
]

def normalize_merchant(raw: str | None) -> str:
    s=(raw or "").strip()
    s=re.sub(r"\s+#?\d{3,}\b","",s)
    s=re.sub(r"\s{2,}"," ",s)
    return s.title()

def provider_category(tx: dict) -> Optional[str]:
    pfc=tx.get("personal_finance_category") or {}
    primary=(pfc.get("primary") or "").upper()
    detailed=(pfc.get("detailed") or "").upper()
    if "GROCER" in detailed: return "Groceries"
    if "RESTAURANT" in detailed or "FAST_FOOD" in detailed or "COFFEE" in detailed: return "Restaurants"
    if "INTERNET" in detailed or "TELEPHONE" in detailed or "UTILIT" in detailed: return "Utilities"
    if "RENT" in detailed or "MORTGAGE" in detailed: return "Housing"
    if "INSURANCE" in detailed: return "Insurance"
    if "SUBSCRIPTION" in detailed: return "Subscriptions"
    return PFC_MAP.get(primary)

def deterministic_category(merchant: str, description: str) -> Optional[str]:
    text=f"{merchant} {description}".lower()
    for pattern, cat in MERCHANT_RULES:
        if re.search(pattern,text,re.I):
            return cat
    return None

def choose_category(household_id:int, merchant:str, description:str, provider_cat:Optional[str]):
    with SessionLocal() as s:
        mem=s.scalar(select(MerchantMemory).where(
            MerchantMemory.household_id==household_id,
            MerchantMemory.merchant_normalized==merchant
        ))
        rule=deterministic_category(merchant,description)
        # User-confirmed memory can guide ambiguous provider output, but deterministic
        # transaction-specific rules remain visible and confidence is not forced to 1.
        if mem and (not rule or rule==mem.preferred_category):
            return mem.preferred_category, min(.99,max(.93,mem.confidence)), "merchant_memory"
        if rule:
            return rule,.96,"deterministic_rule"
        if provider_cat:
            return provider_cat,.84,"provider_pfc_v2"
        return "Other",.45,"unresolved"

def normalize_plaid_transaction(household_id:int, raw:dict):
    merchant=normalize_merchant(raw.get("merchant_name") or raw.get("name"))
    desc=raw.get("name") or merchant or "Transaction"
    pcat=provider_category(raw)
    category,confidence,source=choose_category(household_id,merchant,desc,pcat)
    # Plaid transaction amount convention is outflow-positive for most Transactions data.
    amount=-float(raw.get("amount",0))
    excluded=category=="Transfers"
    return {
        "provider":"plaid",
        "provider_transaction_id":raw["transaction_id"],
        "provider_account_id":raw.get("account_id"),
        "tx_date":date.fromisoformat(raw["date"]),
        "merchant_raw":raw.get("merchant_name") or raw.get("name"),
        "merchant_normalized":merchant,
        "description":desc,
        "amount":amount,
        "category":category,
        "category_confidence":confidence,
        "category_source":source,
        "pending":bool(raw.get("pending",False)),
        "excluded_from_spending":excluded,
        "provider_category":pcat,
    }

def upsert_normalized_transaction(household_id:int, norm:dict):
    with SessionLocal() as s:
        account=None
        if norm.get("provider_account_id"):
            account=s.scalar(select(Account).where(
                Account.provider=="plaid",
                Account.provider_account_id==norm["provider_account_id"]
            ))
        tx=s.scalar(select(Transaction).where(
            Transaction.provider==norm["provider"],
            Transaction.provider_transaction_id==norm["provider_transaction_id"]
        ))
        if not tx:
            tx=Transaction(
                household_id=household_id,
                account_id=account.id if account else None,
                provider=norm["provider"],
                provider_transaction_id=norm["provider_transaction_id"],
                tx_date=norm["tx_date"],
                merchant_raw=norm["merchant_raw"],
                merchant_normalized=norm["merchant_normalized"],
                description=norm["description"],
                amount=norm["amount"],
                category=norm["category"],
                category_confidence=norm["category_confidence"],
                pending=norm["pending"],
                excluded_from_spending=norm["excluded_from_spending"]
            )
            s.add(tx); s.flush()
            event="transaction_ingested"
        else:
            tx.tx_date=norm["tx_date"]
            tx.merchant_raw=norm["merchant_raw"]
            tx.merchant_normalized=norm["merchant_normalized"]
            tx.description=norm["description"]
            tx.amount=norm["amount"]
            tx.pending=norm["pending"]
            tx.excluded_from_spending=norm["excluded_from_spending"]
            # Preserve a user-confirmed category if it is stronger than incoming provider classification.
            if tx.category_confidence < .99:
                tx.category=norm["category"]
                tx.category_confidence=norm["category_confidence"]
            event="transaction_updated"
        s.add(AuditEvent(
            household_id=household_id,event_type=event,entity_type="transaction",
            entity_id=str(tx.id),detail_json=json_dumps_safe({
                "category_source":norm["category_source"],
                "provider_category":norm.get("provider_category")
            })
        ))
        s.commit()
        return tx.id

def json_dumps_safe(obj):
    import json
    return json.dumps(obj,separators=(",",":"),default=str)

def evidence_match_score(tx:Transaction, ev:Evidence)->float:
    score=0.0
    tm=(tx.merchant_normalized or "").lower()
    em=(ev.merchant or "").lower()
    if tm and em and (tm in em or em in tm): score+=.45
    if ev.amount is not None and abs(abs(tx.amount)-abs(ev.amount))<=.02: score+=.35
    if ev.evidence_date and abs((tx.tx_date-ev.evidence_date).days)<=3: score+=.15
    if ev.subject and tm and tm.split()[0] in ev.subject.lower(): score+=.05
    return round(min(score,1.0),2)

def match_unlinked_evidence(household_id:int):
    matches=[]
    with SessionLocal() as s:
        txs=s.scalars(select(Transaction).where(Transaction.household_id==household_id)).all()
        evidence=s.scalars(select(Evidence).where(
            Evidence.household_id==household_id,
            Evidence.transaction_id.is_(None)
        )).all()
        for ev in evidence:
            scored=[(evidence_match_score(tx,ev),tx) for tx in txs]
            scored.sort(key=lambda x:x[0],reverse=True)
            if scored and scored[0][0]>=.80:
                ev.match_score=scored[0][0]
                ev.transaction_id=scored[0][1].id
                matches.append({"evidence_id":ev.id,"transaction_id":scored[0][1].id,"score":scored[0][0]})
        s.commit()
    return matches

def detect_anomalies(household_id:int):
    with SessionLocal() as s:
        txs=s.scalars(select(Transaction).where(
            Transaction.household_id==household_id,
            Transaction.amount<0,
            Transaction.excluded_from_spending==False
        )).all()
        amounts=sorted(abs(t.amount) for t in txs)
        median=amounts[len(amounts)//2] if amounts else 0
        created=[]
        for t in txs:
            reasons=[]
            if abs(t.amount)>max(250,median*3): reasons.append("large_vs_typical")
            if t.category_confidence<.75: reasons.append("low_category_confidence")
            if reasons:
                period=t.tx_date.strftime("%Y-%m")
                title=f"Review {t.merchant_normalized or t.description}"
                exists=s.scalar(select(Insight).where(
                    Insight.household_id==household_id,
                    Insight.insight_type=="transaction_review",
                    Insight.title==title,
                    Insight.period_key==period
                ))
                if not exists:
                    ins=Insight(
                        household_id=household_id,insight_type="transaction_review",
                        title=title,
                        body=f"${abs(t.amount):,.2f} · {', '.join(reasons)}",
                        severity="review",period_key=period
                    )
                    s.add(ins); created.append(title)
        s.commit()
        return {"median_outflow":median,"created":created}

def upsert_recurring_streams(household_id:int, streams:list[dict]):
    count=0
    with SessionLocal() as s:
        for st in streams:
            merchant=normalize_merchant(st.get("merchant_name") or st.get("description"))
            category=provider_category({"personal_finance_category":st.get("personal_finance_category")})
            last_amount=(st.get("last_amount") or {}).get("amount")
            if last_amount is None:
                last_amount=st.get("last_amount",0)
            cadence=(st.get("frequency") or "monthly").lower()
            existing=s.scalar(select(RecurringObligation).where(
                RecurringObligation.household_id==household_id,
                RecurringObligation.merchant==merchant,
                RecurringObligation.source=="plaid_recurring"
            ))
            next_date=st.get("predicted_next_date")
            nd=date.fromisoformat(next_date) if next_date else None
            if existing:
                existing.category=category or existing.category
                existing.amount=abs(float(last_amount or existing.amount))
                existing.cadence=cadence
                existing.next_expected_date=nd
                existing.confidence=.9
            else:
                s.add(RecurringObligation(
                    household_id=household_id,merchant=merchant,
                    category=category or "Other",amount=abs(float(last_amount or 0)),
                    cadence=cadence,next_expected_date=nd,
                    confidence=.9,source="plaid_recurring"
                ))
            count+=1
        s.commit()
    return count
