
from __future__ import annotations
from dataclasses import dataclass,asdict
from datetime import datetime,date
import json, hashlib
from sqlalchemy import select
from .data_model import SessionLocal,IngestEvent,Transaction,SourceDocument,FinancialProfile

@dataclass
class NormalizedIngest:
    connector_type:str
    event_type:str
    external_id:str|None
    profile_id:int|None
    occurred_at:str|None
    transaction:dict|None
    document:dict|None
    payroll:dict|None
    accounting:dict|None
    warnings:list[str]

def _dt(v):
    if not v: return None
    if isinstance(v,(date,datetime)): return v
    try:
        if "T" in str(v): return datetime.fromisoformat(str(v).replace("Z","+00:00"))
        return datetime.fromisoformat(str(v))
    except: return None

def normalize_payload(connector_type:str,event_type:str,payload:dict,profile_id:int|None=None):
    c=connector_type.lower()
    warnings=[]
    tx=None; doc=None; payroll=None; accounting=None
    external_id=str(payload.get("id") or payload.get("transaction_id") or payload.get("message_id") or payload.get("external_id") or "") or None
    occurred=payload.get("date") or payload.get("datetime") or payload.get("received_at") or payload.get("posted_at")

    if c in {"plaid","bank","credit_card","csv_bank"}:
        amount=payload.get("amount")
        # Canonical convention: inflow positive, outflow negative.
        if c=="plaid" and amount is not None:
            amount=-float(amount)  # Plaid transaction amounts are commonly positive for outflows.
        elif amount is not None:
            amount=float(amount)
        tx={
            "provider":c,
            "provider_transaction_id":external_id,
            "tx_date":str(payload.get("date") or payload.get("authorized_date") or "")[:10] or None,
            "merchant_raw":payload.get("merchant_name") or payload.get("name") or payload.get("description"),
            "merchant_normalized":payload.get("merchant_name") or payload.get("name"),
            "description":payload.get("description") or payload.get("name") or payload.get("merchant_name") or "Imported transaction",
            "amount":amount,
            "category":payload.get("category"),
            "category_confidence":payload.get("category_confidence")
        }
    elif c in {"gmail","outlook","email","upload"}:
        doc={
            "source_type":"email" if c in {"gmail","outlook","email"} else "upload",
            "source_value":payload.get("account") or payload.get("mailbox") or payload.get("source_value"),
            "folder_or_label":payload.get("folder") or payload.get("label") or payload.get("folder_or_label"),
            "subject":payload.get("subject"),
            "body":payload.get("body") or payload.get("text") or payload.get("content"),
            "received_at":str(payload.get("received_at") or payload.get("date") or "")
        }
    elif c=="payroll":
        payroll={
            "payroll_run_id":external_id,
            "gross_pay":payload.get("gross_pay"),
            "net_pay":payload.get("net_pay"),
            "employer_cost":payload.get("employer_cost"),
            "withholdings":payload.get("withholdings"),
            "pay_date":payload.get("pay_date") or payload.get("date"),
            "source_name":payload.get("source_name")
        }
    elif c in {"quickbooks","xero","accounting"}:
        accounting={
            "object_type":payload.get("object_type") or event_type,
            "object_id":external_id,
            "account":payload.get("account"),
            "debit":payload.get("debit"),
            "credit":payload.get("credit"),
            "memo":payload.get("memo"),
            "date":payload.get("date")
        }
    else:
        warnings.append("Unknown connector type; raw payload retained without domain normalization.")

    return NormalizedIngest(
        connector_type=c,event_type=event_type,external_id=external_id,
        profile_id=profile_id,occurred_at=str(occurred) if occurred else None,
        transaction=tx,document=doc,payroll=payroll,accounting=accounting,warnings=warnings
    )

def _fingerprint(connector_type,event_type,payload):
    blob=json.dumps([connector_type,event_type,payload],sort_keys=True,default=str)
    return hashlib.sha256(blob.encode()).hexdigest()

def ingest_event(household_id:int,connector_type:str,event_type:str,payload:dict,profile_id:int|None=None,auto_process:bool=True):
    normalized=normalize_payload(connector_type,event_type,payload,profile_id)
    external_id=normalized.external_id or _fingerprint(connector_type,event_type,payload)
    with SessionLocal() as s:
        existing=s.scalar(select(IngestEvent).where(
            IngestEvent.household_id==household_id,
            IngestEvent.connector_type==normalized.connector_type,
            IngestEvent.external_id==external_id,
            IngestEvent.event_type==event_type
        ))
        if existing:
            return {"duplicate":True,"ingest_event_id":existing.id,
                    "linked_transaction_id":existing.linked_transaction_id,
                    "linked_source_document_id":existing.linked_source_document_id,
                    "normalized":asdict(normalized)}

        txid=None; docid=None
        if normalized.transaction:
            nt=normalized.transaction
            tx=Transaction(
                household_id=household_id,profile_id=profile_id,
                provider=nt["provider"],provider_transaction_id=nt["provider_transaction_id"] or external_id,
                tx_date=date.fromisoformat(nt["tx_date"]) if nt.get("tx_date") else date.today(),
                merchant_raw=nt.get("merchant_raw"),merchant_normalized=nt.get("merchant_normalized"),
                description=nt.get("description"),amount=nt.get("amount") or 0,
                category=nt.get("category"),category_confidence=nt.get("category_confidence")
            )
            s.add(tx);s.flush();txid=tx.id

        if normalized.document:
            nd=normalized.document
            d=SourceDocument(
                household_id=household_id,profile_id=profile_id,
                source_type=nd["source_type"],source_value=nd.get("source_value"),
                folder_or_label=nd.get("folder_or_label"),subject=nd.get("subject"),
                body=nd.get("body"),received_at=_dt(nd.get("received_at")) or datetime.utcnow()
            )
            s.add(d);s.flush();docid=d.id

        ev=IngestEvent(
            household_id=household_id,profile_id=profile_id,
            connector_type=normalized.connector_type,external_id=external_id,
            event_type=event_type,occurred_at=_dt(normalized.occurred_at),
            raw_payload_json=json.dumps(payload,default=str),
            normalized_payload_json=json.dumps(asdict(normalized),default=str),
            ingest_status="materialized" if (txid or docid) else "normalized_only",
            linked_transaction_id=txid,linked_source_document_id=docid
        )
        s.add(ev);s.commit();s.refresh(ev)
        result={"duplicate":False,"ingest_event_id":ev.id,
                "linked_transaction_id":txid,"linked_source_document_id":docid,
                "normalized":asdict(normalized)}
        event_id=ev.id
    if auto_process:
        from .durable_processing import enqueue,run_job
        job_id=enqueue(household_id,event_id)
        job=run_job(job_id)
        result["job"]=job
        result["processing"]=job.get("result")
    return result

def list_ingest_events(household_id:int):
    with SessionLocal() as s:
        rows=s.scalars(select(IngestEvent).where(
            IngestEvent.household_id==household_id
        ).order_by(IngestEvent.id)).all()
        return [{
            "id":r.id,"connector_type":r.connector_type,"event_type":r.event_type,
            "external_id":r.external_id,"status":r.ingest_status,
            "linked_transaction_id":r.linked_transaction_id,
            "linked_source_document_id":r.linked_source_document_id
        } for r in rows]
