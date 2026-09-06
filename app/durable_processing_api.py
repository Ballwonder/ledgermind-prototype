
from fastapi import APIRouter,HTTPException
from .personal_service import ensure_demo_household
from .durable_processing import enqueue,run_job,exceptions
router=APIRouter(prefix="/api/v026",tags=["LedgerMind v0.26 durable processing"])
@router.post("/events/{event_id}/enqueue")
def q(event_id:int): return {"job_id":enqueue(ensure_demo_household(),event_id)}
@router.post("/jobs/{job_id}/run")
def run(job_id:int):
    try:return run_job(job_id)
    except KeyError:raise HTTPException(404,"Job not found")
@router.get("/exceptions")
def ex():return {"exceptions":exceptions(ensure_demo_household())}
