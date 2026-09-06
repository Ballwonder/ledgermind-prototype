
import os,tempfile
from datetime import date
tmp=tempfile.NamedTemporaryFile(suffix=".db",delete=False);tmp.close()
os.environ["DATABASE_URL"]="sqlite:///"+tmp.name

from fastapi.testclient import TestClient
from app.main import app
from app.data_model import SessionLocal, Transaction, Evidence

with TestClient(app) as client:
    client.post("/api/v09/reset")
    profiles=client.get("/api/v010/profiles").json()["profiles"]
    sole=next(p for p in profiles if p["profile_type"]=="sole_proprietor")
    rental=next(p for p in profiles if p["profile_type"]=="rental")

    # A: clean sole-prop office-supply transaction with evidence -> AUTO_FINISH
    with SessionLocal() as s:
        base=s.query(Transaction).first()
        a=Transaction(household_id=base.household_id,profile_id=sole["id"],provider="test",
            provider_transaction_id="A",tx_date=date(2026,9,1),
            merchant_raw="Staples",merchant_normalized="Staples",
            description="toner paper office supplies",amount=-113,
            category="Office Supplies",category_confidence=.98)
        s.add(a);s.flush()
        s.add(Evidence(household_id=base.household_id,transaction_id=a.id,provider="test",
            evidence_type="receipt",merchant="Staples",amount=113,evidence_date=date(2026,9,1),
            subject="Staples receipt",excerpt="paper toner office supplies subtotal and tax"))
        s.commit(); aid=a.id
    da=client.post(f"/api/v015/autonomy/transactions/{aid}",json={"item_type":"consumable"}).json()
    assert da["route"]=="AUTO_FINISH", da

    # B: mixed use, missing % -> OWNER_QUESTION
    with SessionLocal() as s:
        base=s.query(Transaction).first()
        b=Transaction(household_id=base.household_id,profile_id=sole["id"],provider="test",
            provider_transaction_id="B",tx_date=date(2026,9,2),
            merchant_raw="Rogers",merchant_normalized="Rogers",
            description="mobile service",amount=-226,category="Utilities",category_confidence=.9)
        s.add(b);s.flush()
        s.add(Evidence(household_id=base.household_id,transaction_id=b.id,provider="test",
            evidence_type="invoice",merchant="Rogers",amount=226,evidence_date=date(2026,9,2),
            subject="Rogers invoice",excerpt="wireless mobile service"))
        s.commit(); bid=b.id
    db=client.post(f"/api/v015/autonomy/transactions/{bid}",json={"item_type":"service","personal_component_present":True}).json()
    assert db["route"]=="OWNER_QUESTION", db

    # C: rental improvement -> PROFESSIONAL_REVIEW
    with SessionLocal() as s:
        base=s.query(Transaction).first()
        c=Transaction(household_id=base.household_id,profile_id=rental["id"],provider="test",
            provider_transaction_id="C",tx_date=date(2026,9,3),
            merchant_raw="ABC Contracting",merchant_normalized="ABC Contracting",
            description="bathroom renovation upgraded finishes",amount=-8400,
            category="Repairs",category_confidence=.85)
        s.add(c);s.flush()
        s.add(Evidence(household_id=base.household_id,transaction_id=c.id,provider="test",
            evidence_type="invoice",merchant="ABC Contracting",amount=8400,evidence_date=date(2026,9,3),
            subject="Bathroom renovation",excerpt="upgrade tile vanity fixtures improved finishes"))
        s.commit(); cid=c.id
    dc=client.post(f"/api/v015/autonomy/transactions/{cid}",json={
        "item_type":"repair","lasting_benefit":True,"improves_beyond_original_condition":True
    }).json()
    assert dc["route"]=="PROFESSIONAL_REVIEW", dc

    # D: unknown profile -> OWNER_QUESTION
    with SessionLocal() as s:
        base=s.query(Transaction).first()
        d=Transaction(household_id=base.household_id,profile_id=None,provider="test",
            provider_transaction_id="D",tx_date=date(2026,9,4),
            merchant_raw="Unknown Vendor",merchant_normalized="Unknown Vendor",
            description="purchase",amount=-75,category="Other",category_confidence=.5)
        s.add(d);s.commit(); did=d.id
    dd=client.post(f"/api/v015/autonomy/transactions/{did}",json={}).json()
    assert dd["route"]=="OWNER_QUESTION", dd
    assert dd["weakest_material_factor"]=="profile_assignment"

    print({
      "clean_expense":da["route"],
      "mixed_use":db["route"],
      "capital_judgment":dc["route"],
      "unknown_profile":dd["route"],
      "clean_confidence":da["confidence"]
    })
