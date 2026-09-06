
from __future__ import annotations
import json
from datetime import datetime
from sqlalchemy import select, delete
from .data_model import (
    SessionLocal, Transaction, FinancialProfile, Evidence, ProcessingRun,
    TransactionProcessingResult
)
from .autonomy_router import decide_autonomy
from .streamlining_engine import recurring_match
from .transaction_enrichment import enrich_transaction
from .evidence_retrieval import retrieve_for_transaction
from .journal_engine_v027 import build_journal,payload as journal_payload
from .journal_gated_autonomy import decide_with_journal

def _journal_for(tx, profile, treatment, recurring=None):
    amt=abs(float(tx.amount))
    if tx.amount < 0:
        # Expense/payment template
        expense_account=(recurring or {}).get("category") or tx.category or "Uncategorized Expense"
        return [
            {"account":expense_account,"debit":round(amt,2),"credit":0.0},
            {"account":"Cash / Credit Card","debit":0.0,"credit":round(amt,2)},
        ]
    else:
        revenue_account=tx.category or "Revenue"
        return [
            {"account":"Cash / Bank","debit":round(amt,2),"credit":0.0},
            {"account":revenue_account,"debit":0.0,"credit":round(amt,2)},
        ]

def _balanced(journal):
    d=round(sum(x["debit"] for x in journal),2)
    c=round(sum(x["credit"] for x in journal),2)
    return d==c

def _reconciled(tx, evidence):
    # Prototype: exact supporting-doc amount match or provider transaction ID exists.
    a=abs(float(tx.amount))
    for ev in evidence:
        if ev.amount is not None and abs(abs(float(ev.amount))-a) < .01:
            return True
    return bool(tx.provider_transaction_id)

def _facts_from_transaction(tx, recurring=None):
    facts={
        "item_type": None,
        "business_use_pct": None,
        "personal_component_present": False,
        "lasting_benefit": False,
        "restores_original_condition": False,
        "improves_beyond_original_condition": False,
    }
    desc=((tx.description or "")+" "+(tx.category or "")).lower()
    if any(k in desc for k in ["office supplies","paper","toner","stationery"]):
        facts["item_type"]="consumable"
    elif any(k in desc for k in ["repair","plumbing","shingle","maintenance"]):
        facts["item_type"]="repair"
    elif any(k in desc for k in ["renovation","upgrade","improvement"]):
        facts["item_type"]="repair"
        facts["lasting_benefit"]=True
        facts["improves_beyond_original_condition"]=True
    elif any(k in desc for k in ["mobile","internet","phone"]):
        facts["item_type"]="service"

    if recurring:
        if recurring.get("business_use_pct") is not None:
            facts["business_use_pct"]=recurring["business_use_pct"]
            if recurring["business_use_pct"] < 1:
                facts["personal_component_present"]=True
    return facts

