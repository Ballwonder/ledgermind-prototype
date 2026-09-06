# LedgerMind v0.14 — Contextual Accounting Treatment Precedent

Reviewer corrections can now become structured accounting precedents.

A precedent is scoped by:
- financial profile/entity,
- item type,
- business-use percentage,
- restoration/improvement/lasting-benefit facts,
- personal-component fact,
- merchant (supporting only),
- amount band,
- receipt/invoice evidence keywords,
- authority level,
- reviewer rationale.

Critical fact mismatches invalidate a precedent rather than merely lowering its score.

Authority order:
1. statute/regulation
2. CRA guidance
3. accounting standard
4. firm policy
5. client policy
6. reviewer precedent
7. model inference

v0.14 does not let a reviewer precedent override a higher-authority rule. Merchant identity alone is never enough to carry treatment.

Routing:
- strong unconflicted precedent >= 0.90 → `apply_precedent`
- partial precedent >= 0.75 → `review_precedent`
- otherwise → `no_precedent`

The ordinary accounting engine remains active; precedent is an additional evidence layer rather than a hidden override.
