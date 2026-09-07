
from __future__ import annotations
from dataclasses import dataclass,asdict
from datetime import datetime,date
import re
from sqlalchemy import select
from .data_model import SessionLocal,Transaction,Evidence
from .document_validator import persist_validation

@dataclass
class ExtractedDocument:
    supplier_name:str|None
    invoice_or_tax_date:str|None
    total_amount:float|None
    gst_hst_indication:bool|None
    supplier_gst_hst_number:str|None
    buyer_name:str|None
    description:str|None
    payment_terms:str|None
    mixed_tax_status:bool=False
    supply_tax_status:str|None=None
    extraction_confidence:float=0.0
    field_confidence:dict|None=None
    gst_hst_amount:float|None=None
    tax_disclosure_status:str="not_found"
    donation_indicator:bool=False
    charity_or_nonprofit_indicator:bool=False
    subtotal_amount:float|None=None
    tax_rate:float|None=None
    tax_calculation_basis:str|None=None

def _money_candidates(text:str):
    vals=[]
    for m in re.finditer(r'(?<!\d)(?:\$|CAD\s*)?(\d{1,5}(?:,\d{3})*(?:\.\d{2}))(?!\d)',text,re.I):
        try: vals.append(float(m.group(1).replace(",","")))
        except: pass
    return vals

def extract_document_fields(subject:str|None,body:str|None):
    text=((subject or "")+"\n"+(body or "")).strip()
    lines=[x.strip() for x in text.splitlines() if x.strip()]
    field_conf={}
    supplier=None
    if lines:
        supplier=re.sub(r'(?i)\b(invoice|receipt|statement)\b.*$','',lines[0]).strip(" -:")
        if supplier:
            field_conf["supplier_name"]=.80

    # explicit supplier/vendor lines override header guess
    mm=re.search(r'(?im)^(?:supplier|vendor|merchant)\s*[:\-]\s*(.+)$',text)
    if mm:
        supplier=mm.group(1).strip();field_conf["supplier_name"]=.98

    date_val=None
    dm=re.search(r'(?i)\b(?:invoice\s*date|date|paid\s*on)\s*[:\-]?\s*((?:20\d{2}[-/]\d{1,2}[-/]\d{1,2})|(?:\d{1,2}[-/]\d{1,2}[-/]20\d{2}))',text)
    if dm:
        date_val=dm.group(1);field_conf["invoice_or_tax_date"]=.95

    total=None
    tm=re.search(r'(?i)\b(?:total|amount\s*due|amount\s*paid|grand\s*total)\s*[:\-]?\s*(?:CAD\s*)?\$?\s*(\d[\d,]*\.\d{2})',text)
    if tm:
        total=float(tm.group(1).replace(",",""));field_conf["total_amount"]=.98
    else:
        vals=_money_candidates(text)
        if vals:
            total=max(vals);field_conf["total_amount"]=.65

    reg=None
    rm=re.search(r'(?i)\b(?:GST/HST|HST|GST)\s*(?:registration|reg(?:istration)?\.?|#|number|no\.?)?\s*[:#]?\s*(\d{9}\s*[A-Z]{2}\s*\d{4})',text)
    if not rm:
        rm=re.search(r'\b(\d{9}\s*(?:RT)\s*\d{4})\b',text,re.I)
    if rm:
        reg=re.sub(r'\s+','',rm.group(1).upper());field_conf["supplier_gst_hst_number"]=.99

    tax_amount=None
    subtotal=None
    subtotal_match=re.search(r'(?i)\bsub[- ]?total\s*[:\-]?\s*(?:CAD\s*)?\$?\s*(\d[\d,]*\.\d{2})',text)
    if subtotal_match:
        subtotal=float(subtotal_match.group(1).replace(",",""));field_conf["subtotal_amount"]=.98
    rate_match=re.search(r'(?i)\b(?:HST|GST|GST/HST)\s*(?:@|at)?\s*(\d{1,2}(?:\.\d+)?)\s*%',text)
    tax_rate=float(rate_match.group(1))/100 if rate_match else None
    tax_match=re.search(r'(?i)\b(?:HST|GST|GST/HST)\b\s*(?:amount|total)?\s*[:\-]?\s*(?:CAD\s*)?\$?\s*(\d[\d,]*\.\d{2})',text)
    tax_included=bool(re.search(r'(?i)(?:includes?|including|incl\.?|tax[- ]included).{0,18}\b(?:HST|GST|GST/HST)\b|\b(?:HST|GST|GST/HST)\b.{0,18}(?:included|incl\.?)(?:\s|$)',text))
    tax_additional=bool(re.search(r'(?i)(?:plus|add|additional|extra|\+)\s*(?:applicable\s*)?(?:HST|GST|GST/HST)|(?:HST|GST|GST/HST)\s*(?:extra|additional|applies)',text))
    if tax_match:
        tax_amount=float(tax_match.group(1).replace(",",""))
        gst_ind=True;tax_status="explicit_amount";tax_basis="receipt_tax_line";field_conf["gst_hst_indication"]=.99;field_conf["gst_hst_amount"]=.99
    elif subtotal is not None and total is not None and total>subtotal and re.search(r'(?i)\b(?:HST|GST|GST/HST|tax)\b',text):
        tax_amount=round(total-subtotal,2)
        gst_ind=True;tax_status="subtotal_total_difference";tax_basis="labelled_subtotal_to_total_difference";field_conf["gst_hst_indication"]=.90;field_conf["gst_hst_amount"]=.85
    elif tax_included:
        gst_ind=True;tax_status="included_in_total";tax_basis="tax_included_wording";field_conf["gst_hst_indication"]=.95
    elif tax_additional:
        gst_ind=True;tax_status="tax_stated_additional";tax_basis="plus_tax_wording";field_conf["gst_hst_indication"]=.90
    elif reg:
        gst_ind=None;tax_status="registration_number_only";tax_basis="registration_number_only"
    else:
        gst_ind=None;tax_status="not_found";tax_basis=None

    donation=bool(re.search(r'(?i)\b(?:official donation receipt|charitable donation|eligible amount of (?:the )?gift|donation)\b',text))
    charity_nonprofit=donation or bool(re.search(r'(?i)\b(?:registered charity|charitable registration|non[- ]?profit|not[- ]for[- ]profit)\b',text))

    buyer=None
    bm=re.search(r'(?im)^(?:bill\s*to|customer|client|buyer)\s*[:\-]\s*(.+)$',text)
    if bm:
        buyer=bm.group(1).strip();field_conf["buyer_name"]=.95

    terms=None
    pm=re.search(r'(?im)^(?:payment\s*terms|terms|paid\s*via|payment\s*method)\s*[:\-]\s*(.+)$',text)
    if pm:
        terms=pm.group(1).strip();field_conf["payment_terms"]=.92

    desc=None
    xm=re.search(r'(?im)^(?:description|item|service)\s*[:\-]\s*(.+)$',text)
    if xm:
        desc=xm.group(1).strip();field_conf["description"]=.92

    expected=["supplier_name","invoice_or_tax_date","total_amount"]
    base=sum(field_conf.get(k,0) for k in expected)/len(expected)
    return ExtractedDocument(
        supplier_name=supplier,invoice_or_tax_date=date_val,total_amount=total,
        gst_hst_indication=gst_ind,supplier_gst_hst_number=reg,
        buyer_name=buyer,description=desc,payment_terms=terms,
        extraction_confidence=round(base,3),field_confidence=field_conf
        ,gst_hst_amount=tax_amount,tax_disclosure_status=tax_status,
        donation_indicator=donation,charity_or_nonprofit_indicator=charity_nonprofit,
        subtotal_amount=subtotal,tax_rate=tax_rate,tax_calculation_basis=tax_basis
    )

