# LedgerMind v0.17 — Autonomous Bookkeeping Cycle

This version executes a full prototype cycle across the household ledger:

1. load transactions,
2. match recurring rules,
3. derive available structured facts,
4. run autonomy decision,
5. generate a journal entry for safe transactions,
6. verify debit = credit,
7. reconcile against evidence/provider transaction,
8. persist per-transaction processing results,
9. produce an exception list,
10. calculate close readiness.

## Safety
Only `AUTO_FINISH` transactions receive generated journal entries.
Owner questions and professional-review cases remain unresolved and block full close readiness.

## Close readiness
Prototype close readiness requires:
- no unresolved owner questions,
- no unresolved professional reviews,
- every auto-finished transaction reconciled,
- at least one processed transaction.

This is still a synthetic sandbox. Journal templates and reconciliation logic remain simplified and should not be treated as production accounting logic.
