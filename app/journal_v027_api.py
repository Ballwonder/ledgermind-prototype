
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Any
from .journal_engine_v027 import build_journal,payload

router=APIRouter(prefix="/api/v027/journal",tags=["LedgerMind v0.27 journal"])

class JournalRequest(BaseModel):
    transaction:dict[str,Any]
    facts:dict[str,Any]={}

@router.post("/build")
def build(req:JournalRequest):
    return payload(build_journal(req.transaction,req.facts))
