# LedgerMind v0.15 — Autonomy Decision Layer

The autonomy router combines:
- profile assignment confidence,
- evidence quality,
- profile-aware accounting decision,
- contextual accounting precedent,
- explicit review gates.

Final routes:
- `AUTO_FINISH`
- `OWNER_QUESTION`
- `PROFESSIONAL_REVIEW`

Core principle:
Never average away a weak material component. The weakest material factor controls autonomy.

Autonomous completion requires:
- profile known/auto-assignable,
- sufficient evidence,
- no unresolved owner fact,
- no professional-judgment review trigger,
- all material confidence components >= 0.90.

If a factual owner answer can resolve uncertainty, LedgerMind asks the owner before escalating to a professional.

Strong precedents support decisions but do not automatically cancel review-sensitive tax/accounting issues.

Primary safety objective:
Minimize unsafe autonomous completion, even at the cost of some false-positive review/questions during early development.
