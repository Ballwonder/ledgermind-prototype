
import os,tempfile,json,io
tmp=tempfile.NamedTemporaryFile(suffix=".db",delete=False);tmp.close()
os.environ["DATABASE_URL"]="sqlite:///"+tmp.name
from fastapi.testclient import TestClient
from app.main import app

with TestClient(app) as c:
    c.post("/api/v09/reset")
    page=c.get("/prototype")
    assert page.status_code==200 and "LedgerMind" in page.text

    state=c.get("/api/prototype/state").json()
    assert state["connectors"]["csv_import"] is True
    assert state["connectors"]["receipt_upload"] is True

    csv_data=b"date,description,amount,id\n2027-06-01,Client payment,1500,s1\n2027-06-02,Monthly bank fee,-15,s2\n"
    imp=c.post("/api/prototype/import-csv",files={"file":("test.csv",csv_data,"text/csv")}).json()
    assert imp["imported"]==2,imp

    receipt=c.post("/api/prototype/upload-receipt",
        files={"file":("receipt.txt",b"Supplier: Staples\nDate: 2027-06-02\nTotal: 15.00\nDescription: office item","text/plain")}).json()
    assert receipt["source_document_id"]>0,receipt

    state2=c.get("/api/prototype/state").json()
    assert len(state2["transactions"])>=2

    run=c.post("/api/prototype/process-all").json()
    assert "summary" in run
    assert run["summary"]["processed"]==len(state2["transactions"])

    print(json.dumps({
      "prototype_page":page.status_code,
      "csv_imported":imp["imported"],
      "receipt_document_id":receipt["source_document_id"],
      "transactions_after_import":len(state2["transactions"]),
      "process_summary":run["summary"],
      "connector_readiness":state2["connectors"]
    }))
