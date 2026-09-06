
from fastapi import APIRouter,HTTPException
from .personal_service import ensure_demo_household
from .event_processor import process_ingest_event,processing_history

router=APIRouter(prefix="/api/v025/events",tags=["LedgerMind v0.25 events"])

@router.post("/{ingest_event_id}/process")
def process(ingest_event_id:int):
    try:
        return process_ingest_event(ensure_demo_household(),ingest_event_id)
    except KeyError:
        raise HTTPException(404,"Ingest event not found")

@router.get("/history")
def history():
    return {"history":processing_history(ensure_demo_household())}
