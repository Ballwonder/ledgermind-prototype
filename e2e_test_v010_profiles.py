
import os,tempfile
tmp=tempfile.NamedTemporaryFile(suffix=".db",delete=False); tmp.close()
os.environ["DATABASE_URL"]="sqlite:///"+tmp.name

from fastapi.testclient import TestClient
from app.main import app

with TestClient(app) as client:
    r=client.post("/api/v09/reset")
    assert r.status_code==200

    profiles=client.get("/api/v010/profiles").json()["profiles"]
    assert len(profiles)==4
    kinds={p["profile_type"]:p for p in profiles}
    assert kinds["personal"]["tax_regime"]=="personal_finance"
    assert kinds["sole_proprietor"]["tax_regime"]=="T2125"
    assert kinds["rental"]["tax_regime"]=="T776"
    assert kinds["corporation"]["tax_regime"]=="T2_GIFI"

    txs=client.get("/api/v07/transactions").json()
    amazon=next(t for t in txs if t["merchant"]=="Amazon")
    sole=kinds["sole_proprietor"]
    a=client.post(f"/api/v010/profiles/transactions/{amazon['id']}/assign",json={"profile_id":sole["id"]})
    assert a.status_code==200
    assert a.json()["tax_regime"]=="T2125"

    txs2=client.get("/api/v07/transactions").json()
    amazon2=next(t for t in txs2 if t["merchant"]=="Amazon")
    assert amazon2["profile_type"]=="sole_proprietor"
    assert amazon2["tax_regime"]=="T2125"

    c=client.post("/api/v010/profiles",json={"name":"Side Rental","profile_type":"rental","province":"Ontario"})
    assert c.status_code==200
    assert c.json()["tax_regime"]=="T776"

    print({
      "seed_profiles":len(profiles),
      "amazon_profile":amazon2["profile_name"],
      "amazon_tax_regime":amazon2["tax_regime"],
      "created_profile":c.json()["name"],
      "created_profile_regime":c.json()["tax_regime"]
    })
