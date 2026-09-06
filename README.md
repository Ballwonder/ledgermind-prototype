# LedgerMind Web MVP

Integration-first prototype for an autonomous accounting control layer.

## What this prototype demonstrates
- Connected-source architecture for bank feeds, email evidence, payroll, and accounting software.
- Unified transaction/evidence inbox.
- Evidence matching before asking the owner.
- Safety-first routing: auto-post, auto-post+flag, owner question, professional review.
- Journal preview and mock write-back to accounting software.
- Audit trail for every decision.
- SQLite persistence.

## Important
This is an MVP/demo. The connectors are mock adapters. They are intentionally shaped so real provider integrations can replace them later without changing the rest of LedgerMind.

Current production research assumptions:
- Bank adapter is designed around incremental transaction-sync/webhook patterns used by providers such as Plaid.
- Email adapter is designed around message/attachment APIs such as Gmail and Microsoft Graph.
- Accounting adapter is designed around accounting APIs such as QuickBooks Online / Xero.
- Payroll adapter consumes finalized payroll results rather than calculating statutory payroll in v1.

## Run
```bash
cd ledgermind_web_mvp
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000

## Main API endpoints
- GET /api/dashboard
- GET /api/transactions
- GET /api/transactions/{id}
- POST /api/sync
- POST /api/transactions/{id}/answer
- POST /api/transactions/{id}/approve
- POST /api/transactions/{id}/post
- GET /api/audit/{transaction_id}
- GET /api/connectors

## Next production steps
1. Replace MockBankConnector with a real Canadian bank-data provider adapter.
2. Add OAuth for Gmail / Microsoft 365.
3. Add QuickBooks Online and/or Xero OAuth + write-back.
4. Add payroll adapters for finalized pay-run journals.
5. Add encrypted secret storage, tenant isolation, permissions, webhook verification, idempotency, and production audit controls.
6. Expand and independently validate accounting/tax decision coverage before permitting broad autonomous posting.

## LedgerMind Personal v0.2
Open `/personal` for the household-finance dashboard.

This version adds:
- Personal spending categories
- Fixed vs discretionary spending
- Household cash-flow summary
- Recurring-expense detection
- A real Plaid adapter implementation with Sandbox as the safe default
- Live-connection setup notes and environment template

Real bank linking still requires your own provider developer credentials and a browser-side Link flow. Gmail OAuth requires a Google Cloud OAuth client. Those credentials are intentionally not embedded in this downloadable prototype.

## v0.3 additions
- Browser Plaid Link flow.
- Public-token exchange endpoint.
- Encrypted Plaid access-token storage.
- Incremental `/transactions/sync` persistence.
- Plaid transaction webhook listener.
- User correction/feedback endpoint.
- Gmail evidence connector implementation.
- Docker deployment file and production security checklist.

### Safety boundary
v0.3 is suitable for Sandbox testing. It is not yet suitable for real financial or email data because authentication, CSRF protection, verified webhooks, managed encrypted persistence, and completed OAuth-state handling are still outstanding.
