
import os,tempfile,json
tmp=tempfile.NamedTemporaryFile(suffix=".db",delete=False);tmp.close()
os.environ["DATABASE_URL"]="sqlite:///"+tmp.name
from fastapi.testclient import TestClient
from app.main import app

with TestClient(app) as c:
    cases=[
      ("expense",{"amount":-113,"description":"Office supplies","category":"Office Supplies"},
       {"transaction_type":"expense","recoverable_tax_amount":13},True),
      ("revenue",{"amount":1130,"description":"Client invoice paid"},
       {"transaction_type":"revenue","sales_tax_amount":130},True),
      ("transfer",{"amount":-500,"description":"Transfer to savings"},
       {"transaction_type":"transfer","transfer_target_account":"Savings"},True),
      ("loan",{"amount":-1000,"description":"Mortgage payment"},
       {"transaction_type":"loan_payment","principal_amount":800,"interest_amount":200,"liability_account":"Mortgage Payable"},True),
      ("payroll",{"amount":-3800,"description":"Payroll"},
       {"transaction_type":"payroll","gross_pay":5000,"net_pay":3800,"employee_withholdings":1200,"employer_payroll_cost":400},True),
      ("asset",{"amount":-1130,"description":"Equipment purchase"},
       {"transaction_type":"fixed_asset","recoverable_tax_amount":130,"asset_account":"Equipment","capital_class":"Class candidate"},True),
      ("owner_contribution",{"amount":2500,"description":"Owner contribution"},
       {"transaction_type":"owner_contribution"},True),
      ("owner_draw",{"amount":-750,"description":"Owner draw"},
       {"transaction_type":"owner_draw"},True),
    ]
    out={}
    for name,tx,facts,expected in cases:
        r=c.post("/api/v027/journal/build",json={"transaction":tx,"facts":facts}).json()
        assert r["balanced"] is expected,(name,r)
        assert r["debits"]==r["credits"],(name,r)
        out[name]={"balanced":r["balanced"],"debits":r["debits"],"credits":r["credits"],"lines":r["lines"]}

    missing=c.post("/api/v027/journal/build",json={
      "transaction":{"amount":-1000,"description":"Mortgage payment"},
      "facts":{"transaction_type":"loan_payment"}
    }).json()
    assert missing["balanced"] is False
    assert set(missing["missing_facts"])=={"principal_amount","interest_amount"}

    mismatch=c.post("/api/v027/journal/build",json={
      "transaction":{"amount":-1000,"description":"Loan payment"},
      "facts":{"transaction_type":"loan_payment","principal_amount":700,"interest_amount":200}
    }).json()
    assert mismatch["review_required"] is True

    print(json.dumps({
      "case_count":len(cases),
      "all_balanced":all(v["balanced"] for v in out.values()),
      "loan_missing_facts":missing["missing_facts"],
      "mismatched_loan_review_required":mismatch["review_required"],
      "sample_payroll":out["payroll"],
      "sample_revenue":out["revenue"]
    }))
