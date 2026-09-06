
import os,tempfile,json
from datetime import date
tmp=tempfile.NamedTemporaryFile(suffix=".db",delete=False);tmp.close()
os.environ["DATABASE_URL"]="sqlite:///"+tmp.name

from fastapi.testclient import TestClient
from app.main import app
from app.data_model import SessionLocal,Transaction,FinancialProfile

with TestClient(app) as client:
    client.post("/api/v09/reset")
    profiles=client.get("/api/v010/profiles").json()["profiles"]
    sole=next(p for p in profiles if p["profile_type"]=="sole_proprietor")

    with SessionLocal() as s:
        p=s.get(FinancialProfile,sole["id"]); p.gst_hst_registered=True
        base=s.query(Transaction).first()
        tx=Transaction(household_id=base.household_id,profile_id=p.id,provider="test",
          provider_transaction_id="v22-staples",tx_date=date(2026,9,6),
          merchant_raw="Staples",merchant_normalized="Staples",
          description="office supplies",amount=-226.00,
          category="Office Supplies",category_confidence=.98)
        s.add(tx);s.commit();txid=tx.id

    before=client.post("/api/v017/cycle/run?reset_results=true").json()
    rb=next(r for r in client.get("/api/v017/cycle/results").json()["results"] if r["transaction_id"]==txid)
    assert rb["route"]=="OWNER_QUESTION",rb

    body="""Supplier: Staples
Invoice Date: 2026-09-06
Description: Office supplies
Total: $226.00
HST: included
GST/HST Number: 123456789RT0001
Payment Terms: Paid by card
"""
    ing=client.post("/api/v022/document-ingest/ingest",json={
      "subject":"Staples invoice","body":body
    }).json()
    assert ing["auto_linked_transaction_id"]==txid,ing
    assert ing["document_validation"]["valid_for_itc_support"] is True,ing

    after=client.post("/api/v017/cycle/run?reset_results=true").json()
    ra=next(r for r in client.get("/api/v017/cycle/results").json()["results"] if r["transaction_id"]==txid)
    assert ra["route"]=="AUTO_FINISH",ra

    # Ambiguous/mismatched document should not auto-link.
    amb=client.post("/api/v022/document-ingest/ingest",json={
      "subject":"Unknown invoice","body":"Supplier: Random Vendor\nInvoice Date: 2026-09-06\nTotal: $999.99"
    }).json()
    assert amb["auto_linked_transaction_id"] is None,amb

    print(json.dumps({
      "before":rb["route"],
      "extracted":ing["extracted"],
      "top_match":ing["matches"][0],
      "auto_linked_transaction_id":ing["auto_linked_transaction_id"],
      "document_valid":ing["document_validation"]["valid_for_itc_support"],
      "after":ra["route"],
      "ambiguous_auto_link":amb["auto_linked_transaction_id"],
      "cycle_auto_finished":after["auto_finished"]
    }))
