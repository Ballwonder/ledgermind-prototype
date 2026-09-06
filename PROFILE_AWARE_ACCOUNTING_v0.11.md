# LedgerMind v0.11 — Profile-Aware Accounting

The FinancialProfile is now an input to accounting decisions.

Same purchase, different profile:
- Personal: household spending / possible net-worth asset; no business deduction engine.
- Sole proprietor: T2125-oriented current-vs-capital screen, business-use allocation, GST/HST/ITC review when registered.
- Rental: T776-oriented property expense screen; repair/restoration versus improvement/capital review.
- Corporation: corporate bookkeeping/T2-GIFI context; personal component triggers shareholder-versus-employee benefit review.

Decision output:
- treatment
- bookkeeping_required
- deductible_candidate
- business_use_pct
- gst_hst_review
- capital_review
- journal_template
- review_required
- owner_question
- rationale
- confidence

Important: these are decision/routing candidates, not automated tax filing conclusions. High-risk or fact-dependent issues remain reviewable.
