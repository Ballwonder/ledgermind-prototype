
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
          provider_transaction_id="v23-staples",tx_date=date(2026,9,6),
          merchant_raw="Staples",merchant_normalized="Staples",
          description="office supplies",amount=-226,
          category="Office Supplies",category_confidence=.98)
        s.add(tx);s.commit();txid=tx.id

    before=client.post("/api/v017/cycle/run?reset_results=true").json()
    rb=next(r for r in client.get("/api/v017/cycle/results").json()["results"] if r["transaction_id"]==txid)
    assert rb["route"]=="OWNER_QUESTION",rb

    # Add a mapped source and an unprocessed invoice in that source.
    client.post("/api/v016/source-maps",json={
      "profile_id":sole["id"],"source_type":"email","source_value":"accounting@example.test",
      "folder_or_label":"Business Receipts","trust_level":"dedicated","confidence":0.995
    })
    client.post("/api/v023/retrieval/source-documents",json={
      "profile_id":sole["id"],"source_type":"email","source_value":"accounting@example.test",
      "folder_or_label":"Business Receipts","subject":"Staples invoice",
      "body":"Supplier: Staples\\nInvoice Date: 2026-09-06\\nDescription: Office supplies\\nTotal: $226.00\\nHST: included\\nGST/HST Number: 123456789RT0001\\nPayment Terms: Paid by card"
    })

    retrieval=client.post(f"/api/v023/retrieval/transactions/{txid}").json()
    assert retrieval["auto_linked_documents"]==1,retrieval
    assert retrieval["evidence_sufficient"] is True,retrieval
    assert retrieval["owner_question_required"] is False,retrieval

    after=client.post("/api/v017/cycle/run?reset_results=true").json()
    ra=next(r for r in client.get("/api/v017/cycle/results").json()["results"] if r["transaction_id"]==txid)
    assert ra["route"]=="AUTO_FINISH",ra

    # Add ambiguous source doc: should not auto-link.
    client.post("/api/v023/retrieval/source-documents",json={
      "profile_id":sole["id"],"source_type":"email","source_value":"accounting@example.test",
      "folder_or_label":"Business Receipts","subject":"Unknown invoice",
      "body":"Supplier: Random Vendor\\nInvoice Date: 2026-09-06\\nTotal: $999.99"
    })
    allr=client.post("/api/v023/retrieval/run").json()

    print(json.dumps({
      "before":rb["route"],
      "retrieval":retrieval,
      "after":ra["route"],
      "all_retrieval_summary":{
        "processed":allr["processed"],
        "resolved":allr["resolved"],
        "candidate_needs_confirmation":allr["candidate_needs_confirmation"],
        "unresolved":allr["unresolved"],
        "auto_linked_documents":allr["auto_linked_documents"]
      },
      "cycle_auto_finished":after["auto_finished"]
    }))
