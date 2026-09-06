# LedgerMind v0.20 — Purpose-Specific Evidence Sufficiency

The old question, “Does this transaction have a receipt?”, has been replaced by:
**“What decision is LedgerMind trying to support, and what evidence does that decision require?”**

Prototype evidence purposes:
- personal-finance classification
- cash movement / specialized payment support
- business expense support
- business income support
- general support

Key policy:
- Personal categorization can rely on a linked financial-account transaction without demanding a receipt.
- Business/rental/corporate expenses remain conservative: a bank/card charge alone does not automatically support the expense/tax claim.
- GST/HST registrants are flagged as needing documentary support before ITCs are treated as fully supported.
- Business income can use identifiable bank-source evidence for bookkeeping occurrence, while source documents should still be retained.
- Detailed GST/HST statutory field validation is intentionally deferred to a dedicated validator.

This is product routing logic, not legal/tax advice.
