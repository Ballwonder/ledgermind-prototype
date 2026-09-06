
from datetime import datetime
from sqlalchemy import select
from .data_model import SessionLocal,ProcessingJob,AccountingException
from .event_processor import process_ingest_event

def enqueue(household_id,event_id):
    key=f"ingest:{event_id}:primary"
    with SessionLocal() as s:
        j=s.scalar(select(ProcessingJob).where(ProcessingJob.job_key==key))
        if j: return j.id
        j=ProcessingJob(household_id=household_id,ingest_event_id=event_id,job_key=key)
        s.add(j);s.commit();s.refresh(j);return j.id

def _sync_exception(hh,event_id,result):
    txid=result.get("transaction_id"); route=result.get("route")
    if not txid:return
    with SessionLocal() as s:
        openx=s.scalar(select(AccountingException).where(
            AccountingException.household_id==hh,
            AccountingException.transaction_id==txid,
            AccountingException.state.in_(["OPEN","REVIEW"])
        ).order_by(AccountingException.id.desc()))
        if route=="AUTO_FINISH":
            if openx:
                openx.state="RESOLVED";openx.resolved_by_event_id=event_id
                openx.resolution_note="Later evidence/context allowed autonomous completion."
                openx.updated_at=datetime.utcnow()
        elif route in ("OWNER_QUESTION","PROFESSIONAL_REVIEW"):
            state="OPEN" if route=="OWNER_QUESTION" else "REVIEW"
            if openx:
                openx.state=state;openx.updated_at=datetime.utcnow()
            else:
                d=result.get("detail",{}).get("decision",{}) or {}
                x=AccountingException(household_id=hh,transaction_id=txid,
                    exception_type=route,state=state,
                    question=d.get("owner_question"),
                    review_reason=d.get("professional_review_reason"),
                    opened_by_event_id=event_id)
                s.add(x)
        s.commit()

def run_job(job_id,simulate_failure=False):
    with SessionLocal() as s:
        j=s.get(ProcessingJob,job_id)
        if not j: raise KeyError("job")
        if j.status=="SUCCEEDED":
            return {"job_id":j.id,"status":j.status,"attempts":j.attempts,"idempotent":True}
        if j.status=="DEAD":
            return {"job_id":j.id,"status":j.status,"attempts":j.attempts,"idempotent":True}
        j.status="RUNNING";j.attempts+=1;j.updated_at=datetime.utcnow();s.commit()
        hh,event_id,attempt,max_attempts=j.household_id,j.ingest_event_id,j.attempts,j.max_attempts
    try:
        if simulate_failure: raise RuntimeError("simulated transient failure")
        result=process_ingest_event(hh,event_id)
        _sync_exception(hh,event_id,result)
        with SessionLocal() as s:
            j=s.get(ProcessingJob,job_id);j.status="SUCCEEDED";j.last_error=None;j.updated_at=datetime.utcnow();s.commit()
        return {"job_id":job_id,"status":"SUCCEEDED","attempts":attempt,"result":result}
    except Exception as e:
        with SessionLocal() as s:
            j=s.get(ProcessingJob,job_id)
            j.last_error=str(e);j.status="DEAD" if j.attempts>=j.max_attempts else "RETRY"
            j.updated_at=datetime.utcnow();s.commit()
            status=j.status
        return {"job_id":job_id,"status":status,"attempts":attempt,"error":str(e)}

def exceptions(hh):
    with SessionLocal() as s:
        rows=s.scalars(select(AccountingException).where(AccountingException.household_id==hh).order_by(AccountingException.id)).all()
        return [{"id":x.id,"transaction_id":x.transaction_id,"type":x.exception_type,"state":x.state,
                 "question":x.question,"review_reason":x.review_reason,
                 "opened_by_event_id":x.opened_by_event_id,"resolved_by_event_id":x.resolved_by_event_id,
                 "resolution_note":x.resolution_note} for x in rows]
