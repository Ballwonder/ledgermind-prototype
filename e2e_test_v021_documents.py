
import os,tempfile,json
from datetime import date
tmp=tempfile.NamedTemporaryFile(suffix=".db",delete=False);tmp.close()
os.environ["DATABASE_URL"]="sqlite:///"+tmp.name
from fastapi.testclient import TestClient
from app.main import app
from app.data_model import SessionLocal,Transaction,Evidence,FinancialProfile

with TestClient(app) as client:
    client.post("/api/v09/reset")
    profiles=client.get("/api/v010/profiles").json()["profiles"]
    sole=next(p for p in profiles if p["profile_type"]=="sole_proprietor")
    with SessionLocal() as s:
        p=s.get(FinancialProfile,sole["id"]); p.gst_hst_registered=True
        base=s.query(Transaction).first()
        tx=Transaction(household_id=base.household_id,profile_id=p.id,provider="test",
          provider_transaction_id="v21-office",tx_date=date(2026,9,6),
          merchant_raw="Staples",merchant_normalized="Staples",
          description="office supplies",amount=-226,
          category="Office Supplies",category_confidence=.98)
        s.add(tx);s.flush()
        s.add(Evidence(household_id=base.household_id,transaction_id=tx.id,provider="test",
          evidence_type="receipt",merchant="Staples",amount=226,evidence_date=date(2026,9,6),
          subject="Staples receipt",excerpt="office supplies"))
        s.commit(); txid=tx.id

    # threshold unit checks
    u100=client.post("/api/v021/documents/validate",json={
      "supplier_name":"Vendor","invoice_or_tax_date":"2026-09-06","total_amount":80
    }).json()
    mid_bad=client.post("/api/v021/documents/validate",json={
      "supplier_name":"Vendor","invoice_or_tax_date":"2026-09-06","total_amount":226
    }).json()
    mid_good=client.post("/api/v021/documents/validate",json={
      "supplier_name":"Vendor","invoice_or_tax_date":"2026-09-06","total_amount":226,
      "gst_hst_indication":True,"supplier_gst_hst_number":"123456789RT0001"
    }).json()
    high_bad=client.post("/api/v021/documents/validate",json={
      "supplier_name":"Vendor","invoice_or_tax_date":"2026-09-06","total_amount":700,
      "gst_hst_indication":True,"supplier_gst_hst_number":"123456789RT0001"
    }).json()
    high_good=client.post("/api/v021/documents/validate",json={
      "supplier_name":"Vendor","invoice_or_tax_date":"2026-09-06","total_amount":700,
      "gst_hst_indication":True,"supplier_gst_hst_number":"123456789RT0001",
      "buyer_name":"Demo Consulting","description":"Office furniture","payment_terms":"Paid by card"
    }).json()
    assert u100["valid_for_itc_support"] is True
    assert mid_bad["valid_for_itc_support"] is False
    assert mid_good["valid_for_itc_support"] is True
    assert high_bad["valid_for_itc_support"] is False
    assert high_good["valid_for_itc_support"] is True

    # before document validation, GST-registered expense remains blocked
    before=client.post("/api/v017/cycle/run?reset_results=true").json()
    results=client.get("/api/v017/cycle/results").json()["results"]
    rb=next(r for r in results if r["transaction_id"]==txid)
    assert rb["route"]=="OWNER_QUESTION",rb

    client.post(f"/api/v021/documents/transactions/{txid}/validate",json={
      "supplier_name":"Staples","invoice_or_tax_date":"2026-09-06","total_amount":226,
      "gst_hst_indication":True,"supplier_gst_hst_number":"123456789RT0001"
    })

    after=client.post("/api/v017/cycle/run?reset_results=true").json()
    results=client.get("/api/v017/cycle/results").json()["results"]
    ra=next(r for r in results if r["transaction_id"]==txid)
    assert ra["route"]=="AUTO_FINISH",ra

    print(json.dumps({
      "under_100_valid":u100["valid_for_itc_support"],
      "mid_missing":mid_bad["missing_fields"],
      "mid_valid":mid_good["valid_for_itc_support"],
      "high_missing":high_bad["missing_fields"],
      "high_valid":high_good["valid_for_itc_support"],
      "gst_expense_before_validation":rb["route"],
      "gst_expense_after_validation":ra["route"],
      "after_cycle_auto_finished":after["auto_finished"]
    }))
