# LedgerMind v0.13 — Contextual Profile Learning

A correction no longer teaches `Amazon = Business`.

It teaches a scoped precedent built from:
- normalized merchant,
- transaction descriptor/evidence signature,
- source account,
- amount band,
- linked receipt/invoice keywords,
- confirmed target profile,
- confirmation count and confidence.

Profile assignment scoring:
- merchant match alone: deliberately weak,
- same account: adds evidence,
- descriptor overlap: adds evidence,
- receipt/invoice keyword overlap: adds evidence,
- amount within learned band: adds evidence.

Auto-assignment still requires >= 0.95 confidence and a >= 0.10 lead over competing profiles.

Conflicts:
If the same contextual pattern is later confirmed to a different profile, LedgerMind preserves the conflicting precedent rather than overwriting it. Ambiguous future matches therefore fall back to confirmation/review.

This is intentionally conservative because entity/profile errors can change tax and bookkeeping treatment downstream.
