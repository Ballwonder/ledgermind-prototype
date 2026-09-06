
import os, tempfile
tmp=tempfile.NamedTemporaryFile(suffix=".db",delete=False)
tmp.close()
os.environ["DATABASE_URL"]="sqlite:///"+tmp.name

from fastapi.testclient import TestClient
from app.main import app

with TestClient(app) as client:
    r=client.post("/api/v09/reset")
    assert r.status_code==200, r.text
    state=client.get("/api/v09/state").json()
    assert len(state["transactions"])==12
    assert state["counts"]["corrections"]==0

    cycle=client.post("/api/v09/demo-cycle")
    assert cycle.status_code==200, cycle.text
    assert len(cycle.json()["evidence_matches"])>=1

    state=client.get("/api/v09/state").json()
    amazon=next(t for t in state["transactions"] if t["merchant"]=="Amazon")
    corr=client.post(f"/api/v07/transactions/{amazon['id']}/category",json={
        "category":"Home","note":"Sandbox correction"
    })
    assert corr.status_code==200, corr.text

    state=client.get("/api/v09/state").json()
    assert state["counts"]["corrections"]==1
    assert state["counts"]["merchant_memory"]==1
    amazon2=next(t for t in state["transactions"] if t["merchant"]=="Amazon")
    assert amazon2["category"]=="Home"
    assert amazon2["confidence"]==1.0

    print({
      "transactions":len(state["transactions"]),
      "evidence":state["counts"]["evidence"],
      "corrections":state["counts"]["corrections"],
      "merchant_memory":state["counts"]["merchant_memory"],
      "insights":state["counts"]["insights"],
      "audit_events":state["counts"]["audit_events"],
      "amazon_category":amazon2["category"],
      "amazon_confidence":amazon2["confidence"]
    })
