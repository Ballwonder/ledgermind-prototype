# LedgerMind v0.16 — Source Mapping, Recurring Rules, Exception Queue

## Source-to-profile mapping
Profiles can own trusted sources:
- email address,
- email folder/label,
- bank account,
- credit card,
- receipt inbox,
- other connector identifiers.

A dedicated source can carry up to 99.5% profile confidence. A mapped email that also requires a folder/label is capped when that folder is not confirmed.

## Recurring treatment rules
Repeated transactions can reuse:
- profile,
- category,
- treatment,
- business-use percentage,
- expected amount/tolerance,
- descriptor pattern,
- cadence.

Rules are profile-scoped.

## Exception-only workflow
`GET /api/v016/exception-queue` returns only transactions that still need:
- an owner fact/confirmation, or
- professional review.

This moves LedgerMind toward a workflow where completed transactions disappear into the background and the user sees only unresolved work.
