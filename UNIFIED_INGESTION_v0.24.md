# LedgerMind v0.24 — Unified Ingestion Boundary

All external systems now enter through one canonical ingestion interface.

Supported normalized connector families:
- bank / credit card / Plaid / bank CSV → Transaction
- Gmail / Outlook / generic email / upload → SourceDocument
- payroll → normalized payroll event
- QuickBooks / Xero / accounting → normalized accounting event

Every ingestion creates an immutable-ish IngestEvent record containing:
- connector type
- external ID
- event type
- raw payload
- normalized payload
- profile context
- linked canonical transaction/document IDs

Duplicate external events are detected and are not materialized twice.

This is still a sandbox boundary. It does not authenticate to Plaid, Gmail, Outlook, payroll providers, QuickBooks or Xero by itself.
