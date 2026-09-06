# LedgerMind v0.12 — Automatic Profile Assignment

Purpose:
Determine whether a transaction belongs to Personal, Sole Proprietor, Corporation, or a Rental profile before the accounting/tax engine runs.

Evidence hierarchy in v0.12:
1. Existing explicit transaction profile
2. Explicit source-account ownership
3. User-confirmed profile-assignment rules
4. Linked receipt/invoice evidence
5. Weak semantic context

Actions:
- `keep_assigned`
- `auto_assign`
- `confirm_profile`
- `owner_question`

Safety:
- Auto-assignment requires confidence >= 0.95 and at least a 0.10 margin over the next-best candidate.
- Ambiguous transactions are not assigned automatically.
- User confirmations can create scoped merchant rules.
- Conflicting learned rules are not silently overwritten.
- Profile assignment is resolved before profile-aware accounting treatment.

Important design note:
A payment account can contain transactions belonging to different profiles. Account ownership is strong evidence only when an account is explicitly dedicated to one profile; otherwise transaction-level evidence and user confirmation remain necessary.
