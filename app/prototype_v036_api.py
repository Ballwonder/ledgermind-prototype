
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from datetime import date, datetime
import csv, io, os, json
from .personal_service import ensure_demo_household
from .data_model import SessionLocal,Transaction,FinancialProfile,SourceDocument
from .unified_engine_v035 import process_transaction, process_all

router=APIRouter(tags=["LedgerMind Working Prototype"])

@router.get("/prototype",response_class=HTMLResponse)
def prototype():
    here=os.path.dirname(__file__)
    return open(os.path.join(here,"templates","prototype_v038.html"),encoding="utf-8").read()

@router.get("/api/prototype/state")
def state():
    hh=ensure_demo_household()
    with SessionLocal() as s:
        txs=s.scalars(select(Transaction).where(Transaction.household_id==hh).order_by(Transaction.tx_date.desc(),Transaction.id.desc())).all()
        profiles=s.scalars(select(FinancialProfile).where(FinancialProfile.household_id==hh)).all()
        docs=s.scalars(select(SourceDocument).where(SourceDocument.household_id==hh)).all()
        return {
          "profiles":[{"id":p.id,"name":p.name,"profile_type":p.profile_type,"tax_regime":p.tax_regime} for p in profiles],
          "transactions":[{"id":t.id,"date":str(t.tx_date),"merchant":t.merchant_normalized or t.merchant_raw,
            "description":t.description,"amount":t.amount,"category":t.category,"profile_id":t.profile_id} for t in txs],
          "documents":len(docs),
          "connectors":{
            "csv_import":True,"receipt_upload":True,
            "plaid_ready":bool(os.getenv("PLAID_CLIENT_ID") and os.getenv("PLAID_SECRET")),
            "gmail_ready":bool(os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET")),
            "outlook_ready":bool(os.getenv("MICROSOFT_CLIENT_ID") and os.getenv("MICROSOFT_CLIENT_SECRET"))
          }
        }

@router.post("/api/prototype/import-csv")
async def import_csv(file:UploadFile=File(...)):
    hh=ensure_demo_household()
    raw=await file.read()
    text=raw.decode("utf-8-sig")
    rows=list(csv.DictReader(io.StringIO(text)))
    made=[]
    with SessionLocal() as s:
        for i,r in enumerate(rows):
            d=(r.get("date") or r.get("Date") or "").strip()
            desc=(r.get("description") or r.get("Description") or r.get("merchant") or r.get("Merchant") or "Imported transaction").strip()
            amt=float((r.get("amount") or r.get("Amount") or "0").replace(",",""))
            ext=(r.get("id") or r.get("ID") or f"csv:{file.filename}:{i}:{d}:{amt}:{desc}")[:250]
            existing=s.scalar(select(Transaction).where(Transaction.household_id==hh,Transaction.provider=="csv",Transaction.provider_transaction_id==ext))
            if existing: continue
            tx=Transaction(household_id=hh,provider="csv",provider_transaction_id=ext,
                tx_date=date.fromisoformat(d[:10]),merchant_raw=desc,merchant_normalized=desc,
                description=desc,amount=amt,category="Uncategorized",category_confidence=0.0)
            s.add(tx);s.flush();made.append(tx.id)
        s.commit()
    return {"imported":len(made),"transaction_ids":made}

@router.post("/api/prototype/upload-receipt")
async def upload_receipt(file:UploadFile=File(...), profile_id:int|None=Form(None)):
    hh=ensure_demo_household()
    raw=await file.read()
    try:text=raw.decode("utf-8")
    except:text=f"Uploaded file: {file.filename}"
    with SessionLocal() as s:
        doc=SourceDocument(household_id=hh,profile_id=profile_id,source_type="upload",
            source_value=file.filename or "upload",folder_or_label="Manual Upload",
            subject=file.filename or "Receipt",body=text[:20000],received_at=datetime.utcnow(),processed=False)
        s.add(doc);s.commit();s.refresh(doc)
        return {"source_document_id":doc.id,"filename":file.filename}

@router.post("/api/prototype/process/{tx_id}")
def process(tx_id:int):
    hh=ensure_demo_household()
    try:return process_transaction(hh,tx_id,{})
    except KeyError:raise HTTPException(404,"Transaction not found")

@router.post("/api/prototype/process-all")
def process_everything():
    hh=ensure_demo_household()
    rows=process_all(hh)
    summary={"processed":len(rows),"fully_ready":0,"books_ready_tax_hold":0,"owner_question":0,"professional_review":0,"errors":0}
    for r in rows:
        if "error" in r: summary["errors"]+=1;continue
        d=r["decision"]; status=d["overall_status"]
        if status=="FULLY_READY":summary["fully_ready"]+=1
        elif status=="BOOKS_READY_TAX_HOLD":summary["books_ready_tax_hold"]+=1
        elif status=="OWNER_QUESTION":summary["owner_question"]+=1
        elif status=="PROFESSIONAL_REVIEW":summary["professional_review"]+=1
    return {"summary":summary,"results":rows}
