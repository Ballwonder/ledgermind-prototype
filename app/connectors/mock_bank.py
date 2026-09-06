
from .base import BankConnector
from app.models import SourceTransaction

class MockBankConnector(BankConnector):
    def sync_transactions(self):
        return [
            SourceTransaction(
                source_id="bank-001", source="bank", account_name="Business Mastercard",
                date="2026-09-01", amount=-113.00,
                description="STAPLES 0142 CORNWALL", merchant="Staples"
            ),
            SourceTransaction(
                source_id="bank-002", source="bank", account_name="Business Chequing",
                date="2026-09-02", amount=-226.00,
                description="ROGERS COMMUNICATIONS", merchant="Rogers"
            ),
            SourceTransaction(
                source_id="bank-003", source="bank", account_name="Business Chequing",
                date="2026-09-03", amount=-2875.00,
                description="ABC CONTRACTING INV 882", merchant="ABC Contracting"
            ),
            SourceTransaction(
                source_id="bank-004", source="bank", account_name="Business Chequing",
                date="2026-09-04", amount=-1025.00,
                description="TD COMMERCIAL LOAN", merchant="TD"
            ),
            SourceTransaction(
                source_id="bank-005", source="bank", account_name="Business Chequing",
                date="2026-09-05", amount=4500.00,
                description="CLIENT DEPOSIT PROJECT A", merchant="Client"
            ),
        ]
