# LedgerMind v0.28 — Journal-Gated Autonomy

`AUTO_FINISH` now requires two independent conditions:

1. the existing profile/evidence/accounting autonomy router returns AUTO_FINISH, and
2. the transaction-specific journal is complete, balanced, and does not require journal-level review.

Downgrades:
- missing journal facts → OWNER_QUESTION
- unbalanced journal → PROFESSIONAL_REVIEW
- journal warnings requiring review → PROFESSIONAL_REVIEW

Examples:
- mortgage without principal/interest split cannot auto-finish.
- payroll without finalized gross/net totals cannot auto-finish.
- fixed asset without unresolved capital-class handling can be forced to review.
- ordinary expense/revenue/transfer with sufficient facts and evidence can auto-finish only after debit=credit validation.

This makes AUTO_FINISH a stronger accounting state rather than just a classification state.
