
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import json, os, secrets

from app.db import init_db, conn, audit
from app.models import OwnerAnswer, ReviewApproval, PlaidExchange, TransactionCorrection
from app.engine import decide, balanced
from app.personal_finance import summarize, recurring_candidates
from app.connectors.plaid_bank import PlaidBankConnector
from app.security import encrypt_secret, decrypt_secret
from app.auth import router as auth_router, authenticate_request, enforce_csrf
from app.personal_service import set_request_household, reset_request_household
from app.personal_api import router as personal_v07_router, init_v07
from app.pipeline_api import router as pipeline_v08_router
from app.sandbox_api import router as sandbox_v09_router
from app.profile_api import router as profile_v010_router
from app.accounting_api import router as accounting_v011_router
from app.profile_assignment_api import router as profile_assignment_v012_router
from app.contextual_memory_api import router as contextual_memory_v013_router
from app.accounting_precedent_api import router as accounting_precedent_v014_router
from app.autonomy_api import router as autonomy_v015_router
from app.streamlining_api import router as streamlining_v016_router
from app.bookkeeping_cycle_api import router as bookkeeping_cycle_v017_router
from app.transaction_enrichment_api import router as enrichment_v018_router
from app.exception_diagnostics_api import router as diagnostics_v019_router
from app.evidence_sufficiency_api import router as evidence_v020_router
from app.document_validator_api import router as documents_v021_router
from app.document_extraction_api import router as document_ingest_v022_router
from app.evidence_retrieval_api import router as retrieval_v023_router
from app.ingestion_api import router as ingestion_v024_router
from app.event_processing_api import router as events_v025_router
from app.durable_processing_api import router as durable_v026_router
from app.journal_v027_api import router as journal_v027_router
from app.journal_gated_autonomy_api import router as autonomy_v028_router
from app.reconciliation_v029_api import router as reconciliation_v029_router
from app.statement_matching_v030_api import router as statement_v030_router
from app.reconciliation_actions_v031_api import router as recon_actions_v031_router
from app.outstanding_items_v032_api import router as outstanding_v032_router
from app.prototype_v036_api import router as prototype_v038_router
from app.connectors.mock_bank import MockBankConnector
from app.connectors.mock_email import MockEmailConnector
from app.connectors.mock_payroll import MockPayrollConnector
from app.connectors.mock_accounting import MockAccountingConnector

app = FastAPI(title="LedgerMind", version="0.1.0")

PUBLIC_PATHS = {"/health", "/login", "/setup"}

@app.middleware("http")
async def secure_application(request: Request, call_next):
    path = request.url.path
    if path in PUBLIC_PATHS:
        return await call_next(request)
    auth = authenticate_request(request)
    if not auth:
        if path.startswith("/api/"):
            return JSONResponse({"detail": "Authentication required"}, status_code=401)
        return RedirectResponse("/login", status_code=303)
    user, csrf = auth
    try:
        enforce_csrf(request, csrf)
    except HTTPException as exc:
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
    request.state.user = user
    request.state.csrf = csrf
    context_token = set_request_household(user.household_id)
    try:
        return await call_next(request)
    finally:
        reset_request_household(context_token)

app.include_router(auth_router)

app.include_router(personal_v07_router)
app.include_router(pipeline_v08_router)
app.include_router(sandbox_v09_router)
app.include_router(profile_v010_router)
app.include_router(accounting_v011_router)
app.include_router(profile_assignment_v012_router)
app.include_router(contextual_memory_v013_router)
app.include_router(accounting_precedent_v014_router)
app.include_router(autonomy_v015_router)
app.include_router(streamlining_v016_router)
app.include_router(bookkeeping_cycle_v017_router)
app.include_router(enrichment_v018_router)
app.include_router(diagnostics_v019_router)
app.include_router(evidence_v020_router)
app.include_router(documents_v021_router)
app.include_router(document_ingest_v022_router)
app.include_router(retrieval_v023_router)
app.include_router(ingestion_v024_router)
app.include_router(events_v025_router)
app.include_router(durable_v026_router)
app.include_router(journal_v027_router)
app.include_router(autonomy_v028_router)
app.include_router(reconciliation_v029_router)
app.include_router(statement_v030_router)
app.include_router(recon_actions_v031_router)
app.include_router(outstanding_v032_router)
app.include_router(prototype_v038_router)

templates = Jinja2Templates(directory="app/templates")

bank = MockBankConnector()
email = MockEmailConnector()
payroll = MockPayrollConnector()
accounting = MockAccountingConnector()
plaid = PlaidBankConnector()

@app.on_event("startup")
def startup():
    init_db()

