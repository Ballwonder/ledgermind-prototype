
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel
from dataclasses import asdict
from .personal_service import ensure_demo_household
from .statement_matching_v030 import ingest_statement_lines,match_statement

router=APIRouter(prefix="/api/v030/statements",tags=["LedgerMind v0.30 statement matching"])
class LinesIn(BaseModel):
    lines:list[dict]

@router.post("/{statement_id}/lines")
def add_lines(statement_id:int,x:LinesIn):
    try:return {"line_ids":ingest_statement_lines(ensure_demo_household(),statement_id,x.lines)}
    except KeyError:raise HTTPException(404,"Statement not found")

@router.post("/{statement_id}/match")
def run_match(statement_id:int):
    try:return asdict(match_statement(ensure_demo_household(),statement_id))
    except KeyError:raise HTTPException(404,"Statement not found")
