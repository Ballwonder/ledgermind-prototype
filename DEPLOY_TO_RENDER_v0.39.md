# LedgerMind v0.39 — Render Deployment

## What this package does
This package is configured as a Render Blueprint with:
- a Python FastAPI web service,
- `/health` HTTP health check,
- a Render Postgres database,
- automatic `DATABASE_URL` injection,
- generated session secret,
- live financial connectors disabled by default.

## Fastest deployment path

### 1. Create a private GitHub repository
Create a new empty private repository, for example `ledgermind-prototype`.

Extract this ZIP and upload/push the **contents inside the LedgerMind_v0.39_Render_Deployable folder** to the root of the repository. `render.yaml` must be at the repository root.

Do not commit `.env` files or credentials.

### 2. Create a Render account
In Render, choose **New > Blueprint** and connect the private GitHub repository.

Render should detect `render.yaml` and propose:
- `ledgermind-prototype` web service
- `ledgermind-prototype-db` Postgres database

Review the resources, then deploy the Blueprint.

### 3. Open the application
After the deploy succeeds, Render supplies an `onrender.com` address.

Open:
- `/health` — should return status `ok`
- `/prototype` — LedgerMind prototype
- `/docs` — FastAPI API documentation

### 4. Test without real financial information
Start with `sample_bank_transactions.csv`.
Upload sample/test receipts only.

The free Render Postgres database is temporary prototype storage. As of September 2026, free Render Postgres instances expire 30 days after creation and have no backups. Do not rely on it for permanent financial records.

## Before using real financial data
Keep `ENABLE_LIVE_FINANCIAL_CONNECTORS=false` until these are completed:
- user authentication/session enforcement,
- tenant/data isolation testing,
- CSRF protection for browser writes,
- encrypted OAuth token storage,
- OAuth state/PKCE where supported,
- webhook signature verification,
- audit logging and secret redaction,
- data export/delete workflow,
- backup/recovery plan,
- production database,
- production security review.

## Live connector credentials
When ready, add credentials only in Render's Environment/Secrets settings. Do not put them in GitHub source code or send them in chat.

Variables reserved by this prototype:
- `PLAID_CLIENT_ID`
- `PLAID_SECRET`
- `PLAID_ENV`
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `MICROSOFT_CLIENT_ID`
- `MICROSOFT_CLIENT_SECRET`

## Free-tier caveats
Render free web services can spin down when inactive and take time to wake again.
Free Postgres is suitable only for testing and expires after 30 days.
A paid Postgres instance or another durable managed database is required before relying on LedgerMind to retain financial records long term.
