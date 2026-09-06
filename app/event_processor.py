
from __future__ import annotations
import json
from sqlalchemy import select
from .data_model import SessionLocal,IngestEvent,EventProcessingRecord,Transaction,SourceDocument
from .transaction_enrichment import enrich_transaction
from .evidence_retrieval import retrieve_for_transaction
from .autonomy_router import decide_autonomy
from .journal_gated_autonomy import decide_with_journal
from .document_extraction import ingest_document

def _persist(ingest_event_id,household_id,action_type,detail,transaction_id=None,source_document_id=None,route=None,status="completed"):
    with SessionLocal() as s:
        rec=EventProcessingRecord(
            ingest_event_id=ingest_event_id,household_id=household_id,
            action_type=action_type,transaction_id=transaction_id,
            source_document_id=source_document_id,route=route,status=status,
            detail_json=json.dumps(detail,default=str)
        )
        s.add(rec);s.commit();s.refresh(rec)
        return rec.id

def process_ingest_event(household_id:int,ingest_event_id:int):
    with SessionLocal() as s:
        ev=s.get(IngestEvent,ingest_event_id)
        if not ev or ev.household_id!=household_id:
            raise KeyError("ingest_event")
        existing=s.scalar(select(EventProcessingRecord).where(
            EventProcessingRecord.ingest_event_id==ingest_event_id,
            EventProcessingRecord.action_type=="primary"
        ).order_by(EventProcessingRecord.id.desc()))
        if existing:
            return {
                "duplicate_processing":True,
                "record_id":existing.id,
                "route":existing.route,
                "transaction_id":existing.transaction_id,
                "source_document_id":existing.source_document_id,
                "detail":json.loads(existing.detail_json)
            }
        txid=ev.linked_transaction_id
        docid=ev.linked_source_document_id
        connector=ev.connector_type

    # Transaction events: enrich -> search evidence -> decide autonomy.
    if txid:
        enrichment=enrich_transaction(household_id,txid,persist=True)
        retrieval=retrieve_for_transaction(household_id,txid)
        with SessionLocal() as s:
            tx_obj=s.get(Transaction,txid)
        decision=decide_with_journal(household_id,tx_obj,enrichment.facts)
        detail={
            "path":"transaction",
            "enrichment":{"changed":enrichment.changed,"reasons":enrichment.reasons},
            "retrieval":{
                "status":retrieval.status,
                "searched_documents":retrieval.searched_documents,
                "auto_linked_documents":retrieval.auto_linked_documents,
                "evidence_sufficient":retrieval.evidence_sufficient
            },
            "decision":{
                "route":decision.final_route,
                "safe_to_finish":decision.safe_to_finish,
                "journal_status":decision.journal_status,
                "journal":decision.journal,
                "treatment":decision.proposed_treatment,
                "owner_question":decision.owner_question,
                "professional_review_reason":decision.professional_review_reason
            }
        }
        rid=_persist(ingest_event_id,household_id,"primary",detail,transaction_id=txid,route=decision.final_route)
        return {"duplicate_processing":False,"record_id":rid,"transaction_id":txid,"route":decision.final_route,"detail":detail}

    # Document events: extract+match; then reprocess matched transaction through autonomy.
    if docid:
        with SessionLocal() as s:
            doc=s.get(SourceDocument,docid)
            if not doc: raise KeyError("source_document")
            subject,body=doc.subject,doc.body
        ingested=ingest_document(household_id,subject,body,auto_link_threshold=.85)
        matched=ingested.get("auto_linked_transaction_id")
        route=None; decision_detail=None
        if matched:
            enrichment=enrich_transaction(household_id,matched,persist=True)
            with SessionLocal() as s:
                tx_obj=s.get(Transaction,matched)
            decision=decide_with_journal(household_id,tx_obj,enrichment.facts)
            route=decision.final_route
            decision_detail={
                "route":decision.final_route,
                "safe_to_finish":decision.safe_to_finish,
                "journal_status":decision.journal_status,
                "journal":decision.journal,
                "treatment":decision.proposed_treatment,
                "owner_question":decision.owner_question,
                "professional_review_reason":decision.professional_review_reason
            }
        detail={
            "path":"document",
            "matched_transaction_id":matched,
            "match_candidates":ingested.get("matches",[])[:3],
            "document_validation":ingested.get("document_validation"),
            "decision":decision_detail
        }
        rid=_persist(ingest_event_id,household_id,"primary",detail,transaction_id=matched,source_document_id=docid,route=route)
        return {"duplicate_processing":False,"record_id":rid,"source_document_id":docid,"transaction_id":matched,"route":route,"detail":detail}

    # Other normalized events are preserved, but no autonomous accounting action yet.
    detail={"path":"normalized_only","connector_type":connector,"message":"Event retained; no materialized transaction/document action is defined yet."}
    rid=_persist(ingest_event_id,household_id,"primary",detail)
    return {"duplicate_processing":False,"record_id":rid,"route":None,"detail":detail}

def processing_history(household_id:int):
    with SessionLocal() as s:
        rows=s.scalars(select(EventProcessingRecord).where(
            EventProcessingRecord.household_id==household_id
        ).order_by(EventProcessingRecord.id)).all()
        return [{
            "id":r.id,"ingest_event_id":r.ingest_event_id,"action_type":r.action_type,
            "transaction_id":r.transaction_id,"source_document_id":r.source_document_id,
            "route":r.route,"status":r.status,"detail":json.loads(r.detail_json)
        } for r in rows]
