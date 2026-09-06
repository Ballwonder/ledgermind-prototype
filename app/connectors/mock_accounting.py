
from .base import AccountingConnector

class MockAccountingConnector(AccountingConnector):
    def __init__(self):
        self.posted = []

    def post_journal(self, transaction_id: str, journal: list[dict]):
        result = {
            "external_id": f"mock-je-{transaction_id}",
            "transaction_id": transaction_id,
            "journal": journal,
            "status": "posted"
        }
        self.posted.append(result)
        return result
