# LedgerMind v0.19 — Exception Diagnostics

This layer measures *why* LedgerMind cannot finish transactions instead of lowering thresholds blindly.

Primary bottleneck buckets:
- profile uncertainty
- missing/weak evidence
- missing owner fact
- accounting confidence
- professional judgment
- other/unknown

For every unresolved transaction it records the profile, evidence and accounting confidence components, available evidence count, exact owner question/review reason, and enrichment signals already attempted.

The purpose is to direct development toward the highest-volume remaining failure mode.
