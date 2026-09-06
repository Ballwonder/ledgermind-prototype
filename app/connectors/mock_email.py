
from .base import EvidenceConnector
from app.models import Evidence

class MockEmailConnector(EvidenceConnector):
    def sync_evidence(self):
        return [
            Evidence(
                evidence_id="email-101", source="email", date="2026-09-01",
                vendor="Staples", amount=113.00,
                description="Invoice: printer paper and toner. Subtotal 100.00, HST 13.00, total 113.00.",
                attachment_name="staples_invoice_101.pdf", confidence=0.99
            ),
            Evidence(
                evidence_id="email-102", source="email", date="2026-09-02",
                vendor="Rogers", amount=226.00,
                description="Business internet and mobile services invoice, total 226.00.",
                attachment_name="rogers_sep.pdf", confidence=0.99
            ),
            Evidence(
                evidence_id="email-103", source="email", date="2026-09-03",
                vendor="ABC Contracting", amount=2875.00,
                description="Bathroom renovation: replace vanity, tile, fixtures and upgrade finishes.",
                attachment_name="abc_contracting_882.pdf", confidence=0.99
            )
        ]
