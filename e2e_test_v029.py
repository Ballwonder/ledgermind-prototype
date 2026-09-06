
import os,tempfile,json
from datetime import date
tmp=tempfile.NamedTemporaryFile(suffix=".db",delete=False);tmp.close()
os.environ["DATABASE_URL"]="sqlite:///"+tmp.name
from fastapi.testclient import TestClient
from app.main import app
from app.data_model import SessionLocal,Transaction

with TestClient(app) as c:
    c.post("/api/v09/reset")
    # isolate by creating period outside seeded demo month
    with SessionLocal() as s:
        base=s.query(Transaction).first()
        hh=base.household_id
        txs=[
          Transaction(household_id=hh,provider="test",provider_transaction_id="r1",tx_date=date(2027,1,1),
            merchant_raw="Employer",merchant_normalized="Employer",description="Payroll Deposit",amount=1000,category="Income",category_confidence=.99),
          Transaction(household_id=hh,provider="test",provider_transaction_id="r2",tx_date=date(2027,1,2),
            merchant_raw="Grocer",merchant_normalized="Grocer",description="Groceries",amount=-200,category="Groceries",category_confidence=.99),
          Transaction(household_id=hh,provider="test",provider_transaction_id="r3",tx_date=date(2027,1,3),
            merchant_raw="Transfer",merchant_normalized="Transfer",description="Transfer to savings",amount=-300,category="Transfer",category_confidence=.99),
          Transaction(household_id=hh,provider="test",provider_transaction_id="r4",tx_date=date(2027,1,3),
            merchant_raw="Transfer",merchant_normalized="Transfer",description="Transfer from chequing",amount=300,category="Transfer",category_confidence=.99),
        ]
        s.add_all(txs);s.commit()

    st=c.post("/api/v029/reconciliation/statements",json={
      "account_name":"Chequing","period_start":"2027-01-01","period_end":"2027-01-31",
      "opening_balance":500,"closing_balance":1300
    }).json()["statement_id"]
    good=c.post(f"/api/v029/reconciliation/statements/{st}/run").json()
    assert good["ties"] is True,good
    assert good["difference"]==0
    assert good["transfer_pair_count"]==1
    assert good["close_blocking"] is False

    # Add duplicate; should block even if balance adjusted to include only first copy.
    with SessionLocal() as s:
        base=s.query(Transaction).first();hh=base.household_id
        s.add(Transaction(household_id=hh,provider="test",provider_transaction_id="dup",tx_date=date(2027,1,2),
          merchant_raw="Grocer",merchant_normalized="Grocer",description="Groceries duplicate",amount=-200,category="Groceries",category_confidence=.99))
        s.commit()
    dup=c.post(f"/api/v029/reconciliation/statements/{st}/run").json()
    assert dup["duplicate_count"]==1,dup
    assert dup["close_blocking"] is True,dup

    # Statement mismatch blocks close.
    st2=c.post("/api/v029/reconciliation/statements",json={
      "account_name":"Savings","period_start":"2027-01-01","period_end":"2027-01-31",
      "opening_balance":0,"closing_balance":9999
    }).json()["statement_id"]
    bad=c.post(f"/api/v029/reconciliation/statements/{st2}/run").json()
    assert bad["ties"] is False,bad
    assert bad["close_blocking"] is True,bad

    recs=c.get(f"/api/v029/reconciliation/statements/{st}/records").json()["records"]
    assert any(r["status"]=="TRANSFER_PAIRED" for r in recs)
    assert any(r["status"]=="DUPLICATE_SUSPECT" for r in recs)

    print(json.dumps({
      "good_ties":good["ties"],
      "good_difference":good["difference"],
      "transfer_pairs":good["transfer_pair_count"],
      "duplicate_detected":dup["duplicate_count"],
      "duplicate_blocks_close":dup["close_blocking"],
      "mismatch_difference":bad["difference"],
      "mismatch_blocks_close":bad["close_blocking"],
      "record_statuses":sorted(set(r["status"] for r in recs))
    }))
