
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel
from .personal_service import ensure_demo_household
from .evidence_retrieval import retrieve_for_transaction,retrieve_all_unresolved
from .data_model import SessionLocal,SourceDocument
from dataclasses import asdict

router=APIRouter(prefix="/api/v023/retrieval",tags=["LedgerMind v0.23 retrieval"])

class SourceDocumentIn(BaseModel):
    profile_id:int|None=None
    source_type:str="email"
    source_value:str|None=None
    folder_or_label:str|None=None
    subject:str|None=None
    body:str|None=None

@router.post("/source-documents")
def add_doc(payload:SourceDocumentIn):
    hh=ensure_demo_household()
    with SessionLocal() as s:
        d=SourceDocument(household_id=hh,**payload.model_dump())
        s.add(d);s.commit();s.refresh(d)
        return {"id":d.id}

@router.post("/transactions/{transaction_id}")
def retrieve_one(transaction_id:int):
    try:
        return asdict(retrieve_for_transaction(ensure_demo_household(),transaction_id))
    except KeyError:
        raise HTTPException(404,"Transaction not found")

@router.post("/run")
def retrieve_all():
    return retrieve_all_unresolved(ensure_demo_household())
