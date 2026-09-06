
from app.accounting_decision_engine import evaluate_transaction

tx={"amount":-1000,"category":"Office Equipment","merchant":"Example Vendor"}

profiles=[
 {"profile_type":"personal","tax_regime":"personal_finance","gst_hst_registered":False},
 {"profile_type":"sole_proprietor","tax_regime":"T2125","gst_hst_registered":True},
 {"profile_type":"rental","tax_regime":"T776","gst_hst_registered":False},
 {"profile_type":"corporation","tax_regime":"T2_GIFI","gst_hst_registered":True},
]

durable={"item_type":"durable_asset","lasting_benefit":True}
results={p["profile_type"]:evaluate_transaction(p,tx,durable) for p in profiles}
assert results["personal"].treatment=="personal_spending"
assert results["sole_proprietor"].treatment=="capital_asset_candidate"
assert results["sole_proprietor"].capital_review is True
assert results["rental"].treatment=="rental_capital_candidate"
assert results["corporation"].treatment=="corporate_capital_asset_candidate"

mixed=evaluate_transaction(
 {"profile_type":"sole_proprietor","tax_regime":"T2125","gst_hst_registered":True},
 tx,{"personal_component_present":True}
)
assert mixed.owner_question is not None

corp_personal=evaluate_transaction(
 {"profile_type":"corporation","tax_regime":"T2_GIFI","gst_hst_registered":True},
 tx,{"personal_component_present":True}
)
assert corp_personal.treatment=="shareholder_or_employee_benefit_review"
assert corp_personal.review_required is True

rental_repair=evaluate_transaction(
 {"profile_type":"rental","tax_regime":"T776","gst_hst_registered":False},
 {"amount":-2875,"category":"Repairs","merchant":"Contractor"},
 {"restores_original_condition":True}
)
assert rental_repair.treatment=="rental_current_expense_candidate"
assert rental_repair.review_required is False

print({
 "same_1000_purchase":{
   k:{"treatment":v.treatment,"review":v.review_required,"tax_regime":v.tax_regime}
   for k,v in results.items()
 },
 "sole_prop_mixed_use_question":mixed.owner_question,
 "corporate_personal_treatment":corp_personal.treatment,
 "rental_restoration_treatment":rental_repair.treatment
})
