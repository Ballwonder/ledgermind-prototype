
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any

@dataclass
class JournalLine:
    account:str
    debit:float=0.0
    credit:float=0.0
    memo:str|None=None

@dataclass
class JournalDecision:
    transaction_type:str
    lines:list[JournalLine]
    balanced:bool
    review_required:bool
    missing_facts:list[str]
    warnings:list[str]
    rationale:list[str]

def _bal(lines):
    d=round(sum(x.debit for x in lines),2)
    c=round(sum(x.credit for x in lines),2)
    return d==c

def _expense(amount, expense_account, cash_account, tax_amount=0.0, recoverable_tax_account="GST/HST Recoverable"):
    gross=abs(float(amount))
    tax=max(0.0,float(tax_amount or 0))
    net=round(gross-tax,2)
    lines=[]
    if net:
        lines.append(JournalLine(expense_account,debit=net))
    if tax:
        lines.append(JournalLine(recoverable_tax_account,debit=tax))
    lines.append(JournalLine(cash_account,credit=gross))
    return lines

def build_journal(transaction:dict[str,Any],facts:dict[str,Any]|None=None):
    facts=facts or {}
    amount=float(transaction.get("amount") or 0)
    desc=(transaction.get("description") or "").lower()
    category=transaction.get("category") or "Uncategorized Expense"
    source_account=transaction.get("source_account") or ("Cash/Bank" if amount>=0 else "Cash/Bank")
    ttype=facts.get("transaction_type")

    if not ttype:
        if "transfer" in desc:
            ttype="transfer"
        elif any(k in desc for k in ["loan payment","mortgage payment"]):
            ttype="loan_payment"
        elif any(k in desc for k in ["payroll","pay run","wages"]):
            ttype="payroll"
        elif any(k in desc for k in ["owner contribution","shareholder contribution"]):
            ttype="owner_contribution"
        elif any(k in desc for k in ["owner draw","shareholder draw","distribution"]):
            ttype="owner_draw"
        elif amount>0:
            ttype="revenue"
        else:
            ttype="expense"

    warnings=[];missing=[];rationale=[];review=False;lines=[]

    if ttype=="transfer":
        target=facts.get("transfer_target_account")
        if not target:
            missing.append("transfer_target_account")
            return JournalDecision(ttype,[],False,False,missing,warnings,["Transfer requires both sides/accounts."])
        gross=abs(amount)
        if amount<0:
            lines=[JournalLine(target,debit=gross),JournalLine(source_account,credit=gross)]
        else:
            lines=[JournalLine(source_account,debit=gross),JournalLine(target,credit=gross)]
        rationale.append("Transfer moves value between balance-sheet accounts without creating income or expense.")

    elif ttype=="loan_payment":
        gross=abs(amount)
        principal=facts.get("principal_amount")
        interest=facts.get("interest_amount")
        if principal is None or interest is None:
            missing += [x for x,v in [("principal_amount",principal),("interest_amount",interest)] if v is None]
            return JournalDecision(ttype,[],False,False,missing,warnings,["Loan/mortgage payment must be split between principal and interest before autonomous posting."])
        principal=float(principal);interest=float(interest)
        if round(principal+interest,2)!=round(gross,2):
            warnings.append("Principal + interest does not equal cash payment.")
            review=True
        lines=[JournalLine(facts.get("liability_account","Loan Payable"),debit=principal),
               JournalLine(facts.get("interest_account","Interest Expense"),debit=interest),
               JournalLine(source_account,credit=gross)]
        rationale.append("Principal reduces the liability; interest is expensed separately.")

    elif ttype=="payroll":
        gross=facts.get("gross_pay")
        net=facts.get("net_pay")
        emp_tax=facts.get("employee_withholdings")
        employer_cost=facts.get("employer_payroll_cost")
        if gross is None or net is None:
            missing += [x for x,v in [("gross_pay",gross),("net_pay",net)] if v is None]
            return JournalDecision(ttype,[],False,False,missing,warnings,["Payroll requires finalized provider totals."])
        gross=float(gross);net=float(net);emp_tax=float(emp_tax or (gross-net));employer_cost=float(employer_cost or 0)
        lines=[
            JournalLine("Wages Expense",debit=gross),
            JournalLine("Payroll Liabilities",credit=emp_tax),
            JournalLine(source_account,credit=net)
        ]
        if employer_cost:
            lines += [JournalLine("Employer Payroll Expense",debit=employer_cost),
                      JournalLine("Payroll Liabilities",credit=employer_cost)]
        rationale.append("Payroll journal uses finalized payroll-provider totals, separating wage expense, net cash, and payroll liabilities.")

    elif ttype=="fixed_asset":
        gross=abs(amount)
        tax=float(facts.get("recoverable_tax_amount") or 0)
        cost=round(gross-tax,2)
        asset=facts.get("asset_account") or "Property, Plant & Equipment"
        lines=[JournalLine(asset,debit=cost)]
        if tax: lines.append(JournalLine("GST/HST Recoverable",debit=tax))
        lines.append(JournalLine(source_account,credit=gross))
        rationale.append("Capital purchase is recorded to an asset account rather than current expense.")
        if not facts.get("capital_class"):
            warnings.append("Capital class/useful-life treatment remains unresolved.")
            review=True

    elif ttype=="owner_contribution":
        gross=abs(amount)
        equity=facts.get("equity_account") or "Owner/Shareholder Contributions"
        lines=[JournalLine(source_account,debit=gross),JournalLine(equity,credit=gross)]
        rationale.append("Owner/shareholder contribution is equity/funding, not revenue.")

    elif ttype=="owner_draw":
        gross=abs(amount)
        equity=facts.get("equity_account") or "Owner Draws / Shareholder Receivable"
        lines=[JournalLine(equity,debit=gross),JournalLine(source_account,credit=gross)]
        rationale.append("Owner draw/distribution is not a business expense.")

    elif ttype=="revenue":
        gross=abs(amount)
        tax=float(facts.get("sales_tax_amount") or 0)
        net=round(gross-tax,2)
        lines=[JournalLine(source_account,debit=gross),
               JournalLine(facts.get("revenue_account","Revenue"),credit=net)]
        if tax:
            lines.append(JournalLine("GST/HST Payable",credit=tax))
        rationale.append("Revenue separates sales tax collected from earned revenue when tax amount is known.")

    else: # expense
        gross=abs(amount)
        tax=float(facts.get("recoverable_tax_amount") or 0)
        lines=_expense(gross,facts.get("expense_account") or category,source_account,tax)
        rationale.append("Operating expense journal separates recoverable GST/HST when the validated amount is known.")

    return JournalDecision(ttype,lines,_bal(lines),review,missing,warnings,rationale)

def payload(x):
    d=asdict(x)
    d["debits"]=round(sum(i["debit"] for i in d["lines"]),2)
    d["credits"]=round(sum(i["credit"] for i in d["lines"]),2)
    return d
