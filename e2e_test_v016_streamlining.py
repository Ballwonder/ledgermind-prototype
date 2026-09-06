
import os,tempfile
tmp=tempfile.NamedTemporaryFile(suffix=".db",delete=False);tmp.close()
os.environ["DATABASE_URL"]="sqlite:///"+tmp.name
from fastapi.testclient import TestClient
from app.main import app
from app.data_model import SessionLocal, Transaction

with TestClient(app) as client:
    client.post("/api/v09/reset")
    profiles=client.get("/api/v010/profiles").json()["profiles"]
    sole=next(p for p in profiles if p["profile_type"]=="sole_proprietor")
    rental=next(p for p in profiles if p["profile_type"]=="rental")

    # Dedicated accounting email + folder.
    r=client.post("/api/v016/source-maps",json={
        "profile_id":sole["id"],"source_type":"email",
        "source_value":"accounting@example.test","folder_or_label":"Business Receipts",
        "trust_level":"dedicated"})
    assert r.status_code==200
    resolved=client.post("/api/v016/source-maps/resolve",json={
        "source_type":"email","source_value":"accounting@example.test",
        "folder_or_label":"Business Receipts"}).json()
    assert resolved["candidates"][0]["profile_id"]==sole["id"]
    assert resolved["candidates"][0]["confidence"]>=.99

    # Same email but wrong folder is not blindly trusted.
    wrong=client.post("/api/v016/source-maps/resolve",json={
        "source_type":"email","source_value":"accounting@example.test",
        "folder_or_label":"Personal"}).json()
    assert wrong["candidates"][0]["confidence"]<=.70

    # Recurring Rogers treatment.
    rr=client.post("/api/v016/recurring-rules",json={
        "profile_id":sole["id"],"merchant":"Rogers","category":"Utilities",
        "treatment":"current_business_expense_candidate","business_use_pct":0.70,
        "expected_amount":226,"amount_tolerance_pct":0.15,"cadence":"monthly"})
    assert rr.status_code==200

    txs=client.get("/api/v07/transactions").json()
    rogers=next(t for t in txs if t["merchant"]=="Rogers")
    client.post(f"/api/v010/profiles/transactions/{rogers['id']}/assign",json={"profile_id":sole["id"]})
    match=client.get(f"/api/v016/recurring-rules/match/{rogers['id']}").json()
    assert match["matches"] and match["matches"][0]["business_use_pct"]==0.70

    q=client.get("/api/v016/exception-queue")
    assert q.status_code==200
    payload=q.json()
    assert "exceptions" in payload

    print({
      "mapped_email_confidence":resolved["candidates"][0]["confidence"],
      "wrong_folder_confidence":wrong["candidates"][0]["confidence"],
      "recurring_rogers_business_use":match["matches"][0]["business_use_pct"],
      "exception_queue_count":payload["count"]
    })
