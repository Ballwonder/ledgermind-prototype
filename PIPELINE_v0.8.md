# LedgerMind v0.8 Ingestion & Intelligence Pipeline

Pipeline:
1. Provider transaction arrives.
2. Provider identifiers are retained separately from LedgerMind IDs.
3. Merchant is normalized.
4. Plaid PFCv2 is mapped into LedgerMind's internal taxonomy.
5. Deterministic transaction rules and scoped user merchant memory are evaluated.
6. A category plus confidence and source are produced.
7. Email/receipt evidence is matched using merchant, amount, date and subject.
8. Recurring streams can populate RecurringObligation records.
9. Anomaly detection creates review Insights rather than silently changing transactions.
10. Audit events preserve why a transaction was ingested/updated.

Important boundaries:
- Provider category is evidence, not LedgerMind's canonical truth.
- User-confirmed category memory has high weight but is scoped to a normalized merchant.
- Transfers are retained but excluded from ordinary spending totals.
- Email evidence remains a separate provenance object.
- Real Plaid recurring access can require product access; the adapter is implemented but the prototype does not assume entitlement.
