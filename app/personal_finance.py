
from collections import defaultdict
from datetime import datetime
import re

CATEGORY_RULES = [
    ("Housing", ["mortgage","rent","property tax","condo"]),
    ("Utilities", ["hydro","electric","gas bill","enbridge","water","internet","rogers","bell"]),
    ("Groceries", ["grocery","loblaws","walmart","food basics","metro","costco"]),
    ("Restaurants", ["restaurant","cafe","coffee","pizza","uber eats","doordash"]),
    ("Transportation", ["gas station","esso","shell","petro","parking","transit","uber"]),
    ("Insurance", ["insurance"]),
    ("Subscriptions", ["netflix","spotify","subscription","prime"]),
    ("Shopping", ["amazon","staples","best buy","home depot"]),
    ("Income", ["payroll","salary","deposit"]),
    ("Transfers", ["transfer","payment"]),
]

FIXED = {"Housing","Utilities","Insurance","Subscriptions"}

def categorize(description: str, amount: float):
    t=(description or "").lower()
    for cat, terms in CATEGORY_RULES:
        if any(x in t for x in terms):
            return cat
    return "Other"

def summarize(transactions):
    by_cat=defaultdict(float)
    income=0.0
    spending=0.0
    for tx in transactions:
        amount=float(tx["amount"])
        cat=categorize(tx.get("description",""), amount)
        if amount > 0 and cat == "Income":
            income += amount
        elif amount < 0:
            by_cat[cat] += abs(amount)
            spending += abs(amount)
    fixed=sum(v for k,v in by_cat.items() if k in FIXED)
    discretionary=max(0, spending-fixed)
    return {
        "income": round(income,2),
        "spending": round(spending,2),
        "net_cash_flow": round(income-spending,2),
        "fixed": round(fixed,2),
        "discretionary": round(discretionary,2),
        "categories": dict(sorted(by_cat.items(), key=lambda x:x[1], reverse=True))
    }

def recurring_candidates(transactions):
    groups=defaultdict(list)
    for tx in transactions:
        if float(tx["amount"]) < 0:
            merchant=re.sub(r"\d+","",tx.get("merchant") or tx.get("description","")).strip().lower()
            groups[merchant].append(abs(float(tx["amount"])))
    out=[]
    for merchant, vals in groups.items():
        if len(vals)>=2 and merchant:
            avg=sum(vals)/len(vals)
            variance=max(abs(x-avg) for x in vals)/avg if avg else 1
            if variance <= .15:
                out.append({"merchant":merchant.title(),"occurrences":len(vals),"average":round(avg,2)})
    return sorted(out,key=lambda x:x["average"],reverse=True)
