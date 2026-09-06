
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
    rental=next(p for p in profiles if p["profile_type"]=="rental")

    # First contractor job: roof restoration, confirmed current repair.
    with SessionLocal() as s:
        base=s.query(Transaction).first()
        t1=Transaction(
            household_id=base.household_id,profile_id=rental["id"],provider="test",
            provider_transaction_id="roof-1",tx_date=date(2026,9,1),
            merchant_raw="ABC Contracting",merchant_normalized="ABC Contracting",
            description="replace wind damaged shingles same materials",
            amount=-2875,category="Repairs",category_confidence=.8
        )
        s.add(t1);s.flush()
        s.add(Evidence(
            household_id=base.household_id,transaction_id=t1.id,provider="test",
            evidence_type="invoice",merchant="ABC Contracting",amount=2875,evidence_date=date(2026,9,1),
            subject="Roof repair invoice",excerpt="replace damaged shingles with same materials restore original condition"
        ))
        s.commit();t1id=t1.id

    learn=client.post(f"/api/v014/accounting-precedent/transactions/{t1id}/learn",json={
        "item_type":"repair",
        "restores_original_condition":True,
        "improves_beyond_original_condition":False,
        "lasting_benefit":False,
        "personal_component_present":False,
        "final_treatment":"rental_current_expense_candidate",
        "account_or_category":"Repairs",
        "rationale":"Restored storm-damaged shingles using same materials and function."
    })
    assert learn.status_code==200, learn.text

    # Similar roof repair should reuse precedent.
    with SessionLocal() as s:
        base=s.query(Transaction).first()
        t2=Transaction(
            household_id=base.household_id,profile_id=rental["id"],provider="test",
            provider_transaction_id="roof-2",tx_date=date(2026,9,10),
            merchant_raw="ABC Contracting",merchant_normalized="ABC Contracting",
            description="repair damaged shingles same material",
            amount=-2650,category="Repairs",category_confidence=.75
        )
        s.add(t2);s.flush()
        s.add(Evidence(
            household_id=base.household_id,transaction_id=t2.id,provider="test",
            evidence_type="invoice",merchant="ABC Contracting",amount=2650,evidence_date=date(2026,9,10),
            subject="Roof repair invoice",excerpt="repair damaged shingles same materials restore original condition"
        ))
        s.commit();t2id=t2.id

    m2=client.post(f"/api/v014/accounting-precedent/transactions/{t2id}/match",json={
        "item_type":"repair","restores_original_condition":True,
        "improves_beyond_original_condition":False,"lasting_benefit":False,
        "personal_component_present":False
    }).json()
    assert m2["action"]=="apply_precedent", m2
    assert m2["match"]["treatment"]=="rental_current_expense_candidate"

    # Same contractor, but bathroom renovation/improvement: precedent MUST NOT apply.
    with SessionLocal() as s:
        base=s.query(Transaction).first()
        t3=Transaction(
            household_id=base.household_id,profile_id=rental["id"],provider="test",
            provider_transaction_id="reno-1",tx_date=date(2026,9,15),
            merchant_raw="ABC Contracting",merchant_normalized="ABC Contracting",
            description="bathroom gut renovation upgraded finishes",
            amount=-8400,category="Repairs",category_confidence=.7
        )
        s.add(t3);s.flush()
        s.add(Evidence(
            household_id=base.household_id,transaction_id=t3.id,provider="test",
            evidence_type="invoice",merchant="ABC Contracting",amount=8400,evidence_date=date(2026,9,15),
            subject="Bathroom renovation",excerpt="gut bathroom upgrade tile vanity fixtures improved finishes"
        ))
        s.commit();t3id=t3.id

    m3=client.post(f"/api/v014/accounting-precedent/transactions/{t3id}/match",json={
        "item_type":"repair","restores_original_condition":False,
        "improves_beyond_original_condition":True,"lasting_benefit":True,
        "personal_component_present":False
    }).json()
    assert m3["action"]=="no_precedent", m3

    # Accounting endpoint should expose strong precedent for t2.
    ev=client.post(f"/api/v011/accounting/transactions/{t2id}/evaluate",json={
        "item_type":"repair","restores_original_condition":True,
        "improves_beyond_original_condition":False,"lasting_benefit":False,
        "personal_component_present":False
    }).json()
    assert ev["precedent"]["action"]=="apply_precedent"

    print({
      "similar_repair":m2["action"],
      "similar_repair_score":m2["match"]["score"],
      "similar_repair_treatment":m2["match"]["treatment"],
      "same_vendor_improvement":m3["action"],
      "accounting_endpoint_precedent":ev["precedent"]["action"]
    })
