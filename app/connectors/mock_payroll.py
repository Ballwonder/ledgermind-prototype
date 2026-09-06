
from .base import PayrollConnector

class MockPayrollConnector(PayrollConnector):
    def sync_payruns(self):
        return [{
            "payrun_id": "pay-2026-09-01",
            "date": "2026-09-05",
            "gross_wages": 8200.00,
            "employer_costs": 730.00,
            "net_pay": 6120.00,
            "withholdings": 2810.00,
            "status": "finalized"
        }]
