# LedgerMind v0.22 — Document Extraction + Transaction Matching

Prototype capabilities:
- extract supplier, date, total, GST/HST indication, registration number, buyer, description and payment terms from email/document text,
- score candidate bank/card transactions by amount, merchant and date,
- auto-link only above a high-confidence threshold,
- create linked Evidence,
- immediately run the v0.21 deterministic document validator,
- feed the resulting evidence/validation into the normal autonomy cycle.

Important safety boundary:
Ambiguous matches are returned as candidates and are not auto-linked.

This extractor is text-based. Production receipt/PDF/image extraction should use a dedicated document/OCR/vision pipeline plus validation.
