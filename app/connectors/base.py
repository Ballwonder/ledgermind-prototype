
from abc import ABC, abstractmethod

class BankConnector(ABC):
    @abstractmethod
    def sync_transactions(self): ...

class EvidenceConnector(ABC):
    @abstractmethod
    def sync_evidence(self): ...

class PayrollConnector(ABC):
    @abstractmethod
    def sync_payruns(self): ...

class AccountingConnector(ABC):
    @abstractmethod
    def post_journal(self, transaction_id: str, journal: list[dict]): ...
