"""ORM models aligned to the backend-first data model in the project spec."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class CompanyModel(TimestampMixin, Base):
    """Tracked company metadata for admin and public surfaces."""

    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    company_name: Mapped[str] = mapped_column(String(255), index=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sector: Mapped[str | None] = mapped_column(String(128), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(128), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    visibility: Mapped[str] = mapped_column(String(32), default="draft_only", index=True)
    is_tracked: Mapped[bool] = mapped_column(Boolean, default=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    assessments: Mapped[list["AssessmentModel"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    source_documents: Mapped[list["SourceDocumentModel"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    publish_events: Mapped[list["PublishEventModel"]] = relationship(back_populates="company", cascade="all, delete-orphan")


class AssessmentModel(TimestampMixin, Base):
    """Versioned company assessment containing draft and published fields."""

    __tablename__ = "assessments"
    __table_args__ = (
        UniqueConstraint("company_id", "version_number", name="uq_assessment_company_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    version_number: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    published_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    calculation_version: Mapped[str] = mapped_column(String(64), default="beta-v1")
    public_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_public_comment_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    internal_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_provider: Mapped[str | None] = mapped_column(String(128), nullable=True)
    llm_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    llm_prompt_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    as_of_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    aggregate_score: Mapped[int] = mapped_column(Integer, default=0)
    relative_score: Mapped[float] = mapped_column(default=0.0)
    beta_like_score: Mapped[float] = mapped_column(default=0.0)
    suggested_position_size: Mapped[float] = mapped_column(default=0.0)
    llm_assumptions_json: Mapped[list] = mapped_column(JSON, default=list)
    raw_payload_json: Mapped[dict] = mapped_column(JSON, default=dict)

    company: Mapped["CompanyModel"] = relationship(back_populates="assessments")
    factors: Mapped[list["AssessmentFactorModel"]] = relationship(back_populates="assessment", cascade="all, delete-orphan")
    evidence_links: Mapped[list["AssessmentEvidenceLinkModel"]] = relationship(back_populates="assessment", cascade="all, delete-orphan")


class SourceDocumentModel(Base):
    """Admin-only source documents ingested from Outlook, forum posts, or notes."""

    __tablename__ = "source_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(32), index=True)
    external_source_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body_text: Mapped[str] = mapped_column(Text)
    author_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ingested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    content_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_uri: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    company: Mapped["CompanyModel"] = relationship(back_populates="source_documents")
    assessment_links: Mapped[list["AssessmentEvidenceLinkModel"]] = relationship(back_populates="source_document")


class AssessmentFactorModel(Base):
    """Factor-level scores and rationale for one assessment revision."""

    __tablename__ = "assessment_factors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assessment_id: Mapped[int] = mapped_column(ForeignKey("assessments.id"), index=True)
    factor_key: Mapped[str] = mapped_column(String(64), index=True)
    factor_label: Mapped[str] = mapped_column(String(128))
    score: Mapped[int] = mapped_column(Integer)
    score_min: Mapped[int] = mapped_column(Integer, default=0)
    score_max: Mapped[int] = mapped_column(Integer, default=10)
    internal_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    public_rationale_override: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    assessment: Mapped["AssessmentModel"] = relationship(back_populates="factors")


class AssessmentEvidenceLinkModel(Base):
    """Associations between assessments, factors, and source documents."""

    __tablename__ = "assessment_evidence_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assessment_id: Mapped[int] = mapped_column(ForeignKey("assessments.id"), index=True)
    factor_key: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    source_document_id: Mapped[int] = mapped_column(ForeignKey("source_documents.id"), index=True)
    relevance_rank: Mapped[int] = mapped_column(Integer, default=0)
    evidence_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    used_by_llm: Mapped[bool] = mapped_column(Boolean, default=False)
    used_in_final_review: Mapped[bool] = mapped_column(Boolean, default=False)

    assessment: Mapped["AssessmentModel"] = relationship(back_populates="evidence_links")
    source_document: Mapped["SourceDocumentModel"] = relationship(back_populates="assessment_links")


class AdminUserModel(TimestampMixin, Base):
    """Authenticated admin users who can review and publish assessments."""

    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(64))
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    auth_provider_subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(64), default="active")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditEventModel(Base):
    """Audit trail for admin mutations and publish operations."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(128), index=True)
    entity_type: Mapped[str] = mapped_column(String(128), index=True)
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    before_json: Mapped[dict] = mapped_column(JSON, default=dict)
    after_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PublishEventModel(Base):
    """Publication trail for historical visibility changes."""

    __tablename__ = "publish_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    assessment_id: Mapped[int] = mapped_column(ForeignKey("assessments.id"), index=True)
    published_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    company: Mapped["CompanyModel"] = relationship(back_populates="publish_events")
