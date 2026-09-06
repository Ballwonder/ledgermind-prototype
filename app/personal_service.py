
from __future__ import annotations
from datetime import date, datetime
from sqlalchemy import select, func
from .data_model import (
    SessionLocal, Household, FinancialProfile, Account, Transaction, RecurringObligation,
    Goal, MerchantMemory, Correction, Insight, AuditEvent
)

FIXED_CATEGORIES={"Housing","Utilities","Insurance","Subscriptions"}

def ensure_demo_household():
    with SessionLocal() as s:
        hh=s.scalar(select(Household).limit(1))
        if hh:
            return hh.id
        hh=Household(name="Demo Household",currency="CAD")
        s.add(hh); s.flush()
        profiles=[
            FinancialProfile(household_id=hh.id,name="Personal Household",profile_type="personal",entity_type="individual",activity_type="personal",tax_regime="personal_finance",province="Ontario"),
            FinancialProfile(household_id=hh.id,name="Consulting — Sole Proprietor",profile_type="sole_proprietor",entity_type="individual",activity_type="business_or_professional",tax_regime="T2125",province="Ontario"),
            FinancialProfile(household_id=hh.id,name="Rental Property",profile_type="rental",entity_type="individual",activity_type="rental_property",tax_regime="T776",province="Ontario"),
            FinancialProfile(household_id=hh.id,name="Example Corporation",profile_type="corporation",entity_type="corporation",activity_type="business",tax_regime="T2_GIFI",province="Ontario"),
        ]
        s.add_all(profiles); s.flush()
        personal_profile=profiles[0]
        accounts=[
            Account(household_id=hh.id,profile_id=personal_profile.id,name="Chequing",account_type="depository",current_balance=4850,is_asset=True),
            Account(household_id=hh.id,profile_id=personal_profile.id,name="Savings",account_type="depository",current_balance=18200,is_asset=True),
            Account(household_id=hh.id,profile_id=personal_profile.id,name="Investments",account_type="investment",current_balance=41750,is_asset=True),
            Account(household_id=hh.id,profile_id=personal_profile.id,name="Home (estimated)",account_type="property",current_balance=460000,is_asset=True),
            Account(household_id=hh.id,profile_id=personal_profile.id,name="Mortgage",account_type="loan",current_balance=372000,is_asset=False),
            Account(household_id=hh.id,profile_id=personal_profile.id,name="Credit Card",account_type="credit",current_balance=1290,is_asset=False),
        ]
        s.add_all(accounts); s.flush()
        rows=[
            ("2026-09-01","Mortgage Payment","Housing",-1700,1.0),
            ("2026-09-01","Payroll Deposit","Income",3250,1.0),
            ("2026-09-02","Food Basics","Groceries",-126.42,.99),
            ("2026-09-02","Rogers","Utilities",-226,.92),
            ("2026-09-03","Hydro One","Utilities",-143.18,.99),
            ("2026-09-03","Netflix","Subscriptions",-22.59,.99),
            ("2026-09-04","Shell","Transportation",-78.33,.95),
            ("2026-09-04","Restaurant","Restaurants",-84.16,.82),
            ("2026-09-05","Amazon","Shopping",-119.99,.71),
            ("2026-09-05","Insurance","Insurance",-188,.98),
            ("2026-09-06","Costco","Groceries",-212.64,.86),
            ("2026-09-06","Interac Transfer","Transfers",-300,.67),
        ]
        for i,(d,m,c,a,conf) in enumerate(rows,1):
            s.add(Transaction(
                household_id=hh.id, profile_id=personal_profile.id, provider="demo", provider_transaction_id=f"demo-{i}",
                tx_date=date.fromisoformat(d), merchant_raw=m, merchant_normalized=m,
                description=m, amount=a, category=c, category_confidence=conf,
                excluded_from_spending=(c=="Transfers")
            ))
        obligations=[
            ("Mortgage Payment","Housing",1700,"biweekly","2026-09-15"),
            ("Rogers","Utilities",226,"monthly","2026-10-02"),
            ("Hydro One","Utilities",143.18,"monthly","2026-10-03"),
            ("Netflix","Subscriptions",22.59,"monthly","2026-10-03"),
            ("Insurance","Insurance",188,"monthly","2026-10-05"),
        ]
        for m,c,a,cd,n in obligations:
            s.add(RecurringObligation(household_id=hh.id,merchant=m,category=c,amount=a,cadence=cd,next_expected_date=date.fromisoformat(n)))
        for n,t,c in [("Emergency fund",20000,18200),("Travel fund",5000,2150),("Extra mortgage principal",10000,1250)]:
            s.add(Goal(household_id=hh.id,name=n,target_amount=t,current_amount=c))
        s.commit()
        return hh.id

