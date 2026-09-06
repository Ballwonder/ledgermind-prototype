# LedgerMind v0.21 — Deterministic CRA Document Validator

For ordinary ITC-support documents, current CRA information thresholds are encoded as deterministic rules:

## Under $100
- supplier/business/trading name
- invoice date or tax-paid/payable date
- total amount

## $100 to $499.99
Everything above, plus:
- GST/HST amount/inclusion indication
- supplier/intermediary GST/HST registration number
- supply tax status when the document mixes taxable and exempt supplies

## $500+
Everything above, plus:
- buyer/recipient name or trading name
- brief description of property/services
- payment terms

The validator intentionally does not decide whether an ITC is legally allowable in every circumstance. It checks whether the ordinary document-information fields are present.

GST/HST-registered business expenses are now blocked from fully autonomous ITC treatment until a linked document has passed this validator.

Rule version: CRA_ITC_2021_THRESHOLDS_v1
