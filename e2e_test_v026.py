
import os,tempfile,json
tmp=tempfile.NamedTemporaryFile(suffix=".db",delete=False);tmp.close()
os.environ["DATABASE_URL"]="sqlite:///"+tmp.name
from fastapi.testclient import TestClient
from app.main import app
from app.data_model import SessionLocal,FinancialProfile
from app.durable_processing import enqueue,run_job
with TestClient(app) as c:
 c.post("/api/v09/reset")
 ps=c.get("/api/v010/profiles").json()["profiles"]; sole=next(p for p in ps if p["profile_type"]=="sole_proprietor")
 with SessionLocal() as s:
  p=s.get(FinancialProfile,sole["id"]);p.gst_hst_registered=True;s.commit()
 bank=c.post("/api/v024/ingest",json={"connector_type":"plaid","event_type":"transaction","profile_id":sole["id"],
  "payload":{"transaction_id":"job-staples","date":"2026-09-06","merchant_name":"Staples","amount":226}}).json()
 assert bank["job"]["status"]=="SUCCEEDED"
 txid=bank["linked_transaction_id"]
 ex=c.get("/api/v026/exceptions").json()["exceptions"]; assert ex[-1]["state"]=="OPEN"
 email=c.post("/api/v024/ingest",json={"connector_type":"gmail","event_type":"message","profile_id":sole["id"],
  "payload":{"message_id":"job-mail","subject":"Staples invoice","body":"Supplier: Staples\\nInvoice Date: 2026-09-06\\nDescription: Office supplies\\nTotal: $226.00\\nHST: included\\nGST/HST Number: 123456789RT0001\\nPayment Terms: Paid by card"}}).json()
 assert email["processing"]["route"]=="AUTO_FINISH"
 ex2=c.get("/api/v026/exceptions").json()["exceptions"]; assert ex2[-1]["state"]=="RESOLVED"
 # retry state on a separately queued, non-auto-processed event
 raw=c.post("/api/v024/ingest",json={"connector_type":"payroll","event_type":"payroll_run","auto_process":False,
   "payload":{"id":"retry-test","gross_pay":100}}).json()
 jid=enqueue(1,raw["ingest_event_id"])
 fail=run_job(jid,simulate_failure=True);assert fail["status"]=="RETRY"
 ok=run_job(jid);assert ok["status"]=="SUCCEEDED" and ok["attempts"]==2
 again=run_job(jid);assert again["idempotent"] is True
 print(json.dumps({"initial_route":bank["processing"]["route"],"exception_initial":"OPEN",
  "later_route":email["processing"]["route"],"exception_final":ex2[-1]["state"],
  "retry_first":fail["status"],"retry_second":ok["status"],"attempts":ok["attempts"],
  "successful_job_idempotent":again["idempotent"]}))
