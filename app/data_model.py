
from __future__ import annotations
import os
from datetime import datetime, date
from sqlalchemy import (
    create_engine, String, Integer, Float, Date, DateTime, Boolean,
    ForeignKey, Text, UniqueConstraint
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/ledgermind_v07.db")
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

class Household(Base):
    __tablename__ = "households"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), default="My Household")
    currency: Mapped[str] = mapped_column(String(3), default="CAD")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FinancialProfile(Base):
    __tablename__ = "financial_profiles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    profile_type: Mapped[str] = mapped_column(String(40), index=True)
    entity_type: Mapped[str] = mapped_column(String(40), index=True)
    activity_type: Mapped[str] = mapped_column(String(60), index=True)
    tax_regime: Mapped[str] = mapped_column(String(60), index=True)
    currency: Mapped[str] = mapped_column(String(3), default="CAD")
    province: Mapped[str | None] = mapped_column(String(40), nullable=True)
    gst_hst_registered: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Account(Base):
    __tablename__ = "accounts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    profile_id: Mapped[int | None] = mapped_column(ForeignKey("financial_profiles.id"), nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(40), default="manual")
    provider_account_id: Mapped[str | None] = mapped_column(String(180), nullable=True)
    name: Mapped[str] = mapped_column(String(120))
    account_type: Mapped[str] = mapped_column(String(40))
    subtype: Mapped[str | None] = mapped_column(String(80), nullable=True)
    current_balance: Mapped[float] = mapped_column(Float, default=0.0)
    available_balance: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_asset: Mapped[bool] = mapped_column(Boolean, default=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    __table_args__ = (UniqueConstraint("provider","provider_account_id", name="uq_provider_account"),)

class Transaction(Base):
    __tablename__ = "personal_transactions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    profile_id: Mapped[int | None] = mapped_column(ForeignKey("financial_profiles.id"), nullable=True, index=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(40), default="manual")
    provider_transaction_id: Mapped[str | None] = mapped_column(String(180), nullable=True)
    tx_date: Mapped[date] = mapped_column(Date, index=True)
    posted_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    merchant_raw: Mapped[str | None] = mapped_column(String(240), nullable=True)
    merchant_normalized: Mapped[str | None] = mapped_column(String(240), nullable=True, index=True)
    description: Mapped[str] = mapped_column(String(500))
    amount: Mapped[float] = mapped_column(Float)   # inflow positive, outflow negative
    category: Mapped[str] = mapped_column(String(80), default="Other", index=True)
    category_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    pending: Mapped[bool] = mapped_column(Boolean, default=False)
    recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    excluded_from_spending: Mapped[bool] = mapped_column(Boolean, default=False)
    evidence_status: Mapped[str] = mapped_column(String(40), default="none")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (UniqueConstraint("provider","provider_transaction_id", name="uq_provider_transaction"),)

class RecurringObligation(Base):
    __tablename__ = "recurring_obligations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    merchant: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(80))
    amount: Mapped[float] = mapped_column(Float)
    cadence: Mapped[str] = mapped_column(String(30))
    next_expected_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    source: Mapped[str] = mapped_column(String(40), default="manual")
    active: Mapped[bool] = mapped_column(Boolean, default=True)

class Goal(Base):
    __tablename__ = "goals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    target_amount: Mapped[float] = mapped_column(Float)
    current_amount: Mapped[float] = mapped_column(Float, default=0)
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="active")













class StatementLine(Base):
    __tablename__ = "statement_lines"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    statement_id: Mapped[int] = mapped_column(ForeignKey("bank_statements.id"), index=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    line_date: Mapped[date] = mapped_column(Date)
    description: Mapped[str] = mapped_column(Text)
    amount: Mapped[float] = mapped_column(Float)
    balance: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)



