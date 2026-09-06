
import os,tempfile,json
tmp=tempfile.NamedTemporaryFile(suffix=".db",delete=False);tmp.close()
os.environ["DATABASE_URL"]="sqlite:///"+tmp.name
os.environ["ENABLE_LIVE_FINANCIAL_CONNECTORS"]="false"

from fastapi.testclient import TestClient
from app.main import app

with TestClient(app) as c:
    h=c.get("/health")
    assert h.status_code==200 and h.json()["status"]=="ok",h.text
    p=c.get("/prototype")
    assert p.status_code==200 and "LedgerMind" in p.text
    d=c.get("/docs")
    assert d.status_code==200
    s=c.get("/api/prototype/state")
    assert s.status_code==200
    print(json.dumps({
      "health":h.json(),
      "prototype_status":p.status_code,
      "docs_status":d.status_code,
      "state_status":s.status_code
    }))
