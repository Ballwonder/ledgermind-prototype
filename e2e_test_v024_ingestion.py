
import os,tempfile,json
tmp=tempfile.NamedTemporaryFile(suffix=".db",delete=False);tmp.close()
os.environ["DATABASE_URL"]="sqlite:///"+tmp.name

from fastapi.testclient import TestClient
from app.main import app

with TestClient(app) as client:
    client.post("/api/v09/reset")
    profiles=client.get("/api/v010/profiles").json()["profiles"]
    sole=next(p for p in profiles if p["profile_type"]=="sole_proprietor")

    bank=client.post("/api/v024/ingest",json={
      "connector_type":"plaid","event_type":"transaction",
      "profile_id":sole["id"],
      "payload":{"transaction_id":"plaid-001","date":"2026-09-06","merchant_name":"Staples","name":"Staples","amount":226.00}
    }).json()
    assert bank["linked_transaction_id"] is not None
    assert bank["normalized"]["transaction"]["amount"]==-226.0

    email=client.post("/api/v024/ingest",json={
      "connector_type":"gmail","event_type":"message",
      "profile_id":sole["id"],
      "payload":{"message_id":"msg-001","account":"accounting@example.test","label":"Business Receipts",
                 "received_at":"2026-09-06T10:00:00","subject":"Staples invoice",
                 "body":"Supplier: Staples\\nInvoice Date: 2026-09-06\\nTotal: $226.00"}
    }).json()
    assert email["linked_source_document_id"] is not None

    payroll=client.post("/api/v024/ingest",json={
      "connector_type":"payroll","event_type":"payroll_run",
      "profile_id":sole["id"],
      "payload":{"id":"pay-001","pay_date":"2026-09-05","gross_pay":5000,"net_pay":3800,"employer_cost":5400}
    }).json()
    assert payroll["linked_transaction_id"] is None
    assert payroll["normalized"]["payroll"]["gross_pay"]==5000

    accounting=client.post("/api/v024/ingest",json={
      "connector_type":"quickbooks","event_type":"journal_entry",
      "profile_id":sole["id"],
      "payload":{"id":"qbo-je-001","object_type":"journal_entry","date":"2026-09-06",
                 "account":"Office Supplies","debit":226,"credit":0}
    }).json()
    assert accounting["normalized"]["accounting"]["account"]=="Office Supplies"

    dup=client.post("/api/v024/ingest",json={
      "connector_type":"plaid","event_type":"transaction",
      "profile_id":sole["id"],
      "payload":{"transaction_id":"plaid-001","date":"2026-09-06","merchant_name":"Staples","name":"Staples","amount":226.00}
    }).json()
    assert dup["duplicate"] is True

    events=client.get("/api/v024/ingest/events").json()["events"]
    assert len(events)==4,events

    print(json.dumps({
      "bank_transaction_id":bank["linked_transaction_id"],
      "email_source_document_id":email["linked_source_document_id"],
      "payroll_status":payroll["normalized"]["payroll"],
      "accounting_status":accounting["normalized"]["accounting"],
      "duplicate_blocked":dup["duplicate"],
      "ingest_event_count":len(events)
    }))
