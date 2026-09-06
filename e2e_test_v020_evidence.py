
import os,tempfile,json
from datetime import date
tmp=tempfile.NamedTemporaryFile(suffix=".db",delete=False);tmp.close()
os.environ["DATABASE_URL"]="sqlite:///"+tmp.name
from fastapi.testclient import TestClient
from app.main import app
from app.data_model import SessionLocal,Transaction,Evidence

with TestClient(app) as client:
    client.post("/api/v09/reset")
    profiles=client.get("/api/v010/profiles").json()["profiles"]
    sole=next(p for p in profiles if p["profile_type"]=="sole_proprietor")

    # clean business expense with document
    with SessionLocal() as s:
        base=s.query(Transaction).first()
        good=Transaction(household_id=base.household_id,profile_id=sole["id"],provider="test",
          provider_transaction_id="v20-good",tx_date=date(2026,9,6),merchant_raw="Staples",
          merchant_normalized="Staples",description="office supplies toner paper",amount=-120,
          category="Office Supplies",category_confidence=.98)
        s.add(good);s.flush()
        s.add(Evidence(household_id=base.household_id,transaction_id=good.id,provider="test",
          evidence_type="receipt",merchant="Staples",amount=120,evidence_date=date(2026,9,6),
          subject="Staples receipt",excerpt="office supplies toner paper"))
        # business expense without document must remain blocked
        bad=Transaction(household_id=base.household_id,profile_id=sole["id"],provider="test",
          provider_transaction_id="v20-bad",tx_date=date(2026,9,6),merchant_raw="Office Vendor",
          merchant_normalized="Office Vendor",description="office supplies",amount=-90,
          category="Office Supplies",category_confidence=.98)
        s.add(bad);s.commit(); good_id=good.id; bad_id=bad.id

    run=client.post("/api/v017/cycle/run?reset_results=true").json()
    diag=client.get("/api/v019/diagnostics/exceptions").json()
    results=client.get("/api/v017/cycle/results").json()["results"]
    good_r=next(r for r in results if r["transaction_id"]==good_id)
    bad_r=next(r for r in results if r["transaction_id"]==bad_id)
    assert good_r["route"]=="AUTO_FINISH",good_r
    assert bad_r["route"]=="OWNER_QUESTION",bad_r

    # seeded personal transactions should no longer all fail solely for receipt absence
    assert run["auto_finished"]>1,run
    print(json.dumps({
      "cycle":run,
      "bottlenecks":diag["bottlenecks"],
      "good_business_expense":good_r["route"],
      "unsupported_business_expense":bad_r["route"]
    }))
