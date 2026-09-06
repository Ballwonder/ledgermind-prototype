
from __future__ import annotations
from dataclasses import dataclass,asdict
import json,re
from sqlalchemy import select
from .data_model import SessionLocal,DocumentValidationRecord,Transaction

RULE_VERSION="CRA_ITC_2021_THRESHOLDS_v1"

@dataclass
class DocumentValidation:
    transaction_id:int|None
    total_sale:float
    threshold_band:str
    required_fields:list[str]
    present_fields:list[str]
    missing_fields:list[str]
    warnings:list[str]
    valid_for_itc_support:bool
    confidence:float
    rule_version:str=RULE_VERSION

def _truthy(v):
    return v is not None and (not isinstance(v,str) or bool(v.strip()))

def _band(total:float):
    if total < 100: return "under_100"
    if total < 500: return "100_to_499_99"
    return "500_plus"

def required_itc_fields(total:float, mixed_tax_status:bool=False):
    base=["supplier_name","invoice_or_tax_date","total_amount"]
    if total>=100:
        base += ["gst_hst_indication","supplier_gst_hst_number"]
        if mixed_tax_status:
            base += ["supply_tax_status"]
    if total>=500:
        base += ["buyer_name","description","payment_terms"]
    return base

def validate_document(fields:dict, transaction_id:int|None=None):
    total=float(fields.get("total_amount") or 0)
    mixed=bool(fields.get("mixed_tax_status"))
    req=required_itc_fields(total,mixed)
    missing=[k for k in req if not _truthy(fields.get(k))]
    present=[k for k in req if _truthy(fields.get(k))]
    warnings=[]

    reg=fields.get("supplier_gst_hst_number")
    if reg:
        digits=re.sub(r"\D","",str(reg))
        if len(digits)<9:
            warnings.append("Supplier GST/HST number appears shorter than the expected 9-digit business-number core.")
    if total>=100 and fields.get("gst_hst_indication") is False:
        missing.append("gst_hst_indication")
    missing=sorted(set(missing))

    valid=len(missing)==0
    conf=1.0 if valid and not warnings else (.92 if valid else max(.35,1-len(missing)*.12))
    return DocumentValidation(
        transaction_id=transaction_id,total_sale=round(total,2),
        threshold_band=_band(total),required_fields=req,present_fields=present,
        missing_fields=missing,warnings=warnings,
        valid_for_itc_support=valid,confidence=round(conf,3)
    )

def persist_validation(household_id:int,transaction_id:int,fields:dict):
    result=validate_document(fields,transaction_id)
    with SessionLocal() as s:
        tx=s.get(Transaction,transaction_id)
        if not tx or tx.household_id!=household_id: raise KeyError("transaction")
        rec=DocumentValidationRecord(
            household_id=household_id,transaction_id=transaction_id,purpose="itc_support",
            document_fields_json=json.dumps(fields,default=str),
            threshold_band=result.threshold_band,
            valid_for_itc_support=result.valid_for_itc_support,
            missing_fields_json=json.dumps(result.missing_fields),
            warnings_json=json.dumps(result.warnings),
            rule_version=result.rule_version
        )
        s.add(rec);s.commit();s.refresh(rec)
    return result

def latest_validation(household_id:int,transaction_id:int):
    with SessionLocal() as s:
        rec=s.scalar(select(DocumentValidationRecord).where(
            DocumentValidationRecord.household_id==household_id,
            DocumentValidationRecord.transaction_id==transaction_id
        ).order_by(DocumentValidationRecord.id.desc()))
        if not rec: return None
        fields=json.loads(rec.document_fields_json)
        return validate_document(fields,transaction_id)

def payload(x): return asdict(x)
