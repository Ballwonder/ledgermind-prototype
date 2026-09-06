# LedgerMind v0.10 — Financial Profile / Entity Architecture

A LedgerMind user/household can own multiple Financial Profiles.

Supported v0.10 profile types:
- Personal household → `personal_finance`
- Sole proprietor → `T2125`
- Corporation → `T2_GIFI`
- Rental property → `T776`

Key design rule:
The account that funded a transaction is not necessarily the profile/entity that economically owns the transaction.

A transaction therefore has:
- `household_id`
- `account_id`
- `profile_id`
- provider transaction identifiers
- category / confidence
- downstream tax/accounting context via FinancialProfile

This permits:
- personal and business charges on the same credit card,
- property-specific rental transactions,
- sole-proprietor mixed-use allocations,
- corporate shareholder/employee review where appropriate,
without treating the entire bank account as one accounting entity.

FinancialProfile stores:
- profile_type
- entity_type
- activity_type
- tax_regime
- province
- GST/HST registration flag
- currency

The profile is resolved before accounting/tax logic. It is not merely a UI filter.
