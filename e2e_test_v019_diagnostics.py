
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
    rental=next(p for p in profiles if p["profile_type"]=="rental")

    # one clean autonomous case
    with SessionLocal() as s:
        base=s.query(Transaction).first()
        t=Transaction(household_id=base.household_id,profile_id=sole["id"],provider="test",
          provider_transaction_id="diag-clean",tx_date=date(2026,9,6),
          merchant_raw="Staples",merchant_normalized="Staples",
          description="office supplies toner paper",amount=-100,
          category="Office Supplies",category_confidence=.98)
        s.add(t);s.flush()
        s.add(Evidence(household_id=base.household_id,transaction_id=t.id,provider="test",
          evidence_type="receipt",merchant="Staples",amount=100,evidence_date=date(2026,9,6),
          subject="receipt",excerpt="office supplies toner paper"))
        s.commit()

    run=client.post("/api/v017/cycle/run?reset_results=true").json()
    diag=client.get("/api/v019/diagnostics/exceptions").json()
    assert diag["exception_count"]==run["exception_count"]
    assert sum(x["count"] for x in diag["bottlenecks"])==diag["exception_count"]
    assert all("primary_cause" in x for x in diag["exceptions"])
    print(json.dumps({
      "cycle":run,
      "bottlenecks":diag["bottlenecks"],
      "sample_exceptions":diag["exceptions"][:5]
    }))
