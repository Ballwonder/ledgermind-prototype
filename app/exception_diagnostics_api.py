
from fastapi import APIRouter
from .personal_service import ensure_demo_household
from .exception_diagnostics import diagnose_latest_run
router=APIRouter(prefix="/api/v019/diagnostics",tags=["LedgerMind v0.19 diagnostics"])

@router.get("/exceptions")
def diagnose():
    return diagnose_latest_run(ensure_demo_household())
