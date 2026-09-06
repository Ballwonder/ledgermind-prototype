
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from .personal_service import ensure_demo_household
from .autonomy_router import decide_autonomy, as_payload

router=APIRouter(prefix="/api/v015/autonomy",tags=["LedgerMind v0.15 autonomy"])

class Facts(BaseModel):
    item_type:str|None=None
    business_use_pct:float|None=None
    personal_component_present:bool=False
    lasting_benefit:bool=False
    restores_original_condition:bool=False
    improves_beyond_original_condition:bool=False

@router.post("/transactions/{transaction_id}")
def decide(transaction_id:int,payload:Facts):
    hh=ensure_demo_household()
    try:
        return as_payload(decide_autonomy(hh,transaction_id,payload.model_dump()))
    except KeyError:
        raise HTTPException(404,"Transaction not found")
