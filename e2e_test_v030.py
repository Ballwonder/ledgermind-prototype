
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
          Transaction(household_id=hh,provider="test",provider_transaction_id="b1",tx_date=date(2027,2,1),merchant_raw="Employer",merchant_normalized="Employer",description="Payroll Deposit",amount=1000,category="Income",category_confidence=.99),
          Transaction(household_id=hh,provider="test",provider_transaction_id="b2",tx_date=date(2027,2,2),merchant_raw="Grocer",merchant_normalized="Grocer",description="Groceries",amount=-200,category="Groceries",category_confidence=.99),
          Transaction(household_id=hh,provider="test",provider_transaction_id="b3",tx_date=date(2027,2,4),merchant_raw="Rent",merchant_normalized="Rent",description="Rent",amount=-500,category="Housing",category_confidence=.99),
        ]);s.commit()

    st=c.post("/api/v029/reconciliation/statements",json={"account_name":"Chequing","period_start":"2027-02-01","period_end":"2027-02-28","opening_balance":0,"closing_balance":300}).json()["statement_id"]
    c.post(f"/api/v030/statements/{st}/lines",json={"lines":[
      {"external_id":"s1","date":"2027-02-01","description":"Employer payroll deposit","amount":1000},
      {"external_id":"s2","date":"2027-02-02","description":"Grocer groceries","amount":-200},
      {"external_id":"s3","date":"2027-02-04","description":"Rent","amount":-500}
    ]})
    good=c.post(f"/api/v030/statements/{st}/match").json()
    assert good["matched_count"]==3 and good["close_blocking"] is False,good

    c.post(f"/api/v030/statements/{st}/lines",json={"lines":[
      {"external_id":"s4","date":"2027-02-05","description":"Monthly bank fee","amount":-15}
    ]})
    bank_only=c.post(f"/api/v030/statements/{st}/match").json()
    assert bank_only["bank_only_count"]==1 and bank_only["close_blocking"] is True,bank_only

    with SessionLocal() as s:
        hh=s.query(Transaction).first().household_id
        s.add(Transaction(household_id=hh,provider="test",provider_transaction_id="b4",tx_date=date(2027,2,10),merchant_raw="Cheque",merchant_normalized="Cheque",description="Outstanding cheque",amount=-50,category="Other",category_confidence=.99));s.commit()
    both=c.post(f"/api/v030/statements/{st}/match").json()
    assert both["bank_only_count"]==1 and both["book_only_count"]==1,both

    c.post(f"/api/v030/statements/{st}/lines",json={"lines":[
      {"external_id":"s2dup","date":"2027-02-02","description":"Grocer groceries","amount":-200}
    ]})
    dup=c.post(f"/api/v030/statements/{st}/match").json()
    assert dup["duplicate_statement_line_count"]==1,dup

    print(json.dumps({
      "clean_match_count":good["matched_count"],
      "clean_close_blocking":good["close_blocking"],
      "bank_only_count":bank_only["bank_only_count"],
      "book_only_count":both["book_only_count"],
      "duplicate_statement_line_count":dup["duplicate_statement_line_count"],
      "final_close_blocking":dup["close_blocking"],
      "final_statuses":sorted(set(x["status"] for x in dup["matches"]))
    }))
