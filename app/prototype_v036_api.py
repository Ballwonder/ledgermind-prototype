
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from pydantic import BaseModel
from datetime import date, datetime
import csv, io, os, json
import re
from .personal_service import ensure_demo_household
from .data_model import SessionLocal,Transaction,FinancialProfile,SourceDocument,AccountingException,Evidence,AuditEvent,OwnerFact,TransactionAnalysis
from .unified_engine_v035 import process_transaction, process_all
from .profile_assignment_engine import apply_profile_decision
from .document_extraction import ingest_document

router=APIRouter(tags=["LedgerMind Working Prototype"])

def _csv_value(row:dict,*names:str):
    normalized={str(k or "").strip().lower().replace("_"," "):str(v or "").strip() for k,v in row.items()}
    for name in names:
        value=normalized.get(name.lower().replace("_"," "))
        if value:
            return value
    return ""

def _csv_date(value:str)->date:
    cleaned=value.strip().split("T")[0]
    for fmt in ("%Y-%m-%d","%m/%d/%Y","%m/%d/%y","%d/%m/%Y","%d/%m/%y","%Y/%m/%d","%b %d, %Y","%B %d, %Y"):
        try:
            return datetime.strptime(cleaned,fmt).date()
        except ValueError:
            pass
    raise ValueError(f"unrecognized date '{value}'")

def _csv_money(value:str)->float:
    cleaned=value.strip().replace("$","").replace(",","").replace(" ","")
    negative=cleaned.startswith("(") and cleaned.endswith(")")
    cleaned=cleaned.strip("()")
    if not cleaned:
        return 0.0
    amount=float(cleaned)
    return -abs(amount) if negative else amount

class OwnerAnswerPayload(BaseModel):
    profile_id:int|None=None
    answer:str=""
    facts:dict[str,str|float|bool]|None=None
    remember:bool=True

ALLOWED_OWNER_FACTS={
    "transfer_target_account","principal_amount","interest_amount","liability_account","interest_account",
    "gross_pay","net_pay","employee_withholdings","employer_payroll_cost","recoverable_tax_amount",
    "asset_account","capital_class","equity_account","sales_tax_amount","revenue_account","expense_account",
    "business_use_pct","personal_component_present","lasting_benefit","restores_original_condition",
    "improves_beyond_original_condition","tax_document_validated"
}

def _sync_exception(hh:int,tx_id:int,decision:dict,resolution_note:str|None=None):
    status=decision.get("overall_status","ERROR")
    with SessionLocal() as s:
        current=s.scalar(select(AccountingException).where(
            AccountingException.household_id==hh,
            AccountingException.transaction_id==tx_id,
            AccountingException.state.in_(["OPEN","REVIEW"])
        ).order_by(AccountingException.id.desc()))
        if status in ("OWNER_QUESTION","PROFESSIONAL_REVIEW"):
            state="OPEN" if status=="OWNER_QUESTION" else "REVIEW"
            if current:
                current.state=state
                current.exception_type=status
                current.question=decision.get("owner_question")
                current.review_reason=decision.get("professional_review_reason")
                current.updated_at=datetime.utcnow()
            else:
                s.add(AccountingException(
                    household_id=hh,transaction_id=tx_id,exception_type=status,state=state,
                    question=decision.get("owner_question"),
                    review_reason=decision.get("professional_review_reason")
                ))
        elif current:
            current.state="RESOLVED"
            current.resolution_note=resolution_note or "New owner context allowed the transaction to be reprocessed."
            current.updated_at=datetime.utcnow()
        s.commit()

def _save_analysis(hh:int,tx_id:int,result:dict):
    decision=result.get("decision",{})
    with SessionLocal() as s:
        snapshot=s.scalar(select(TransactionAnalysis).where(
            TransactionAnalysis.household_id==hh,TransactionAnalysis.transaction_id==tx_id
        ))
        payload=json.dumps(result,default=str)
        if snapshot:
            snapshot.status=decision.get("overall_status","ERROR")
            snapshot.result_json=payload
            snapshot.analyzed_at=datetime.utcnow()
        else:
            s.add(TransactionAnalysis(
                household_id=hh,transaction_id=tx_id,
                status=decision.get("overall_status","ERROR"),result_json=payload
            ))
        s.commit()

