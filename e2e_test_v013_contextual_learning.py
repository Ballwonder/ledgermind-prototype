
import os,tempfile
from datetime import date
tmp=tempfile.NamedTemporaryFile(suffix=".db",delete=False); tmp.close()
os.environ["DATABASE_URL"]="sqlite:///"+tmp.name

from fastapi.testclient import TestClient
from app.main import app
from app.data_model import SessionLocal, Transaction, Evidence

with TestClient(app) as client:
    client.post("/api/v09/reset")
    profiles=client.get("/api/v010/profiles").json()["profiles"]
    sole=next(p for p in profiles if p["profile_type"]=="sole_proprietor")
    personal=next(p for p in profiles if p["profile_type"]=="personal")

    # Create first Amazon office-supply transaction with receipt evidence.
    with SessionLocal() as s:
        base=s.query(Transaction).first()
        biz=Transaction(
            household_id=base.household_id,profile_id=None,account_id=base.account_id,
            provider="test",provider_transaction_id="biz-amz-1",tx_date=date(2026,9,6),
            merchant_raw="Amazon",merchant_normalized="Amazon",
            description="Amazon toner paper office supplies",amount=-119.99,
            category="Office Supplies",category_confidence=.70
        )
        s.add(biz);s.flush()
        s.add(Evidence(
            household_id=base.household_id,transaction_id=biz.id,provider="test",
            evidence_type="receipt",merchant="Amazon",amount=119.99,evidence_date=date(2026,9,6),
            subject="Amazon office supplies receipt",
            excerpt="toner paper printer supplies for client work"
        ))
        s.commit(); biz_id=biz.id

    # Confirm to sole prop and learn contextual memory.
    c=client.post(f"/api/v012/profile-assignment/transactions/{biz_id}/confirm",
                  json={"profile_id":sole["id"],"learn":True})
    assert c.status_code==200

    mems=client.get("/api/v013/context-memory").json()["memories"]
    assert len(mems)>=1
    assert mems[0]["merchant"]=="amazon"

    # Similar office-supply purchase should strongly reuse the precedent.
    with SessionLocal() as s:
        base=s.query(Transaction).first()
        sim=Transaction(
            household_id=base.household_id,profile_id=None,account_id=base.account_id,
            provider="test",provider_transaction_id="biz-amz-2",tx_date=date(2026,9,7),
            merchant_raw="Amazon",merchant_normalized="Amazon",
            description="Amazon printer toner and paper",amount=-105.00,
            category="Shopping",category_confidence=.60
        )
        s.add(sim);s.flush()
        s.add(Evidence(
            household_id=base.household_id,transaction_id=sim.id,provider="test",
            evidence_type="receipt",merchant="Amazon",amount=105.00,evidence_date=date(2026,9,7),
            subject="Amazon printer toner receipt",
            excerpt="printer toner paper office supplies"
        ))
        s.commit(); sim_id=sim.id

    p=client.get(f"/api/v012/profile-assignment/transactions/{sim_id}").json()
    assert p["proposed_profile_id"]==sole["id"], p
    assert p["confidence"]>=.95, p
    assert p["action"]=="auto_assign"

    # Different Amazon household-goods purchase must NOT inherit automatically.
    with SessionLocal() as s:
        base=s.query(Transaction).first()
        home=Transaction(
            household_id=base.household_id,profile_id=None,account_id=None,
            provider="test",provider_transaction_id="home-amz",tx_date=date(2026,9,8),
            merchant_raw="Amazon",merchant_normalized="Amazon",
            description="Amazon baby household items",amount=-58.40,
            category="Shopping",category_confidence=.60
        )
        s.add(home);s.flush()
        s.add(Evidence(
            household_id=base.household_id,transaction_id=home.id,provider="test",
            evidence_type="receipt",merchant="Amazon",amount=58.40,evidence_date=date(2026,9,8),
            subject="Amazon household order",
            excerpt="household storage baby items"
        ))
        s.commit(); home_id=home.id

    h=client.get(f"/api/v012/profile-assignment/transactions/{home_id}").json()
    assert h["action"] in {"owner_question","confirm_profile"}
    assert not (h["action"]=="auto_assign" and h["proposed_profile_id"]==sole["id"])

    print({
      "context_memories":len(mems),
      "similar_office_purchase_action":p["action"],
      "similar_office_purchase_confidence":p["confidence"],
      "similar_office_profile":p["proposed_profile_name"],
      "different_household_purchase_action":h["action"],
      "different_household_proposal":h["proposed_profile_name"]
    })
