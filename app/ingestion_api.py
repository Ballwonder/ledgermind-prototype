
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Any
from .personal_service import ensure_demo_household
from .ingestion import ingest_event,list_ingest_events

router=APIRouter(prefix="/api/v024/ingest",tags=["LedgerMind v0.24 ingest"])

class IngestIn(BaseModel):
    connector_type:str
    event_type:str
    profile_id:int|None=None
    payload:dict[str,Any]
    auto_process:bool=True

@router.post("")
def ingest(payload:IngestIn):
    return ingest_event(ensure_demo_household(),payload.connector_type,payload.event_type,payload.payload,payload.profile_id,payload.auto_process)

@router.get("/events")
def events():
    return {"events":list_ingest_events(ensure_demo_household())}