@router.get("/prototype",response_class=HTMLResponse)
def prototype(request: Request):
    here=os.path.dirname(__file__)
    with open(os.path.join(here,"templates","prototype_v038.html"),encoding="utf-8") as template:
        page=template.read()
    return page.replace("__CSRF_TOKEN__", request.state.csrf)

@router.get("/api/prototype/state")
def state():
    hh=ensure_demo_household()
    with SessionLocal() as s:
        txs=s.scalars(select(Transaction).where(Transaction.household_id==hh).order_by(Transaction.tx_date.desc(),Transaction.id.desc())).all()
        profiles=s.scalars(select(FinancialProfile).where(FinancialProfile.household_id==hh)).all()
        docs=s.scalars(select(SourceDocument).where(SourceDocument.household_id==hh)).all()
        exceptions=s.scalars(select(AccountingException).where(
            AccountingException.household_id==hh,
            AccountingException.state.in_(["OPEN","REVIEW"])
        )).all()
        exception_by_tx={x.transaction_id:x for x in exceptions}
        snapshots=s.scalars(select(TransactionAnalysis).where(TransactionAnalysis.household_id==hh)).all()
        analysis_by_tx={x.transaction_id:json.loads(x.result_json) for x in snapshots}

        status_counts={
            "NEEDS_ANALYSIS":0,
            "FULLY_READY":0,
            "BOOKS_READY_TAX_HOLD":0,
            "OWNER_QUESTION":0,
            "PROFESSIONAL_REVIEW":0,
            "ERROR":0,
        }
        tx_rows=[]
        for t in txs:
            raw_status=(t.evidence_status or "none").upper()
            analysis_status = raw_status if raw_status in status_counts else "NEEDS_ANALYSIS"
            status_counts[analysis_status]=status_counts.get(analysis_status,0)+1
            latest=analysis_by_tx.get(t.id,{})
            decision=latest.get("decision",{})
            tx_rows.append({
                "id":t.id,"date":str(t.tx_date),"merchant":t.merchant_normalized or t.merchant_raw,
                "description":t.description,"amount":t.amount,"category":t.category,"profile_id":t.profile_id,
                "analysis_status":analysis_status,"category_confidence":float(t.category_confidence or 0),
                "owner_question":exception_by_tx[t.id].question if t.id in exception_by_tx else None,
                "analysis":{
                    "bookkeeping_route":decision.get("bookkeeping_route"),
                    "tax_route":decision.get("tax_route"),
                    "weakest_factor":decision.get("weakest_material_factor"),
                    "confidence":decision.get("confidence",{}),
                    "reasons":decision.get("reasons",[]),
                    "missing_facts":decision.get("missing_facts",[]),
                    "proposed_treatment":decision.get("proposed_treatment"),
                    "evidence_status":latest.get("retrieval",{}).get("status"),
                } if latest else None,
            })

        total=len(txs)
        ready=status_counts.get("FULLY_READY",0)
        unresolved=total-ready
        analyzed=total-status_counts.get("NEEDS_ANALYSIS",0)
        health_pct=round((ready/total)*100) if total else 100
        automation_pct=round((ready/analyzed)*100) if analyzed else 0

        return {
          "profiles":[{"id":p.id,"name":p.name,"profile_type":p.profile_type,"tax_regime":p.tax_regime} for p in profiles],
          "transactions":tx_rows,
          "documents":len(docs),
          "metrics":{
              "total":total,"ready":ready,"unresolved":unresolved,"analyzed":analyzed,
              "needs_analysis":status_counts.get("NEEDS_ANALYSIS",0),
              "owner_question":status_counts.get("OWNER_QUESTION",0),
              "professional_review":status_counts.get("PROFESSIONAL_REVIEW",0),
              "tax_hold":status_counts.get("BOOKS_READY_TAX_HOLD",0),
              "errors":status_counts.get("ERROR",0),
              "health_pct":health_pct,"automation_pct":automation_pct,
          },
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
    try:
        text=raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text=raw.decode("cp1252")
    rows=list(csv.DictReader(io.StringIO(text)))
    if not rows:
        raise HTTPException(400,"The CSV has no transaction rows")
    made=[]
    rejected=[]
    with SessionLocal() as s:
        for i,r in enumerate(rows):
            try:
                d=_csv_value(r,"date","transaction date","posted date","posting date")
                desc=_csv_value(r,"description","merchant","payee","name","details","transaction description") or "Imported transaction"
                amount_text=_csv_value(r,"amount","transaction amount")
                if amount_text:
                    amt=_csv_money(amount_text)
                else:
                    debit=_csv_money(_csv_value(r,"debit","withdrawal","money out"))
                    credit=_csv_money(_csv_value(r,"credit","deposit","money in"))
                    if not debit and not credit:
                        raise ValueError("no amount, debit, or credit value")
                    amt=abs(credit)-abs(debit)
                tx_date=_csv_date(d)
            except (ValueError,TypeError) as exc:
                rejected.append({"row":i+2,"reason":str(exc)})
                continue
            ext=(_csv_value(r,"id","transaction id","reference","reference number") or f"csv:{file.filename}:{i}:{d}:{amt}:{desc}")[:250]
            existing=s.scalar(select(Transaction).where(Transaction.household_id==hh,Transaction.provider=="csv",Transaction.provider_transaction_id==ext))
            if existing: continue
            tx=Transaction(household_id=hh,provider="csv",provider_transaction_id=ext,
                tx_date=tx_date,merchant_raw=desc,merchant_normalized=desc,
                description=desc,amount=amt,category="Uncategorized",category_confidence=0.0)
            s.add(tx);s.flush();made.append(tx.id)
        s.commit()
    if not made and rejected:
        example=rejected[0]
        raise HTTPException(400,f"No transactions could be imported. Row {example['row']}: {example['reason']}")
    return {"imported":len(made),"transaction_ids":made,"rejected":rejected,"rejected_count":len(rejected)}

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
        document_id=doc.id
    analysis=ingest_document(hh,None,text)
    linked=analysis.get("auto_linked_transaction_id")
    if linked:
        with SessionLocal() as s:
            doc=s.get(SourceDocument,document_id)
            doc.processed=True
            doc.matched_transaction_id=linked
            s.commit()
    extracted=analysis.get("extracted",{})
    extension=os.path.splitext(file.filename or "receipt.txt")[1].lower() or ".txt"
    safe_vendor=re.sub(r"[^a-zA-Z0-9]+","-",extracted.get("supplier_name") or "unknown-vendor").strip("-").lower()
    safe_date=str(extracted.get("invoice_or_tax_date") or "unknown-date").replace("/","-")
    total=extracted.get("total_amount")
    suggested_filename=f"{safe_date}_{safe_vendor}_{total:.2f}{extension}" if total is not None else f"{safe_date}_{safe_vendor}{extension}"
    return {
        "source_document_id":document_id,"filename":file.filename,
        "suggested_filename":suggested_filename,"extracted":extracted,
        "matches":analysis.get("matches",[]),"auto_linked_transaction_id":linked,
        "document_validation":analysis.get("document_validation")
    }

@router.post("/api/prototype/process/{tx_id}")
def process(tx_id:int):
    hh=ensure_demo_household()
    try:
        result=process_transaction(hh,tx_id,{})
        status=result.get("decision",{}).get("overall_status","ERROR")
        with SessionLocal() as s:
            tx=s.get(Transaction,tx_id)
            if tx and tx.household_id==hh:
                tx.evidence_status=status
                s.commit()
        _sync_exception(hh,tx_id,result.get("decision",{}))
        _save_analysis(hh,tx_id,result)
        return result
    except KeyError:
        raise HTTPException(404,"Transaction not found")

@router.post("/api/prototype/process-all")
def process_everything():
    hh=ensure_demo_household()
    with SessionLocal() as s:
        ids=[t.id for t in s.scalars(select(Transaction).where(Transaction.household_id==hh)).all()
             if (t.evidence_status or "none").upper() != "FULLY_READY"]

    rows=[]
    for tid in ids:
        try:
            r=process_transaction(hh,tid,{})
            rows.append(r)
            status=r.get("decision",{}).get("overall_status","ERROR")
        except Exception as e:
            rows.append({"transaction_id":tid,"error":str(e)})
            status="ERROR"
        with SessionLocal() as s:
            tx=s.get(Transaction,tid)
            if tx and tx.household_id==hh:
                tx.evidence_status=status
                s.commit()
        if "error" not in rows[-1]:
            _sync_exception(hh,tid,rows[-1].get("decision",{}))
            _save_analysis(hh,tid,rows[-1])

    summary={"processed":len(rows),"fully_ready":0,"books_ready_tax_hold":0,"owner_question":0,"professional_review":0,"errors":0}
    for r in rows:
        if "error" in r:
            summary["errors"]+=1
            continue
        d=r["decision"]; status=d["overall_status"]
        if status=="FULLY_READY":summary["fully_ready"]+=1
        elif status=="BOOKS_READY_TAX_HOLD":summary["books_ready_tax_hold"]+=1
        elif status=="OWNER_QUESTION":summary["owner_question"]+=1
        elif status=="PROFESSIONAL_REVIEW":summary["professional_review"]+=1
    return {"summary":summary,"results":rows}

@router.post("/api/prototype/transactions/{tx_id}/answer")
def answer_owner_question(tx_id:int,payload:OwnerAnswerPayload):
    hh=ensure_demo_household()
    answer=payload.answer.strip()
    facts={k:v for k,v in (payload.facts or {}).items() if k in ALLOWED_OWNER_FACTS and v not in (None,"")}
    if not answer and not facts:
        raise HTTPException(400,"Please provide the requested information")
    with SessionLocal() as s:
        tx=s.get(Transaction,tx_id)
        if not tx or tx.household_id!=hh:
            raise HTTPException(404,"Transaction not found")
        if tx.profile_id is None and payload.profile_id is None:
            raise HTTPException(400,"Select the financial profile this transaction belongs to")
        if payload.profile_id is not None:
            profile=s.get(FinancialProfile,payload.profile_id)
            if not profile or profile.household_id!=hh:
                raise HTTPException(400,"Select a valid financial profile")
    if payload.profile_id is not None:
        apply_profile_decision(hh,tx_id,payload.profile_id,learn=payload.remember)
    with SessionLocal() as s:
        tx=s.get(Transaction,tx_id)
        saved=s.scalar(select(OwnerFact).where(OwnerFact.household_id==hh,OwnerFact.transaction_id==tx_id))
        prior_facts=json.loads(saved.facts_json or "{}") if saved else {}
        combined_facts={**prior_facts,**facts}
        explanation=answer or "; ".join(f"{key.replace('_',' ')}: {value}" for key,value in facts.items())
        if saved:
            saved.answer=explanation
            saved.facts_json=json.dumps(combined_facts)
            saved.updated_at=datetime.utcnow()
        else:
            s.add(OwnerFact(household_id=hh,transaction_id=tx_id,answer=explanation,facts_json=json.dumps(combined_facts)))
        prior=s.scalar(select(Evidence).where(
            Evidence.household_id==hh,Evidence.transaction_id==tx_id,
            Evidence.provider=="owner",Evidence.subject=="Owner explanation"
        ).order_by(Evidence.id.desc()))
        if prior:
            prior.excerpt=explanation
            prior.amount=abs(tx.amount)
            prior.evidence_date=tx.tx_date
            prior.match_score=1.0
        else:
            s.add(Evidence(
                household_id=hh,transaction_id=tx_id,provider="owner",
                evidence_type="owner_explanation",merchant=tx.merchant_normalized or tx.merchant_raw,
                amount=abs(tx.amount),evidence_date=tx.tx_date,subject="Owner explanation",
                excerpt=explanation,match_score=1.0
            ))
        s.add(AuditEvent(
            household_id=hh,event_type="owner_question_answered",entity_type="transaction",
            entity_id=str(tx_id),detail_json=json.dumps({
                "profile_id":payload.profile_id,"answer":explanation,"facts":facts,"remember":payload.remember
            })
        ))
        s.commit()
    result=process_transaction(hh,tx_id,{"purpose_confirmed":True})
    status=result.get("decision",{}).get("overall_status","ERROR")
    with SessionLocal() as s:
        tx=s.get(Transaction,tx_id)
        tx.evidence_status=status
        s.commit()
    _sync_exception(hh,tx_id,result.get("decision",{}),resolution_note=explanation)
    _save_analysis(hh,tx_id,result)
    return {"saved":True,"status":status,"learned":bool(payload.profile_id and payload.remember),"result":result}