def rowdict(r):
    return dict(r) if r else None

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/personal", response_class=HTMLResponse)
def personal_home(request: Request):
    return templates.TemplateResponse("personal.html", {"request": request})

@app.get("/api/connectors")
def connectors():
    return {
        "bank": {"provider":"MockBankConnector","status":"connected","production_target":"Plaid/Flinks-style adapter"},
        "email": {"provider":"MockEmailConnector","status":"connected","production_target":"Gmail/Microsoft Graph"},
        "payroll": {"provider":"MockPayrollConnector","status":"connected","production_target":"finalized pay-run adapter"},
        "accounting": {"provider":"MockAccountingConnector","status":"connected","production_target":"QuickBooks Online/Xero"},
    }

@app.post("/api/sync")
def sync():
    txs = bank.sync_transactions()
    evidence = email.sync_evidence()
    payruns = payroll.sync_payruns()

    with conn() as c:
        for e in evidence:
            c.execute("""INSERT OR REPLACE INTO evidence
                (id,source,date,vendor,amount,description,attachment_name,confidence)
                VALUES (?,?,?,?,?,?,?,?)""",
                (e.evidence_id,e.source,e.date,e.vendor,e.amount,e.description,e.attachment_name,e.confidence))

        for tx in txs:
            c.execute("""INSERT OR IGNORE INTO transactions
                (id,source_id,source,account_name,date,amount,description,merchant,pending,status)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (tx.source_id,tx.source_id,tx.source,tx.account_name,tx.date,tx.amount,
                 tx.description,tx.merchant,int(tx.pending),"new"))

    for tx in txs:
        decision = decide(tx, evidence)
        with conn() as c:
            c.execute("""INSERT OR REPLACE INTO decisions
                (transaction_id,route,account,tax_category,confidence,explanation,evidence_ids,missing_facts,journal,posted)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (decision.transaction_id,decision.route,decision.account,decision.tax_category,
                 decision.confidence,decision.explanation,json.dumps(decision.evidence_ids),
                 json.dumps(decision.missing_facts),
                 json.dumps([x.model_dump() for x in decision.journal]),int(decision.posted)))
            c.execute("UPDATE transactions SET status=? WHERE id=?", (decision.route, tx.source_id))
        audit(tx.source_id,"decision_created",decision.model_dump())

    return {
        "transactions_synced": len(txs),
        "evidence_synced": len(evidence),
        "payruns_synced": len(payruns),
        "message": "Connected sources synchronized and transactions reprocessed."
    }

@app.get("/api/dashboard")
def dashboard():
    with conn() as c:
        total = c.execute("SELECT COUNT(*) n FROM transactions").fetchone()["n"]
        counts = {r["route"]:r["n"] for r in c.execute(
            "SELECT route,COUNT(*) n FROM decisions GROUP BY route").fetchall()}
        evidence = c.execute("SELECT COUNT(*) n FROM evidence").fetchone()["n"]
    return {
        "transactions": total,
        "evidence_items": evidence,
        "auto_post": counts.get("auto_post",0),
        "auto_post_flag": counts.get("auto_post_flag",0),
        "owner_question": counts.get("owner_question",0),
        "professional_review": counts.get("professional_review",0),
        "posted": counts.get("posted",0)
    }

@app.get("/api/transactions")
def transactions():
    with conn() as c:
        rows = c.execute("""
        SELECT t.*, d.route,d.account,d.confidence,d.explanation,d.posted
        FROM transactions t LEFT JOIN decisions d ON t.id=d.transaction_id
        ORDER BY t.date DESC,t.id
        """).fetchall()
    return [rowdict(r) for r in rows]

@app.get("/api/transactions/{transaction_id}")
def transaction(transaction_id: str):
    with conn() as c:
        tx = c.execute("SELECT * FROM transactions WHERE id=?", (transaction_id,)).fetchone()
        dec = c.execute("SELECT * FROM decisions WHERE transaction_id=?", (transaction_id,)).fetchone()
        if not tx:
            raise HTTPException(404,"Transaction not found")
        out={"transaction":rowdict(tx),"decision":rowdict(dec)}
        if dec:
            for field in ("evidence_ids","missing_facts","journal"):
                out["decision"][field]=json.loads(out["decision"][field] or "[]")
            ids=out["decision"]["evidence_ids"]
            if ids:
                q=",".join("?"*len(ids))
                ev=c.execute(f"SELECT * FROM evidence WHERE id IN ({q})",ids).fetchall()
                out["evidence"]=[rowdict(x) for x in ev]
            else:
                out["evidence"]=[]
        return out

