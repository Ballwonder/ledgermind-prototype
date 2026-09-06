
import os,tempfile,json
from datetime import date
tmp=tempfile.NamedTemporaryFile(suffix=".db",delete=False);tmp.close()
os.environ["DATABASE_URL"]="sqlite:///"+tmp.name
from fastapi.testclient import TestClient
from app.main import app
from app.data_model import SessionLocal,Transaction

with TestClient(app) as c:
    c.post("/api/v09/reset")
    with SessionLocal() as s:
        hh=s.query(Transaction).first().household_id
        s.add_all([
          Transaction(household_id=hh,provider="test",provider_transaction_id="m1",tx_date=date(2027,3,1),
            merchant_raw="Employer",merchant_normalized="Employer",description="Payroll Deposit",amount=1000,category="Income",category_confidence=.99),
          Transaction(household_id=hh,provider="test",provider_transaction_id="m2",tx_date=date(2027,3,2),
            merchant_raw="Cheque",merchant_normalized="Cheque",description="Cheque 1042",amount=-100,category="Other",category_confidence=.99),
        ]);s.commit()

    st=c.post("/api/v029/reconciliation/statements",json={
      "account_name":"Chequing","period_start":"2027-03-01","period_end":"2027-03-31",
      "opening_balance":0,"closing_balance":885
    }).json()["statement_id"]

    c.post(f"/api/v030/statements/{st}/lines",json={"lines":[
      {"external_id":"x1","date":"2027-03-01","description":"Employer payroll deposit","amount":1000},
      {"external_id":"x2","date":"2027-03-05","description":"Monthly bank fee","amount":-15}
    ]})
    before=c.post(f"/api/v030/statements/{st}/match").json()
    assert before["bank_only_count"]==1 and before["book_only_count"]==1,before

    props=c.post(f"/api/v031/reconciliation-actions/statements/{st}/propose").json()["actions"]
    types=sorted(p["action_type"] for p in props)
    assert "PROPOSE_MISSING_LEDGER_ENTRY" in types,props
    assert "MARK_OUTSTANDING" in types,props

    applied=c.post(f"/api/v031/reconciliation-actions/statements/{st}/apply-safe").json()
    assert any(a["action_type"]=="CREATE_LEDGER_TRANSACTION" for a in applied["applied"]),applied
    assert any(a["action_type"]=="MARK_OUTSTANDING" for a in applied["applied"]),applied

    after=c.post(f"/api/v030/statements/{st}/match").json()
    assert after["bank_only_count"]==0,after
    assert after["book_only_count"]==1,after  # outstanding cheque is still not on bank statement; that's expected timing difference

    print(json.dumps({
      "before_bank_only":before["bank_only_count"],
      "before_book_only":before["book_only_count"],
      "proposal_types":types,
      "applied_actions":applied["applied"],
      "after_bank_only":after["bank_only_count"],
      "after_book_only":after["book_only_count"],
      "after_close_blocking":after["close_blocking"]
    }))
