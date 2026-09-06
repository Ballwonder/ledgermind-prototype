# LedgerMind v0.31 — Reconciliation Exception Actions

Turns unresolved reconciliation items into action proposals.

BANK_ONLY:
- deterministic bank/service fees can generate a proposed missing ledger entry;
- simple statement-only inflows may get a proposed income/refund entry;
- otherwise owner review.

BOOK_ONLY:
- recent cheques can be classified as outstanding items;
- recent payments can be marked as timing differences;
- older or unclear items remain investigation items.

AMBIGUOUS:
- surfaced for match confirmation.

DUPLICATE_STATEMENT_LINE:
- surfaced for duplicate review.

Only high-confidence actions cross the safe-apply threshold in this sandbox.