@app.post("/api/transactions/{transaction_id}/answer")
def answer(transaction_id: str, payload: OwnerAnswer):
    with conn() as c:
        d=c.execute("SELECT * FROM decisions WHERE transaction_id=?", (transaction_id,)).fetchone()
        if not d:
            raise HTTPException(404,"Decision not found")
        explanation=d["explanation"] + " Owner answer: " + payload.answer
        route="auto_post_flag"
        c.execute("""UPDATE decisions SET route=?, explanation=?, confidence=?,
                     missing_facts=? WHERE transaction_id=?""",
                  (route, explanation, 0.92, "[]", transaction_id))
        c.execute("UPDATE transactions SET status=? WHERE id=?", (route,transaction_id))
    audit(transaction_id,"owner_answer",payload.model_dump())
    return {"transaction_id":transaction_id,"route":route,"status":"reprocessed"}

@app.post("/api/transactions/{transaction_id}/approve")
def approve(transaction_id: str, payload: ReviewApproval):
    with conn() as c:
        d=c.execute("SELECT * FROM decisions WHERE transaction_id=?", (transaction_id,)).fetchone()
        if not d:
            raise HTTPException(404,"Decision not found")
        account=payload.approved_account or d["account"]
        explanation=d["explanation"] + " Reviewer approval: " + (payload.note or "approved")
        c.execute("""UPDATE decisions SET route='auto_post_flag', account=?, explanation=?,
                     confidence=? WHERE transaction_id=?""",
                  (account, explanation, 0.99, transaction_id))
        c.execute("UPDATE transactions SET status='auto_post_flag' WHERE id=?", (transaction_id,))
    audit(transaction_id,"review_approval",payload.model_dump())
    return {"transaction_id":transaction_id,"route":"auto_post_flag","status":"approved"}

@app.post("/api/transactions/{transaction_id}/post")
def post(transaction_id: str):
    with conn() as c:
        d=c.execute("SELECT * FROM decisions WHERE transaction_id=?", (transaction_id,)).fetchone()
        if not d:
            raise HTTPException(404,"Decision not found")
        if d["route"] not in ("auto_post","auto_post_flag"):
            raise HTTPException(409,"Transaction is not safe to post yet")
        journal=json.loads(d["journal"] or "[]")
        if not journal:
            raise HTTPException(409,"No journal entry is available yet")
        if abs(sum(x.get("debit",0) for x in journal)-sum(x.get("credit",0) for x in journal)) > .01:
            raise HTTPException(409,"Journal entry is not balanced")
        result=accounting.post_journal(transaction_id,journal)
        c.execute("UPDATE decisions SET route='posted',posted=1 WHERE transaction_id=?", (transaction_id,))
        c.execute("UPDATE transactions SET status='posted' WHERE id=?", (transaction_id,))
    audit(transaction_id,"posted_to_accounting",result)
    return result

@app.get("/api/audit/{transaction_id}")
def audit_log(transaction_id: str):
    with conn() as c:
        rows=c.execute("SELECT * FROM audit_events WHERE transaction_id=? ORDER BY id",
                       (transaction_id,)).fetchall()
    return [rowdict(r) for r in rows]


@app.get("/api/personal/summary")
def personal_summary():
    with conn() as c:
        rows=[dict(x) for x in c.execute("SELECT * FROM transactions ORDER BY date").fetchall()]
    return summarize(rows)

@app.get("/api/personal/recurring")
def personal_recurring():
    with conn() as c:
        rows=[dict(x) for x in c.execute("SELECT * FROM transactions ORDER BY date").fetchall()]
    return recurring_candidates(rows)

@app.get("/api/plaid/status")
def plaid_status():
    return {
        "configured": plaid.configured,
        "environment": plaid.env,
        "safe_to_test": plaid.env == "sandbox",
        "message": "Add your own Plaid credentials server-side. Never enter banking credentials directly into LedgerMind."
    }

@app.post("/api/plaid/link-token")
def plaid_link_token():
    if not plaid.configured:
        raise HTTPException(503,"Plaid credentials not configured. See .env.example and LIVE_CONNECTIONS.md.")
    return plaid.create_link_token()



@app.post("/api/plaid/exchange")
def plaid_exchange(payload: PlaidExchange):
    if not plaid.configured:
        raise HTTPException(503,"Plaid is not configured.")
    if not os.getenv("APP_ENCRYPTION_KEY"):
        raise HTTPException(503,"APP_ENCRYPTION_KEY is required before storing bank tokens.")
    data=plaid.exchange_public_token(payload.public_token)
    encrypted=encrypt_secret(data["access_token"])
    with conn() as c:
        c.execute("""INSERT INTO connections(provider,external_id,encrypted_access_token,status)
                     VALUES ('plaid',?,?, 'connected')""",(data["item_id"],encrypted))
    audit(data["item_id"],"plaid_connected",{"item_id":data["item_id"]})
    return {"connected":True,"item_id":data["item_id"]}

