# LedgerMind Personal v0.3 deployment checklist

This package is deployment-shaped, but do not connect real financial data until the security checklist below is completed.

## Required server environment variables
- PLAID_ENV=sandbox (start here)
- PLAID_CLIENT_ID
- PLAID_SECRET
- APP_ENCRYPTION_KEY
- GOOGLE_CLIENT_ID
- GOOGLE_CLIENT_SECRET

## Bank flow now implemented
1. Browser requests a short-lived Plaid Link token.
2. Plaid Link opens in the browser.
3. Browser receives a temporary public token.
4. Server exchanges it for an access token.
5. Server encrypts the access token before storing it.
6. `/transactions/sync` imports incremental bank transaction changes.
7. Plaid webhook endpoint can trigger later syncs.

## Still required before real personal data
- User authentication/session management.
- CSRF protection for state-changing browser requests.
- Plaid webhook signature verification.
- Database encryption/backups and managed persistent storage.
- HTTPS-only deployment.
- Strict server logs with financial payload redaction.
- A privacy/delete-data workflow.
- OAuth state/PKCE and completed Gmail callback flow.
- Explicit consent screen describing what email data is searched/stored.
- Rate limiting and monitoring.
- Separate development/test/production environments.

## Gmail
The Gmail evidence connector is implemented at the API layer, but the OAuth start/callback routes are intentionally not enabled until application authentication and OAuth state storage are present. Do not weaken OAuth safety just to make the demo connect sooner.
