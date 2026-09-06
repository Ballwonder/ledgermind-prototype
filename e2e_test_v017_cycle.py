
import os,tempfile
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

    # Add recurring rule that can resolve business-use facts for Rogers.
    client.post("/api/v016/recurring-rules",json={
        "profile_id":sole["id"],"merchant":"Rogers","category":"Utilities",
        "treatment":"current_business_expense_candidate","business_use_pct":0.70,
        "expected_amount":226,"amount_tolerance_pct":0.20,"cadence":"monthly"
    })

    # Add one clean evidence-backed sole prop expense to ensure end-to-end auto finish path.
    with SessionLocal() as s:
        base=s.query(Transaction).first()
        t=Transaction(household_id=base.household_id,profile_id=sole["id"],provider="test",
          provider_transaction_id="cycle-clean",tx_date=date(2026,9,5),
          merchant_raw="Staples",merchant_normalized="Staples",
          description="office supplies toner paper",amount=-120,
          category="Office Supplies",category_confidence=.98)
        s.add(t);s.flush()
        s.add(Evidence(household_id=base.household_id,transaction_id=t.id,provider="test",
          evidence_type="receipt",merchant="Staples",amount=120,evidence_date=date(2026,9,5),
          subject="Staples receipt",excerpt="toner paper office supplies"))
        s.commit(); clean_id=t.id

    run=client.post("/api/v017/cycle/run?reset_results=true")
    assert run.status_code==200, run.text
    summary=run.json()
    assert summary["processed"]>0
    assert summary["auto_finished"]>0
    assert summary["exception_count"]>=0

    results=client.get("/api/v017/cycle/results").json()["results"]
    clean=next(r for r in results if r["transaction_id"]==clean_id)
    assert clean["route"]=="AUTO_FINISH", clean
    assert clean["journal_balanced"] is True
    assert clean["reconciled"] is True

    ready=client.get("/api/v017/cycle/close-readiness").json()
    exceptions=client.get("/api/v017/cycle/exceptions").json()["exceptions"]

    print({
      "processed":summary["processed"],
      "auto_finished":summary["auto_finished"],
      "owner_questions":summary["owner_questions"],
      "professional_reviews":summary["professional_reviews"],
      "reconciled":summary["reconciled"],
      "close_ready":summary["close_ready"],
      "clean_transaction":clean,
      "exceptions":len(exceptions)
    })