def _norm(s): return re.sub(r'[^a-z0-9]+',' ',(s or "").lower()).strip()

def match_document_to_transactions(household_id:int,doc:ExtractedDocument,max_candidates:int=5):
    with SessionLocal() as s:
        txs=s.scalars(select(Transaction).where(Transaction.household_id==household_id)).all()
        ranked=[]
        for tx in txs:
            score=0.0;reasons=[]
            if doc.total_amount is not None:
                delta=abs(abs(float(tx.amount))-abs(float(doc.total_amount)))
                if delta < .01: score+=.55;reasons.append("exact amount")
                elif delta <= max(1.0,abs(doc.total_amount)*.02): score+=.25;reasons.append("near amount")
            merchant=_norm(tx.merchant_normalized or tx.merchant_raw)
            supplier=_norm(doc.supplier_name)
            if supplier and merchant:
                if supplier==merchant or supplier in merchant or merchant in supplier:
                    score+=.25;reasons.append("merchant")
            if doc.invoice_or_tax_date:
                try:
                    ds=str(doc.invoice_or_tax_date).replace("/","-")
                    dd=datetime.fromisoformat(ds).date()
                    days=abs((tx.tx_date-dd).days)
                    if days==0: score+=.15;reasons.append("same date")
                    elif days<=3: score+=.10;reasons.append("date proximity")
                    elif days<=7: score+=.05
                except: pass
            ranked.append({"transaction_id":tx.id,"score":round(min(score,1),3),
                           "merchant":tx.merchant_normalized or tx.merchant_raw,
                           "amount":tx.amount,"date":str(tx.tx_date),"reasons":reasons})
        ranked.sort(key=lambda x:x["score"],reverse=True)
        return ranked[:max_candidates]

def ingest_document(household_id:int,subject:str|None,body:str|None,auto_link_threshold:float=.85):
    doc=extract_document_fields(subject,body)
    matches=match_document_to_transactions(household_id,doc)
    top=matches[0] if matches else None
    linked=None;validation=None
    if top and top["score"]>=auto_link_threshold:
        linked=top["transaction_id"]
        with SessionLocal() as s:
            ev=Evidence(household_id=household_id,transaction_id=linked,provider="document_extractor",
                evidence_type="invoice_or_receipt",merchant=doc.supplier_name,
                amount=doc.total_amount,evidence_date=None,subject=subject,excerpt=body)
            s.add(ev);s.commit()
        if doc.total_amount is not None:
            validation=persist_validation(household_id,linked,asdict(doc))
    return {
        "extracted":asdict(doc),"matches":matches,"auto_linked_transaction_id":linked,
        "document_validation":asdict(validation) if validation else None
    }
