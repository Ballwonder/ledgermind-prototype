# LedgerMind Prototype Security Notes

This build is a local/sandbox prototype, not a production financial system.

Implemented:
- no credentials or secrets embedded in source
- live connector readiness only activates when server environment variables are present
- CSV imports are idempotent by provider transaction ID
- uploaded documents are stored as source-document records
- deterministic bookkeeping-vs-tax split
- explicit reconciliation exception handling
- prior-period outstanding-item support
- duplicate/ambiguous statement match protection

Still required before real hosted financial-data use:
- authenticated user/session layer
- CSRF protections
- secure managed database and encrypted backups
- OAuth state/PKCE and verified callback origins
- Plaid webhook verification
- Gmail/Microsoft OAuth token encryption and rotation
- delete/export/privacy workflows
- tenant isolation tests
- rate limits and abuse controls
- structured audit logging and log redaction
- production queue/retry/monitoring
- security review

Do not paste live banking/email credentials into ChatGPT or source files. Configure connectors only through environment variables/secret management on the deployed server.
