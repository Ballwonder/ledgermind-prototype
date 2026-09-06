
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel
from typing import Any
from .personal_service import ensure_demo_household
from .document_validator import validate_document,persist_validation,latest_validation,payload

router=APIRouter(prefix="/api/v021/documents",tags=["LedgerMind v0.21 documents"])

class DocumentFields(BaseModel):
    supplier_name:str|None=None
    invoice_or_tax_date:str|None=None
    total_amount:float
    gst_hst_indication:bool|str|None=None
    mixed_tax_status:bool=False
    supply_tax_status:str|None=None
    supplier_gst_hst_number:str|None=None
    buyer_name:str|None=None
    description:str|None=None
    payment_terms:str|None=None

@router.post("/validate")
def validate(payload_:DocumentFields):
    return payload(validate_document(payload_.model_dump()))

@router.post("/transactions/{transaction_id}/validate")
def validate_tx(transaction_id:int,payload_:DocumentFields):
    try:
        return payload(persist_validation(ensure_demo_household(),transaction_id,payload_.model_dump()))
    except KeyError:
        raise HTTPException(404,"Transaction not found")

@router.get("/transactions/{transaction_id}/latest")
def latest(transaction_id:int):
    r=latest_validation(ensure_demo_household(),transaction_id)
    if not r: raise HTTPException(404,"No document validation found")
    return payload(r)