def sync_plaid_item(item_id: str):
    with conn() as c:
        row=c.execute("""SELECT * FROM connections WHERE provider='plaid'
                         AND external_id=? AND status='connected' ORDER BY id DESC LIMIT 1""",
                      (item_id,)).fetchone()
    if not row:
        raise HTTPException(404,"Plaid connection not found.")
    token=decrypt_secret(row["encrypted_access_token"])
    result=plaid.sync_transactions(token,row["cursor"])
    with conn() as c:
        for tx in result["added"] + result["modified"]:
            amt=float(tx.get("amount",0))
            # Plaid spending amounts are positive; LedgerMind uses outflow-negative convention.
            lm_amount=-amt
            c.execute("""INSERT OR REPLACE INTO transactions
                (id,source_id,source,account_name,date,amount,description,merchant,pending,status)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (tx["transaction_id"],tx["transaction_id"],"plaid",
                 tx.get("account_id","Bank"),tx.get("date"),lm_amount,
                 tx.get("name") or tx.get("merchant_name") or "Transaction",
                 tx.get("merchant_name"),int(tx.get("pending",False)),"new"))
        for tx in result["removed"]:
            c.execute("DELETE FROM transactions WHERE source_id=?",(tx["transaction_id"],))
            c.execute("DELETE FROM decisions WHERE transaction_id=?",(tx["transaction_id"],))
        c.execute("""UPDATE connections SET cursor=?,updated_at=CURRENT_TIMESTAMP
                     WHERE provider='plaid' AND external_id=?""",
                  (result["cursor"],item_id))
    audit(item_id,"plaid_sync",{
        "added":len(result["added"]),"modified":len(result["modified"]),
        "removed":len(result["removed"])
    })
    return {"item_id":item_id,"added":len(result["added"]),
            "modified":len(result["modified"]),"removed":len(result["removed"])}

@app.post("/api/plaid/sync/{item_id}")
def plaid_item_sync(item_id: str):
    return sync_plaid_item(item_id)

@app.post("/webhooks/plaid")
async def plaid_webhook(request: Request):
    payload=await request.json()
    # Production hardening still needs Plaid webhook signature verification.
    if payload.get("webhook_type")=="TRANSACTIONS" and payload.get("webhook_code")=="SYNC_UPDATES_AVAILABLE":
        item_id=payload.get("item_id")
        if item_id:
            try:
                result=sync_plaid_item(item_id)
            except Exception as exc:
                audit(item_id,"plaid_webhook_sync_error",{"error":str(exc)})
                return {"accepted":True,"sync":"failed"}
            return {"accepted":True,"sync":result}
    return {"accepted":True}

@app.get("/api/connections")
def live_connections():
    with conn() as c:
        rows=c.execute("""SELECT id,provider,external_id,status,created_at,updated_at
                          FROM connections ORDER BY id DESC""").fetchall()
    return [dict(x) for x in rows]

@app.post("/api/transactions/{transaction_id}/correct-category")
def correct_category(transaction_id: str, payload: TransactionCorrection):
    with conn() as c:
        tx=c.execute("SELECT * FROM transactions WHERE id=?",(transaction_id,)).fetchone()
        if not tx:
            raise HTTPException(404,"Transaction not found")
        d=c.execute("SELECT * FROM decisions WHERE transaction_id=?",(transaction_id,)).fetchone()
        prior=d["account"] if d else None
        c.execute("""INSERT INTO corrections(transaction_id,prior_category,corrected_category,note)
                     VALUES (?,?,?,?)""",(transaction_id,prior,payload.corrected_category,payload.note))
        if d:
            c.execute("""UPDATE decisions SET account=?, route='auto_post_flag',
                         explanation=explanation || ? WHERE transaction_id=?""",
                      (payload.corrected_category,
                       " User corrected category; retained as explicit feedback.",transaction_id))
    audit(transaction_id,"category_correction",payload.model_dump())
    return {"saved":True,"transaction_id":transaction_id,
            "corrected_category":payload.corrected_category}

@app.get("/api/corrections")
def corrections():
    with conn() as c:
        rows=c.execute("SELECT * FROM corrections ORDER BY id DESC").fetchall()
    return [dict(x) for x in rows]


@app.on_event('startup')
def startup_v07():
    init_v07()


@app.get("/health")
def health():
    return {"status": "ok", "service": "LedgerMind"}


@app.get("/launch")
def launch():
    return {
        "name": "LedgerMind",
        "prototype": "/prototype",
        "docs": "/docs",
        "health": "/health"
    }
