
import os,tempfile,json
from datetime import date
tmp=tempfile.NamedTemporaryFile(suffix=".db",delete=False);tmp.close()
os.environ["DATABASE_URL"]="sqlite:///"+tmp.name
from fastapi.testclient import TestClient
from app.main import app
from app.data_model import SessionLocal,Transaction,FinancialProfile,Evidence

with TestClient(app) as c:
    c.post("/api/v09/reset")
    profiles=c.get("/api/v010/profiles").json()["profiles"]
    personal=next(p for p in profiles if p["profile_type"]=="personal")

    # Personal linked-feed transactions already have sufficient evidence in current evidence engine.
    with SessionLocal() as s:
        base=s.query(Transaction).first()
        t1=Transaction(household_id=base.household_id,profile_id=personal["id"],provider="test",
            provider_transaction_id="v28-transfer",tx_date=date(2026,9,6),
            merchant_raw="Transfer",merchant_normalized="Transfer",description="Transfer to savings",
            amount=-500,category="Transfer",category_confidence=.99)
        t2=Transaction(household_id=base.household_id,profile_id=personal["id"],provider="test",
            provider_transaction_id="v28-mortgage",tx_date=date(2026,9,6),
            merchant_raw="Mortgage",merchant_normalized="Mortgage",description="Mortgage payment",
            amount=-1000,category="Housing",category_confidence=.99)
        s.add_all([t1,t2]);s.commit();ids=(t1.id,t2.id)

    transfer=c.post(f"/api/v028/autonomy/transactions/{ids[0]}",json={"transaction_type":"transfer","transfer_target_account":"Savings"}).json()
    assert transfer["final_route"]=="AUTO_FINISH",transfer
    assert transfer["journal_status"]=="ready",transfer

    mortgage_missing=c.post(f"/api/v028/autonomy/transactions/{ids[1]}",json={"transaction_type":"loan_payment"}).json()
    assert mortgage_missing["final_route"]=="OWNER_QUESTION",mortgage_missing
    assert set(mortgage_missing["missing_facts"])=={"principal_amount","interest_amount"},mortgage_missing

    mortgage_good=c.post(f"/api/v028/autonomy/transactions/{ids[1]}",json={
      "transaction_type":"loan_payment","principal_amount":800,"interest_amount":200,
      "liability_account":"Mortgage Payable"
    }).json()
    assert mortgage_good["final_route"]=="AUTO_FINISH",mortgage_good
    assert mortgage_good["journal"]["debits"]==mortgage_good["journal"]["credits"],mortgage_good

    mortgage_bad=c.post(f"/api/v028/autonomy/transactions/{ids[1]}",json={
      "transaction_type":"loan_payment","principal_amount":700,"interest_amount":200,
      "liability_account":"Mortgage Payable"
    }).json()
    assert mortgage_bad["final_route"]=="PROFESSIONAL_REVIEW",mortgage_bad
    assert mortgage_bad["journal_status"]=="unbalanced",mortgage_bad

    print(json.dumps({
      "transfer_route":transfer["final_route"],
      "transfer_journal_balanced":transfer["journal"]["balanced"],
      "mortgage_missing_route":mortgage_missing["final_route"],
      "mortgage_missing_facts":mortgage_missing["missing_facts"],
      "mortgage_complete_route":mortgage_good["final_route"],
      "mortgage_complete_balanced":mortgage_good["journal"]["balanced"],
      "mortgage_mismatch_route":mortgage_bad["final_route"],
      "mortgage_mismatch_review_reasons":mortgage_bad["review_reasons"]
    }))