class OutstandingItem(Base):
    __tablename__ = "outstanding_items_v032"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    statement_id: Mapped[int] = mapped_column(ForeignKey("bank_statements.id"), index=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("personal_transactions.id"), index=True)
    classification: Mapped[str] = mapped_column(String(60), index=True)
    status: Mapped[str] = mapped_column(String(40), default="OUTSTANDING", index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    first_period_end: Mapped[date] = mapped_column(Date)
    last_checked_period_end: Mapped[date] = mapped_column(Date)
    cleared_statement_id: Mapped[int | None] = mapped_column(ForeignKey("bank_statements.id"), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class ReconciliationAction(Base):
    __tablename__ = "reconciliation_actions_v031"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    statement_id: Mapped[int] = mapped_column(ForeignKey("bank_statements.id"), index=True)
    statement_line_id: Mapped[int | None] = mapped_column(ForeignKey("statement_lines.id"), nullable=True, index=True)
    transaction_id: Mapped[int | None] = mapped_column(ForeignKey("personal_transactions.id"), nullable=True, index=True)
    action_type: Mapped[str] = mapped_column(String(60), index=True)
    status: Mapped[str] = mapped_column(String(40), default="PROPOSED", index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    proposed_payload_json: Mapped[str] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class StatementMatch(Base):
    __tablename__ = "statement_matches_v030"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    statement_id: Mapped[int] = mapped_column(ForeignKey("bank_statements.id"), index=True)
    statement_line_id: Mapped[int | None] = mapped_column(ForeignKey("statement_lines.id"), nullable=True, index=True)
    transaction_id: Mapped[int | None] = mapped_column(ForeignKey("personal_transactions.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(40), index=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class BankStatement(Base):
    __tablename__ = "bank_statements"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True, index=True)
    account_name: Mapped[str] = mapped_column(String(255), index=True)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    opening_balance: Mapped[float] = mapped_column(Float)
    closing_balance: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(10), default="CAD")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class ReconciliationRecord(Base):
    __tablename__ = "reconciliation_records_v029"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    statement_id: Mapped[int] = mapped_column(ForeignKey("bank_statements.id"), index=True)
    transaction_id: Mapped[int | None] = mapped_column(ForeignKey("personal_transactions.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(40), index=True)
    matched_transaction_id: Mapped[int | None] = mapped_column(ForeignKey("personal_transactions.id"), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class ProcessingJob(Base):
    __tablename__ = "processing_jobs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    ingest_event_id: Mapped[int] = mapped_column(ForeignKey("ingest_events.id"), index=True)
    job_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default="PENDING", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class AccountingException(Base):
    __tablename__ = "accounting_exceptions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("personal_transactions.id"), index=True)
    exception_type: Mapped[str] = mapped_column(String(60))
    state: Mapped[str] = mapped_column(String(30), default="OPEN", index=True)
    question: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    opened_by_event_id: Mapped[int | None] = mapped_column(ForeignKey("ingest_events.id"), nullable=True)
    resolved_by_event_id: Mapped[int | None] = mapped_column(ForeignKey("ingest_events.id"), nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class EventProcessingRecord(Base):
    __tablename__ = "event_processing_records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ingest_event_id: Mapped[int] = mapped_column(ForeignKey("ingest_events.id"), index=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    action_type: Mapped[str] = mapped_column(String(80))
    transaction_id: Mapped[int | None] = mapped_column(ForeignKey("personal_transactions.id"), nullable=True)
    source_document_id: Mapped[int | None] = mapped_column(ForeignKey("source_documents.id"), nullable=True)
    route: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="completed")
    detail_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class IngestEvent(Base):
    __tablename__ = "ingest_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    profile_id: Mapped[int | None] = mapped_column(ForeignKey("financial_profiles.id"), nullable=True, index=True)
    connector_type: Mapped[str] = mapped_column(String(60), index=True)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    raw_payload_json: Mapped[str] = mapped_column(Text)
    normalized_payload_json: Mapped[str] = mapped_column(Text)
    ingest_status: Mapped[str] = mapped_column(String(40), default="normalized")
    linked_transaction_id: Mapped[int | None] = mapped_column(ForeignKey("personal_transactions.id"), nullable=True)
    linked_source_document_id: Mapped[int | None] = mapped_column(ForeignKey("source_documents.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class SourceDocument(Base):
    __tablename__ = "source_documents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    profile_id: Mapped[int | None] = mapped_column(ForeignKey("financial_profiles.id"), nullable=True, index=True)
    source_type: Mapped[str] = mapped_column(String(50), default="email")
    source_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    folder_or_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(500), nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    matched_transaction_id: Mapped[int | None] = mapped_column(ForeignKey("personal_transactions.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class DocumentValidationRecord(Base):
    __tablename__ = "document_validation_records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("personal_transactions.id"), index=True)
    purpose: Mapped[str] = mapped_column(String(60), default="itc_support")
    document_fields_json: Mapped[str] = mapped_column(Text)
    threshold_band: Mapped[str] = mapped_column(String(40))
    valid_for_itc_support: Mapped[bool] = mapped_column(Boolean, default=False)
    missing_fields_json: Mapped[str] = mapped_column(Text)
    warnings_json: Mapped[str] = mapped_column(Text)
    rule_version: Mapped[str] = mapped_column(String(40), default="CRA_ITC_2021_THRESHOLDS_v1")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class ProcessingRun(Base):
    __tablename__ = "processing_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="running")
    processed_count: Mapped[int] = mapped_column(Integer, default=0)
    auto_finished_count: Mapped[int] = mapped_column(Integer, default=0)
    owner_question_count: Mapped[int] = mapped_column(Integer, default=0)
    professional_review_count: Mapped[int] = mapped_column(Integer, default=0)
    reconciled_count: Mapped[int] = mapped_column(Integer, default=0)
    close_ready: Mapped[bool] = mapped_column(Boolean, default=False)

class TransactionProcessingResult(Base):
    __tablename__ = "transaction_processing_results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("processing_runs.id"), index=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("personal_transactions.id"), index=True)
    route: Mapped[str] = mapped_column(String(50), index=True)
    profile_id: Mapped[int | None] = mapped_column(ForeignKey("financial_profiles.id"), nullable=True)
    treatment: Mapped[str | None] = mapped_column(String(140), nullable=True)
    journal_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    journal_balanced: Mapped[bool] = mapped_column(Boolean, default=False)
    reconciled: Mapped[bool] = mapped_column(Boolean, default=False)
    exception_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class ProfileSourceMap(Base):
    __tablename__ = "profile_source_maps"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("financial_profiles.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(60), index=True)
    source_value: Mapped[str] = mapped_column(String(320), index=True)
    folder_or_label: Mapped[str | None] = mapped_column(String(320), nullable=True)
    trust_level: Mapped[str] = mapped_column(String(30), default="strong")
    confidence: Mapped[float] = mapped_column(Float, default=0.98)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class RecurringTreatmentRule(Base):
    __tablename__ = "recurring_treatment_rules"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("financial_profiles.id"), index=True)
    merchant_normalized: Mapped[str] = mapped_column(String(200), index=True)
    descriptor_contains: Mapped[str | None] = mapped_column(String(240), nullable=True)
    category: Mapped[str | None] = mapped_column(String(120), nullable=True)
    treatment: Mapped[str | None] = mapped_column(String(120), nullable=True)
    business_use_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    amount_tolerance_pct: Mapped[float] = mapped_column(Float, default=0.20)
    cadence: Mapped[str | None] = mapped_column(String(40), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.98)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class AccountingPrecedent(Base):
    __tablename__ = "accounting_precedents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("financial_profiles.id"), index=True)
    treatment: Mapped[str] = mapped_column(String(100), index=True)
    account_or_category: Mapped[str | None] = mapped_column(String(160), nullable=True)
    item_type: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    merchant_normalized: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    min_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    business_use_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    restores_original_condition: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    improves_beyond_original_condition: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    lasting_benefit: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    personal_component_present: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    evidence_keywords: Mapped[str | None] = mapped_column(Text, nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    authority_level: Mapped[str] = mapped_column(String(50), default="reviewer_precedent")
    confidence: Mapped[float] = mapped_column(Float, default=0.95)
    times_confirmed: Mapped[int] = mapped_column(Integer, default=1)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class ContextProfileMemory(Base):
    __tablename__ = "context_profile_memory"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("financial_profiles.id"), index=True)
    merchant_normalized: Mapped[str] = mapped_column(String(200), index=True)
    descriptor_signature: Mapped[str | None] = mapped_column(String(320), nullable=True, index=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True, index=True)
    min_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence_keywords: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.95)
    times_confirmed: Mapped[int] = mapped_column(Integer, default=1)
    source: Mapped[str] = mapped_column(String(60), default="user_confirmation")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_confirmed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class ProfileAssignmentRule(Base):
    __tablename__ = "profile_assignment_rules"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("financial_profiles.id"), index=True)
    rule_type: Mapped[str] = mapped_column(String(50), index=True)
    match_value: Mapped[str] = mapped_column(String(240), index=True)
    secondary_value: Mapped[str | None] = mapped_column(String(240), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.95)
    source: Mapped[str] = mapped_column(String(50), default="user_confirmation")
    times_confirmed: Mapped[int] = mapped_column(Integer, default=1)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("household_id","rule_type","match_value","secondary_value", name="uq_profile_rule"),)

class MerchantMemory(Base):
    __tablename__ = "merchant_memory"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    merchant_normalized: Mapped[str] = mapped_column(String(240), index=True)
    preferred_category: Mapped[str] = mapped_column(String(80))
    source: Mapped[str] = mapped_column(String(40), default="user_correction")
    confidence: Mapped[float] = mapped_column(Float, default=0.95)
    rule_scope: Mapped[str] = mapped_column(String(80), default="merchant_preference")
    times_confirmed: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("household_id","merchant_normalized", name="uq_household_merchant_memory"),)

class Correction(Base):
    __tablename__ = "personal_corrections"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("personal_transactions.id"), index=True)
    field_name: Mapped[str] = mapped_column(String(80))
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Insight(Base):
    __tablename__ = "insights"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    insight_type: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(20), default="info")
    period_key: Mapped[str | None] = mapped_column(String(20), nullable=True)
    dismissed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Evidence(Base):
    __tablename__ = "personal_evidence"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    transaction_id: Mapped[int | None] = mapped_column(ForeignKey("personal_transactions.id"), nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(40))
    provider_message_id: Mapped[str | None] = mapped_column(String(180), nullable=True)
    evidence_type: Mapped[str] = mapped_column(String(50))
    merchant: Mapped[str | None] = mapped_column(String(200), nullable=True)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    subject: Mapped[str | None] = mapped_column(String(500), nullable=True)
    excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    match_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class AuditEvent(Base):
    __tablename__ = "personal_audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    entity_type: Mapped[str] = mapped_column(String(60))
    entity_id: Mapped[str] = mapped_column(String(120))
    detail_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

def create_schema():
    os.makedirs("data", exist_ok=True)
    Base.metadata.create_all(engine)
