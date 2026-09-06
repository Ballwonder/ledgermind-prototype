# LedgerMind v0.25 — Event-Driven Processing

New external events can now trigger downstream work immediately.

## Transaction event
ingest → canonical transaction → enrichment → evidence retrieval → autonomy decision → persisted processing record

## Document/email event
ingest → source document → extraction → transaction matching → validation → matched transaction re-evaluation → persisted processing record

## Payroll/accounting events
normalized and preserved now; specialized autonomous handlers remain future work.

Processing is idempotent at the ingest-event level: an event already given a primary processing record is not processed twice.

This version remains synchronous and sandbox-oriented. Production should move the same semantics behind a durable job queue with retries, dead-letter handling, observability and connector-specific webhook verification.
