# LedgerMind v0.32 — Close-Aware Outstanding Items

Legitimate timing differences no longer automatically block close.

A high-confidence BOOK_ONLY cheque/payment can become an OutstandingItem. The close gate accepts that item as a timing difference while still blocking bank-only, ambiguous, duplicate, unexplained book-only, and stale outstanding items.

Outstanding items persist across periods. When a later statement explicitly matches the ledger transaction, the item becomes CLEARED. Items still outstanding after 90 days become STALE_REVIEW rather than being carried indefinitely.
