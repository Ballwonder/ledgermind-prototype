
from pydantic import BaseModel, Field
from typing import Optional, Literal, Any

Route = Literal["auto_post", "auto_post_flag", "owner_question", "professional_review", "posted"]

class SourceTransaction(BaseModel):
    source_id: str
    source: str
    account_name: str
    date: str
    amount: float
    description: str
    merchant: Optional[str] = None
    pending: bool = False

class Evidence(BaseModel):
    evidence_id: str
    source: str
    date: str
    vendor: Optional[str] = None
    amount: Optional[float] = None
    description: str
    attachment_name: Optional[str] = None
    confidence: float = 1.0

class JournalLine(BaseModel):
    account: str
    debit: float = 0.0
    credit: float = 0.0
    memo: str = ""

class Decision(BaseModel):
    transaction_id: str
    route: Route
    account: Optional[str] = None
    tax_category: Optional[str] = None
    confidence: float
    explanation: str
    evidence_ids: list[str] = Field(default_factory=list)
    missing_facts: list[str] = Field(default_factory=list)
    journal: list[JournalLine] = Field(default_factory=list)
    posted: bool = False

class OwnerAnswer(BaseModel):
    answer: str

class ReviewApproval(BaseModel):
    approved_account: Optional[str] = None
    note: Optional[str] = None


class PlaidExchange(BaseModel):
    public_token: str

class TransactionCorrection(BaseModel):
    corrected_category: str
    note: Optional[str] = None
