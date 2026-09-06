
from __future__ import annotations
import json
from datetime import date
from sqlalchemy import select
from .data_model import SessionLocal,BankStatement,StatementLine,StatementMatch,Transaction,ReconciliationAction

def _norm(v): return " ".join((v or "").lower().split())

def _bank_only_action(line):
    text=_norm(line.description)
    amt=float(line.amount)
    if amt < 0 and any(k in text for k in ["bank fee","service charge","monthly fee","nsf fee"]):
        return {
            "action_type":"PROPOSE_MISSING_LEDGER_ENTRY",
            "confidence":0.97,
            "payload":{
                "transaction_type":"expense",
                "amount":amt,
                "description":line.description,
                "expense_account":"Bank Charges",
                "source_account":"Cash/Bank"
            },
            "reason":"Statement-only bank fee has a deterministic bookkeeping treatment."
        }
    if amt > 0 and any(k in text for k in ["interest","rebate","refund"]):
        return {
            "action_type":"PROPOSE_MISSING_LEDGER_ENTRY",
            "confidence":0.90,
            "payload":{
                "transaction_type":"revenue",
                "amount":amt,
                "description":line.description,
                "revenue_account":"Other Income",
                "source_account":"Cash/Bank"
            },
            "reason":"Statement-only inflow has a plausible simple income/refund treatment."
        }
    return {
        "action_type":"OWNER_REVIEW",
        "confidence":0.45,
        "payload":{"statement_line_id":line.id,"amount":amt,"description":line.description},
        "reason":"Statement-only item is not safe to book automatically from bank description alone."
    }

def _book_only_action(tx,period_end):
    desc=_norm(tx.description)
    age=(period_end-tx.tx_date).days
    if tx.amount < 0 and any(k in desc for k in ["cheque","check"]) and age <= 30:
        return {
            "action_type":"MARK_OUTSTANDING",
            "confidence":0.94,
            "payload":{"transaction_id":tx.id,"classification":"outstanding_cheque"},
            "reason":"Recent cheque in books but absent from statement is a normal timing difference candidate."
        }
    if tx.amount < 0 and any(k in desc for k in ["bill payment","payment"]) and age <= 7:
        return {
            "action_type":"MARK_OUTSTANDING",
            "confidence":0.86,
            "payload":{"transaction_id":tx.id,"classification":"timing_difference"},
            "reason":"Recent payment may not have cleared by statement date."
        }
    return {
        "action_type":"INVESTIGATE_BOOK_ONLY",
        "confidence":0.55,
        "payload":{"transaction_id":tx.id,"age_days":age},
        "reason":"Ledger-only item is not clearly a legitimate timing difference."
    }

def propose_actions(hh:int,statement_id:int,persist=True):
    with SessionLocal() as s:
        st=s.get(BankStatement,statement_id)
        if not st or st.household_id!=hh: raise KeyError("statement")
        matches=s.scalars(select(StatementMatch).where(
            StatementMatch.household_id==hh,
            StatementMatch.statement_id==statement_id
        ).order_by(StatementMatch.id)).all()

        proposals=[]
        for m in matches:
            if m.status=="BANK_ONLY" and m.statement_line_id:
                line=s.get(StatementLine,m.statement_line_id)
                a=_bank_only_action(line)
                proposals.append({"statement_line_id":line.id,"transaction_id":None,**a})
            elif m.status=="BOOK_ONLY" and m.transaction_id:
                tx=s.get(Transaction,m.transaction_id)
                a=_book_only_action(tx,st.period_end)
                proposals.append({"statement_line_id":None,"transaction_id":tx.id,**a})
            elif m.status=="AMBIGUOUS":
                proposals.append({
                    "statement_line_id":m.statement_line_id,"transaction_id":m.transaction_id,
                    "action_type":"CONFIRM_MATCH","confidence":m.score,
                    "payload":{"statement_line_id":m.statement_line_id,"transaction_id":m.transaction_id},
                    "reason":"Candidate match exists but autonomous matching margin was insufficient."
                })
            elif m.status=="DUPLICATE_STATEMENT_LINE":
                proposals.append({
                    "statement_line_id":m.statement_line_id,"transaction_id":None,
                    "action_type":"REVIEW_DUPLICATE","confidence":0.98,
                    "payload":{"statement_line_id":m.statement_line_id},
                    "reason":"Duplicate bank statement line should be resolved before close."
                })

        if persist:
            s.query(ReconciliationAction).filter(ReconciliationAction.statement_id==statement_id).delete()
            for p in proposals:
                s.add(ReconciliationAction(
                    household_id=hh,statement_id=statement_id,
                    statement_line_id=p["statement_line_id"],transaction_id=p["transaction_id"],
                    action_type=p["action_type"],status="PROPOSED",confidence=p["confidence"],
                    proposed_payload_json=json.dumps(p["payload"],default=str),reason=p["reason"]))
            s.commit()
        return proposals

def apply_safe_actions(hh:int,statement_id:int):
    proposals=propose_actions(hh,statement_id,persist=True)
    applied=[]
    with SessionLocal() as s:
        st=s.get(BankStatement,statement_id)
        for p in proposals:
            if p["action_type"]=="PROPOSE_MISSING_LEDGER_ENTRY" and p["confidence"]>=0.95:
                payload=p["payload"]
                existing=s.scalar(select(Transaction).where(
                    Transaction.household_id==hh,
                    Transaction.provider=="reconciliation_auto",
                    Transaction.provider_transaction_id==f"stmt:{statement_id}:line:{p['statement_line_id']}"
                ))
                if not existing:
                    line=s.get(StatementLine,p["statement_line_id"])
                    tx=Transaction(
                        household_id=hh,provider="reconciliation_auto",
                        provider_transaction_id=f"stmt:{statement_id}:line:{line.id}",
                        tx_date=line.line_date,
                        merchant_raw=line.description,merchant_normalized=line.description,
                        description=line.description,amount=line.amount,
                        category=payload.get("expense_account") or payload.get("revenue_account") or "Other",
                        category_confidence=p["confidence"]
                    )
                    s.add(tx);s.flush()
                    applied.append({"action_type":"CREATE_LEDGER_TRANSACTION",
                                    "statement_line_id":line.id,"transaction_id":tx.id})
            elif p["action_type"]=="MARK_OUTSTANDING" and p["confidence"]>=0.90:
                applied.append({"action_type":"MARK_OUTSTANDING",
                                "transaction_id":p["transaction_id"],
                                "classification":p["payload"]["classification"]})
        s.commit()
    return {"proposals":proposals,"applied":applied}