def dashboard(household_id:int):
    with SessionLocal() as s:
        txs=s.scalars(select(Transaction).where(Transaction.household_id==household_id)).all()
        income=sum(t.amount for t in txs if t.amount>0 and t.category=="Income")
        outflows=[t for t in txs if t.amount<0 and not t.excluded_from_spending]
        spending=sum(abs(t.amount) for t in outflows)
        by={}
        for t in outflows: by[t.category]=round(by.get(t.category,0)+abs(t.amount),2)
        fixed=sum(v for k,v in by.items() if k in FIXED_CATEGORIES)
        accounts=s.scalars(select(Account).where(Account.household_id==household_id,Account.active==True)).all()
        assets=sum(a.current_balance for a in accounts if a.is_asset)
        debt=sum(a.current_balance for a in accounts if not a.is_asset)
        return {
            "income":round(income,2),"spending":round(spending,2),"net_cash_flow":round(income-spending,2),
            "fixed":round(fixed,2),"discretionary":round(spending-fixed,2),"categories":by,
            "assets":round(assets,2),"debt":round(debt,2),"net_worth":round(assets-debt,2),
            "needs_review":sum(1 for t in txs if t.category_confidence<.75)
        }

def list_transactions(household_id:int):
    with SessionLocal() as s:
        txs=s.scalars(select(Transaction).where(Transaction.household_id==household_id).order_by(Transaction.tx_date.desc(),Transaction.id.desc())).all()
        profiles={p.id:p for p in s.scalars(select(FinancialProfile).where(FinancialProfile.household_id==household_id)).all()}
        return [{
            "id":t.id,"date":t.tx_date.isoformat(),"merchant":t.merchant_normalized or t.merchant_raw,
            "description":t.description,"amount":t.amount,"category":t.category,
            "confidence":t.category_confidence,"recurring":t.recurring,"pending":t.pending,
            "profile_id":t.profile_id,
            "profile_name":profiles[t.profile_id].name if t.profile_id in profiles else None,
            "profile_type":profiles[t.profile_id].profile_type if t.profile_id in profiles else None,
            "tax_regime":profiles[t.profile_id].tax_regime if t.profile_id in profiles else None
        } for t in txs]

def correct_category(household_id:int, transaction_id:int, category:str, note:str|None=None):
    with SessionLocal() as s:
        tx=s.get(Transaction,transaction_id)
        if not tx or tx.household_id!=household_id: raise KeyError("transaction")
        old=tx.category
        tx.category=category; tx.category_confidence=1.0
        s.add(Correction(household_id=household_id,transaction_id=tx.id,field_name="category",old_value=old,new_value=category,note=note))
        merchant=(tx.merchant_normalized or tx.merchant_raw or "").strip()
        if merchant:
            mem=s.scalar(select(MerchantMemory).where(
                MerchantMemory.household_id==household_id,
                MerchantMemory.merchant_normalized==merchant
            ))
            if mem:
                mem.preferred_category=category; mem.times_confirmed+=1; mem.updated_at=datetime.utcnow()
            else:
                s.add(MerchantMemory(household_id=household_id,merchant_normalized=merchant,preferred_category=category))
        s.add(AuditEvent(household_id=household_id,event_type="category_corrected",entity_type="transaction",entity_id=str(tx.id),detail_json=f'{{"old":"{old}","new":"{category}"}}'))
        s.commit()
        return {"saved":True,"old_category":old,"new_category":category}

def wealth(household_id:int):
    with SessionLocal() as s:
        accounts=s.scalars(select(Account).where(Account.household_id==household_id,Account.active==True)).all()
        goals=s.scalars(select(Goal).where(Goal.household_id==household_id,Goal.status=="active")).all()
        obligations=s.scalars(select(RecurringObligation).where(RecurringObligation.household_id==household_id,RecurringObligation.active==True)).all()
        memories=s.scalars(select(MerchantMemory).where(MerchantMemory.household_id==household_id)).all()
        return {
            "accounts":[{"id":a.id,"name":a.name,"type":a.account_type,"balance":a.current_balance,"is_asset":a.is_asset} for a in accounts],
            "goals":[{"id":g.id,"name":g.name,"target":g.target_amount,"current":g.current_amount,"target_date":g.target_date.isoformat() if g.target_date else None} for g in goals],
            "recurring":[{"id":r.id,"merchant":r.merchant,"category":r.category,"amount":r.amount,"cadence":r.cadence,"next_date":r.next_expected_date.isoformat() if r.next_expected_date else None} for r in obligations],
            "merchant_memory":[{"merchant":m.merchant_normalized,"category":m.preferred_category,"confirmed":m.times_confirmed,"scope":m.rule_scope} for m in memories]
        }
