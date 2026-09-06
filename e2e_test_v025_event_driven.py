
import os,tempfile,json
from datetime import date
tmp=tempfile.NamedTemporaryFile(suffix=".db",delete=False);tmp.close()
os.environ["DATABASE_URL"]="sqlite:///"+tmp.name

from fastapi.testclient import TestClient
from app.main import app
from app.data_model import SessionLocal,FinancialProfile

with TestClient(app) as client:
    client.post("/api/v09/reset")
    profiles=client.get("/api/v010/profiles").json()["profiles"]
    sole=next(p for p in profiles if p["profile_type"]=="sole_proprietor")
    with SessionLocal() as s:
        p=s.get(FinancialProfile,sole["id"]); p.gst_hst_registered=True; s.commit()

    # Bank transaction arrives first: should process immediately and remain unresolved for lack of business doc.
    bank=client.post("/api/v024/ingest",json={
      "connector_type":"plaid","event_type":"transaction","profile_id":sole["id"],
      "payload":{"transaction_id":"evt-staples","date":"2026-09-06","merchant_name":"Staples","name":"Staples","amount":226.00}
    }).json()
    assert bank["processing"]["route"]=="OWNER_QUESTION",bank
    txid=bank["linked_transaction_id"]

    # Matching Gmail document arrives later: should auto-match and immediately reevaluate same transaction.
    email=client.post("/api/v024/ingest",json={
      "connector_type":"gmail","event_type":"message","profile_id":sole["id"],
      "payload":{"message_id":"evt-msg-1","account":"accounting@example.test","label":"Business Receipts",
        "received_at":"2026-09-06T10:00:00","subject":"Staples invoice",
        "body":"Supplier: Staples\\nInvoice Date: 2026-09-06\\nDescription: Office supplies\\nTotal: $226.00\\nHST: included\\nGST/HST Number: 123456789RT0001\\nPayment Terms: Paid by card"}
    }).json()
    assert email["processing"]["transaction_id"]==txid,email
    assert email["processing"]["route"]=="AUTO_FINISH",email

    # Idempotent explicit reprocessing.
    event_id=email["ingest_event_id"]
    again=client.post(f"/api/v025/events/{event_id}/process").json()
    assert again["duplicate_processing"] is True,again

    hist=client.get("/api/v025/events/history").json()["history"]
    assert len(hist)==2,hist

    print(json.dumps({
      "transaction_route_on_bank_arrival":bank["processing"]["route"],
      "transaction_id":txid,
      "route_after_email_arrival":email["processing"]["route"],
      "email_matched_transaction":email["processing"]["transaction_id"],
      "reprocess_blocked":again["duplicate_processing"],
      "processing_record_count":len(hist),
      "processing_paths":[x["detail"]["path"] for x in hist]
    }))
