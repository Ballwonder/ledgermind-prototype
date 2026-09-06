# LedgerMind v0.29 — Real Reconciliation Controls

Reconciliation now requires an account statement period and balance tie-out.

Controls:
- opening balance + cleared in-period transactions must equal statement closing balance,
- duplicate-suspect transactions are detected by same date + amount + merchant,
- paired transfers are identified by equal/opposite amounts within 3 days and transfer context,
- reconciliation records persist transaction-level statuses,
- unresolved statement differences block close,
- duplicate groups block close.

This replaces the earlier overly-loose proxy where a provider transaction ID could count as reconciled.

Current sandbox limitation: statement lines are represented through canonical imported transactions rather than a separate parsed statement-line table. The next production step would ingest actual statement lines and match ledger/book transactions to those lines explicitly.
