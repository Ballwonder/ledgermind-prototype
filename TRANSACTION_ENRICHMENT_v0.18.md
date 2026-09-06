# LedgerMind v0.18 — Transaction Enrichment

Before autonomy routing, LedgerMind now enriches transactions using:
- recurring rules,
- already linked evidence,
- transaction description,
- existing category/profile context.

It can infer or strengthen:
- profile,
- category,
- item type,
- business-use percentage,
- personal-component flag,
- repair/restoration indicators,
- improvement/lasting-benefit indicators,
- evidence quality.

Only very high-confidence recurring-profile mappings are persisted automatically.

The bookkeeping cycle now runs enrichment before autonomy decisions.
