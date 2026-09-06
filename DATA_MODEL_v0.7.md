# LedgerMind Personal v0.7 Data Model

Canonical entities:
- Household
- Account
- Transaction
- RecurringObligation
- Goal
- MerchantMemory
- Correction
- Insight
- Evidence
- AuditEvent

Design rules:
- Provider IDs are separate from LedgerMind internal primary keys.
- Inflows are positive; outflows are negative.
- Transfers can be excluded from spending without deleting the transaction.
- User corrections are immutable correction records plus a scoped merchant-memory update.
- Raw provider data should remain traceable through provider/provider IDs.
- SQLite is the local prototype database; set DATABASE_URL for a production SQLAlchemy-supported database such as PostgreSQL.
- Email evidence is modeled separately from transactions so receipt/invoice provenance can be retained.
