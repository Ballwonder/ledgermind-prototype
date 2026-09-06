
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

    client.post("/api/v016/recurring-rules",json={
        "profile_id":sole["id"],"merchant":"Rogers","category":"Utilities",
        "treatment":"current_business_expense_candidate","business_use_pct":0.70,
        "expected_amount":226,"amount_tolerance_pct":0.25,"cadence":"monthly"
    })

    with SessionLocal() as s:
        base=s.query(Transaction).first()
        cases=[
          ("Staples","office supplies toner printer paper",-119.0,"Shopping",sole["id"]),
          ("Rogers","wireless mobile service",-226.0,"Other",None),
          ("Staples","printer paper office supplies",-88.0,"Shopping",sole["id"]),
        ]
        ids=[]
        for i,(m,d,a,c,pid) in enumerate(cases):
            t=Transaction(household_id=base.household_id,profile_id=pid,
              provider="test",provider_transaction_id=f"v18-{i}",
              tx_date=date(2026,9,5+i),merchant_raw=m,merchant_normalized=m,
              description=d,amount=a,category=c,category_confidence=.60)
            s.add(t);s.flush()
            s.add(Evidence(household_id=base.household_id,transaction_id=t.id,provider="test",
              evidence_type="receipt" if m=="Staples" else "invoice",
              merchant=m,amount=abs(a),evidence_date=date(2026,9,5+i),
              subject=f"{m} document",excerpt=d))
            ids.append(t.id)
        s.commit()

    enrich=client.post("/api/v018/enrichment/run?persist=true").json()
    assert enrich["changed"]>=3, enrich
    assert enrich["profile_inferred"]>=3, enrich
    assert enrich["high_conf_category"]>=3, enrich

    cycle=client.post("/api/v017/cycle/run?reset_results=true").json()
    results=client.get("/api/v017/cycle/results").json()["results"]
    friendly=[r for r in results if r["transaction_id"] in ids]

    staples=[r for r in friendly if r["merchant"]=="Staples"]
    rogers=next(r for r in friendly if r["merchant"]=="Rogers")
    assert all(r["route"]=="AUTO_FINISH" for r in staples), friendly
    assert rogers["route"]=="AUTO_FINISH", rogers
    assert all(r["journal_balanced"] for r in friendly)
    assert all(r["reconciled"] for r in friendly)

    print({
      "enrichment_changed":enrich["changed"],
      "profile_inferred":enrich["profile_inferred"],
      "high_conf_category":enrich["high_conf_category"],
      "cycle_processed":cycle["processed"],
      "cycle_auto_finished":cycle["auto_finished"],
      "cycle_exceptions":cycle["exception_count"],
      "friendly_routes":[(r["merchant"],r["route"],r["treatment"]) for r in friendly]
    })
