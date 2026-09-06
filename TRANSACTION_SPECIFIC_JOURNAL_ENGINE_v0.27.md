# LedgerMind v0.27 — Transaction-Specific Journal Engine

Adds deterministic journal templates for:
- operating expenses
- revenue
- transfers
- loan/mortgage payments
- payroll
- fixed assets
- owner/shareholder contributions
- owner draws/distributions

Safety rules:
- transfers require the destination/source account
- loan/mortgage payments require principal and interest split
- payroll requires finalized payroll-provider totals
- fixed assets can post acquisition cost, but unresolved capital class/useful-life questions remain review items
- GST/HST is separated only when a validated tax amount is supplied
- owner/shareholder funding is not treated as revenue
- owner draws are not treated as expenses

This is accounting-entry logic, not a tax-return engine.
