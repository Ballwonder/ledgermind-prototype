
from fastapi import APIRouter
from pydantic import BaseModel
from .personal_service import ensure_demo_household
from .document_extraction import extract_document_fields,match_document_to_transactions,ingest_document
from dataclasses import asdict

router=APIRouter(prefix="/api/v022/document-ingest",tags=["LedgerMind v0.22 document ingest"])

class RawDocument(BaseModel):
    subject:str|None=None
    body:str|None=None

@router.post("/extract")
def extract(payload:RawDocument):
    return asdict(extract_document_fields(payload.subject,payload.body))

@router.post("/ingest")
def ingest(payload:RawDocument):
    return ingest_document(ensure_demo_household(),payload.subject,payload.body)
