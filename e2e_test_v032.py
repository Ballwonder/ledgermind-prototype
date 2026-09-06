
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
   Transaction(household_id=hh,provider="test",provider_transaction_id="c1",tx_date=date(2027,4,1),merchant_raw="Employer",merchant_normalized="Employer",description="Payroll Deposit",amount=1000,category="Income",category_confidence=.99),
   Transaction(household_id=hh,provider="test",provider_transaction_id="c2",tx_date=date(2027,4,28),merchant_raw="Cheque",merchant_normalized="Cheque",description="Cheque 2001",amount=-100,category="Other",category_confidence=.99)
  ]);s.commit()
 st=c.post("/api/v029/reconciliation/statements",json={"account_name":"Chequing","period_start":"2027-04-01","period_end":"2027-04-30","opening_balance":0,"closing_balance":1000}).json()["statement_id"]
 c.post(f"/api/v030/statements/{st}/lines",json={"lines":[{"external_id":"a1","date":"2027-04-01","description":"Employer payroll deposit","amount":1000}]})
 m=c.post(f"/api/v030/statements/{st}/match").json(); assert m["book_only_count"]==1
 sync=c.post(f"/api/v032/outstanding/statements/{st}/sync").json(); assert len(sync["created"])==1,sync
 close=c.get(f"/api/v032/outstanding/statements/{st}/close-readiness").json()
 assert close["close_ready"] is True,close
 assert close["accepted_timing_differences"][0]["status"]=="ACCEPTABLE_OUTSTANDING"

 # next month: cheque clears and is matched to same book transaction
 st2=c.post("/api/v029/reconciliation/statements",json={"account_name":"Chequing","period_start":"2027-05-01","period_end":"2027-05-31","opening_balance":1000,"closing_balance":900}).json()["statement_id"]
 c.post(f"/api/v030/statements/{st2}/lines",json={"lines":[{"external_id":"b1","date":"2027-05-02","description":"Cheque 2001","amount":-100}]})
 # Current matcher only searches tx inside statement period, so add explicit carried-forward match record to model clearing.
 from app.data_model import SessionLocal,StatementLine,StatementMatch
 with SessionLocal() as s:
  tx=s.query(Transaction).filter(Transaction.provider_transaction_id=="c2").one()
  line=s.query(StatementLine).filter(StatementLine.statement_id==st2).one()
  s.add(StatementMatch(household_id=hh,statement_id=st2,statement_line_id=line.id,transaction_id=tx.id,status="MATCHED",score=.99,reason="Carried-forward outstanding matched on later statement."));s.commit()
 carried=c.post(f"/api/v032/outstanding/statements/{st2}/carry-forward").json()
 assert len(carried["cleared"])==1,carried

 print(json.dumps({"april_book_only":m["book_only_count"],"outstanding_created":len(sync["created"]),
  "april_close_ready":close["close_ready"],"accepted_timing_differences":len(close["accepted_timing_differences"]),
  "may_cleared":len(carried["cleared"]),"may_carried":len(carried["carried_forward"])}))