def process_household(household_id:int, reset_results:bool=False):
    with SessionLocal() as s:
        if reset_results:
            s.execute(delete(TransactionProcessingResult))
            s.execute(delete(ProcessingRun))
            s.commit()

        run=ProcessingRun(household_id=household_id,status="running")
        s.add(run);s.commit();s.refresh(run)

        txs=s.scalars(select(Transaction).where(Transaction.household_id==household_id).order_by(Transaction.tx_date)).all()
        counters={"processed":0,"auto":0,"owner":0,"pro":0,"reconciled":0}
        for tx in txs:
            enrichment=enrich_transaction(household_id,tx.id,persist=True)
            # Exhaust mapped/source evidence before deciding whether the owner must be asked.
            try:
                retrieve_for_transaction(household_id,tx.id)
            except Exception:
                # Retrieval failure must not force an unsafe finish; autonomy remains conservative.
                pass
            # Refresh after enrichment may have persisted profile/category.
            s.refresh(tx)
            recurring=recurring_match(household_id,tx)
            recurring_best=recurring[0] if recurring else None
            facts=enrichment.facts

            d=decide_autonomy(household_id,tx.id,facts)
            route=d.route
            treatment=d.proposed_treatment
            journal=None
            balanced=False

            if route=="AUTO_FINISH":
                profile=s.get(FinancialProfile,d.proposed_profile_id)
                journal=_journal_for(tx,profile,treatment,recurring_best)
                balanced=_balanced(journal)
                if not balanced:
                    route="PROFESSIONAL_REVIEW"

            evidence=s.scalars(select(Evidence).where(Evidence.transaction_id==tx.id)).all()
            rec=_reconciled(tx,evidence) if route=="AUTO_FINISH" and balanced else False

            exception=None
            if route=="OWNER_QUESTION":
                exception=d.owner_question or "Owner input required"
            elif route=="PROFESSIONAL_REVIEW":
                exception=d.professional_review_reason or "Professional review required"

            row=TransactionProcessingResult(
                run_id=run.id,transaction_id=tx.id,route=route,
                profile_id=d.proposed_profile_id,treatment=treatment,
                journal_json=json.dumps(journal) if journal else None,
                journal_balanced=balanced,reconciled=rec,
                exception_reason=exception
            )
            s.add(row)
            counters["processed"]+=1
            counters["auto"]+=int(route=="AUTO_FINISH")
            counters["owner"]+=int(route=="OWNER_QUESTION")
            counters["pro"]+=int(route=="PROFESSIONAL_REVIEW")
            counters["reconciled"]+=int(rec)

        unresolved=counters["owner"]+counters["pro"]
        close_ready=(unresolved==0 and counters["processed"]>0 and counters["reconciled"]==counters["auto"])
        run.completed_at=datetime.utcnow()
        run.status="completed"
        run.processed_count=counters["processed"]
        run.auto_finished_count=counters["auto"]
        run.owner_question_count=counters["owner"]
        run.professional_review_count=counters["pro"]
        run.reconciled_count=counters["reconciled"]
        run.close_ready=close_ready
        s.commit();s.refresh(run)

        return {
            "run_id":run.id,
            "processed":run.processed_count,
            "auto_finished":run.auto_finished_count,
            "owner_questions":run.owner_question_count,
            "professional_reviews":run.professional_review_count,
            "reconciled":run.reconciled_count,
            "close_ready":run.close_ready,
            "completion_pct": round((run.auto_finished_count/run.processed_count*100),1) if run.processed_count else 0,
            "exception_count": unresolved
        }

def close_readiness(household_id:int):
    with SessionLocal() as s:
        run=s.scalar(select(ProcessingRun).where(
            ProcessingRun.household_id==household_id
        ).order_by(ProcessingRun.id.desc()))
        if not run:
            return {"status":"not_run","close_ready":False}
        return {
            "run_id":run.id,"status":run.status,"processed":run.processed_count,
            "auto_finished":run.auto_finished_count,
            "owner_questions":run.owner_question_count,
            "professional_reviews":run.professional_review_count,
            "reconciled":run.reconciled_count,
            "close_ready":run.close_ready,
            "completion_pct": round((run.auto_finished_count/run.processed_count*100),1) if run.processed_count else 0
        }

def exception_rows(household_id:int):
    with SessionLocal() as s:
        run=s.scalar(select(ProcessingRun).where(
            ProcessingRun.household_id==household_id
        ).order_by(ProcessingRun.id.desc()))
        if not run: return []
        rows=s.scalars(select(TransactionProcessingResult).where(
            TransactionProcessingResult.run_id==run.id,
            TransactionProcessingResult.route!="AUTO_FINISH"
        )).all()
        out=[]
        for r in rows:
            tx=s.get(Transaction,r.transaction_id)
            out.append({
                "transaction_id":r.transaction_id,
                "merchant":tx.merchant_normalized or tx.merchant_raw if tx else None,
                "amount":tx.amount if tx else None,
                "route":r.route,
                "reason":r.exception_reason
            })
        return out
