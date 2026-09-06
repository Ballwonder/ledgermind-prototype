
import os,tempfile
tmp=tempfile.NamedTemporaryFile(suffix=".db",delete=False); tmp.close()
os.environ["DATABASE_URL"]="sqlite:///"+tmp.name

from fastapi.testclient import TestClient
from app.main import app
from app.data_model import SessionLocal, Transaction

with TestClient(app) as client:
    client.post("/api/v09/reset")
    profiles=client.get("/api/v010/profiles").json()["profiles"]
    sole=next(p for p in profiles if p["profile_type"]=="sole_proprietor")
    personal=next(p for p in profiles if p["profile_type"]=="personal")

    txs=client.get("/api/v07/transactions").json()
    amazon=next(t for t in txs if t["merchant"]=="Amazon")

    # Make Amazon unassigned to test ambiguity.
    with SessionLocal() as s:
        tx=s.get(Transaction,amazon["id"])
        tx.profile_id=None
        s.commit()

    p=client.get(f"/api/v012/profile-assignment/transactions/{amazon['id']}").json()
    assert p["action"]=="owner_question"

    c=client.post(f"/api/v012/profile-assignment/transactions/{amazon['id']}/confirm",
                  json={"profile_id":sole["id"],"learn":True})
    assert c.status_code==200

    # Add another Amazon transaction, unassigned.
    with SessionLocal() as s:
        orig=s.get(Transaction,amazon["id"])
        clone=Transaction(
            household_id=orig.household_id,profile_id=None,provider="demo2",
            provider_transaction_id="amazon-repeat",tx_date=orig.tx_date,
            merchant_raw="Amazon",merchant_normalized="Amazon",description="Amazon order",
            amount=-49.99,category="Shopping",category_confidence=.70
        )
        s.add(clone);s.commit();s.refresh(clone); clone_id=clone.id

    p2=client.get(f"/api/v012/profile-assignment/transactions/{clone_id}").json()
    assert p2["proposed_profile_id"]==sole["id"]
    assert p2["action"]=="auto_assign"
    assert p2["confidence"]>=.95

    a=client.post(f"/api/v012/profile-assignment/transactions/{clone_id}/auto").json()
    assert a["applied"] is True

    # Accounting layer now inherits T2125 through the assigned profile.
    ev=client.post(f"/api/v011/accounting/transactions/{clone_id}/evaluate",
                   json={"item_type":"service","personal_component_present":False})
    assert ev.status_code==200
    assert ev.json()["tax_regime"]=="T2125"

    state=client.get("/api/v09/state").json()
    assert state["counts"]["profile_assignment_rules"]==1

    print({
      "first_amazon_action":p["action"],
      "confirmed_profile":c.json()["profile_name"],
      "learned_repeat_action":p2["action"],
      "repeat_confidence":p2["confidence"],
      "auto_applied":a["applied"],
      "downstream_tax_regime":ev.json()["tax_regime"],
      "profile_assignment_rules":state["counts"]["profile_assignment_rules"]
    })
