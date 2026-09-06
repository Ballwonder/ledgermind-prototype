
from collections import Counter,defaultdict
from sqlalchemy import select
from .data_model import SessionLocal,ProcessingRun,TransactionProcessingResult,Transaction,Evidence
from .autonomy_router import decide_autonomy
from .transaction_enrichment import enrich_transaction

def diagnose_latest_run(household_id:int):
    with SessionLocal() as s:
        run=s.scalar(select(ProcessingRun).where(
            ProcessingRun.household_id==household_id
        ).order_by(ProcessingRun.id.desc()))
        if not run:
            return {"status":"not_run","exceptions":[],"bottlenecks":[]}
        rows=s.scalars(select(TransactionProcessingResult).where(
            TransactionProcessingResult.run_id==run.id,
            TransactionProcessingResult.route!="AUTO_FINISH"
        )).all()

    exceptions=[]
    buckets=Counter()
    for row in rows:
        enrichment=enrich_transaction(household_id,row.transaction_id,persist=False)
        decision=decide_autonomy(household_id,row.transaction_id,enrichment.facts)
        with SessionLocal() as s:
            tx=s.get(Transaction,row.transaction_id)
            ev=s.scalars(select(Evidence).where(Evidence.transaction_id==row.transaction_id)).all()
            merchant=(tx.merchant_normalized or tx.merchant_raw) if tx else None
            amount=tx.amount if tx else None

        cause=decision.weakest_material_factor or "unknown"
        if decision.route=="PROFESSIONAL_REVIEW":
            cause="professional_judgment"
        elif cause=="profile_assignment":
            cause="profile_uncertainty"
        elif cause in {"evidence_quality","evidence_sufficiency"}:
            cause="missing_or_weak_evidence"
        elif cause=="missing_owner_fact":
            cause="missing_owner_fact"
        elif cause=="accounting":
            cause="accounting_confidence"
        buckets[cause]+=1

        exceptions.append({
            "transaction_id":row.transaction_id,
            "merchant":merchant,"amount":amount,
            "route":decision.route,
            "primary_cause":cause,
            "evidence_count":len(ev),
            "profile_confidence":decision.confidence.get("profile",0),
            "evidence_confidence":decision.confidence.get("evidence",0),
            "accounting_confidence":decision.confidence.get("accounting",0),
            "question":decision.owner_question,
            "review_reason":decision.professional_review_reason,
            "enrichment_reasons":enrichment.reasons
        })

    total=len(exceptions)
    bottlenecks=[
        {"cause":k,"count":v,"pct":round(v/total*100,1) if total else 0}
        for k,v in buckets.most_common()
    ]
    return {
        "run_id":run.id,"exception_count":total,
        "bottlenecks":bottlenecks,
        "exceptions":exceptions
    }
