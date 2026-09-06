# LedgerMind v0.30 — Statement-Line Matching

Adds separate bank statement lines and explicit bank-to-ledger matching.

Statuses: MATCHED, BANK_ONLY, BOOK_ONLY, AMBIGUOUS, DUPLICATE_STATEMENT_LINE.

Autonomous matching requires a strong score and margin over the second-best candidate. Amount, date proximity, and description/merchant overlap contribute to matching.

Close is blocked by unresolved bank-only, book-only, ambiguous or duplicate statement-line items, or a remaining total difference.
