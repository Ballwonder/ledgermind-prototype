
from app.data_model import create_schema, SessionLocal, Evidence, Transaction
from app.personal_service import ensure_demo_household
from app.ingestion_pipeline import normalize_merchant, deterministic_category, match_unlinked_evidence, detect_anomalies
from datetime import date

create_schema()
hh=ensure_demo_household()
assert normalize_merchant("COSTCO #1234")=="Costco"
assert deterministic_category("Food Basics","purchase")=="Groceries"
with SessionLocal() as s:
    existing=s.query(Evidence).filter(Evidence.household_id==hh,Evidence.provider=="smoke").first()
    if not existing:
        s.add(Evidence(household_id=hh,provider="smoke",evidence_type="receipt",merchant="Amazon",amount=119.99,evidence_date=date(2026,9,5),subject="Amazon receipt"))
        s.commit()
matches=match_unlinked_evidence(hh)
anoms=detect_anomalies(hh)
print({"household_id":hh,"evidence_matches":matches,"anomalies":anoms})
