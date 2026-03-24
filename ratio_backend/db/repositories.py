"""Repository layer that isolates database details from backend services."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..domain import (
    AssessmentEvidenceLink,
    AssessmentRecord,
    CompanyRecord,
    CompanyVisibility,
    EvidenceItem,
    EvidenceSourceType,
    FactorAssessment,
    FactorScores,
    LLMDraftMetadata,
    PublicationStatus,
    SizingResult,
)
from .models import (
    AssessmentEvidenceLinkModel,
    AssessmentFactorModel,
    AssessmentModel,
    CompanyModel,
    PublishEventModel,
    SourceDocumentModel,
)


class CompanyRepository:
    """Persistence operations for company metadata."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def list_all(self) -> list[CompanyRecord]:
        rows = self.session.scalars(select(CompanyModel).order_by(CompanyModel.display_order, CompanyModel.ticker)).all()
        return [self._to_domain(row) for row in rows]

    def get(self, company_id: int) -> CompanyRecord | None:
        row = self.session.get(CompanyModel, company_id)
        return self._to_domain(row) if row else None

    def get_by_ticker(self, ticker: str) -> CompanyRecord | None:
        row = self.session.scalar(select(CompanyModel).where(CompanyModel.ticker == ticker.upper()))
        return self._to_domain(row) if row else None

    def save(self, company: CompanyRecord) -> CompanyRecord:
        row = None
        if company.id is not None:
            row = self.session.get(CompanyModel, company.id)
        if row is None:
            row = self.session.scalar(select(CompanyModel).where(CompanyModel.ticker == company.ticker.upper()))
        if row is None:
            row = CompanyModel(ticker=company.ticker.upper(), company_name=company.company_name)
            self.session.add(row)

        row.ticker = company.ticker.upper()
        row.company_name = company.company_name
        row.display_name = company.display_name
        row.sector = company.sector
        row.industry = company.industry
        row.description = company.description
        row.visibility = company.visibility.value
        row.is_tracked = company.is_tracked
        row.is_published = company.is_published
        row.display_order = company.display_order
        row.metadata_json = company.metadata
        self.session.flush()
        return self._to_domain(row)

    @staticmethod
    def _to_domain(row: CompanyModel) -> CompanyRecord:
        return CompanyRecord(
            id=row.id,
            ticker=row.ticker,
            company_name=row.company_name,
            display_name=row.display_name,
            sector=row.sector,
            industry=row.industry,
            description=row.description,
            visibility=CompanyVisibility(row.visibility),
            is_tracked=row.is_tracked,
            is_published=row.is_published,
            display_order=row.display_order,
            created_at=row.created_at,
            updated_at=row.updated_at,
            metadata=row.metadata_json or {},
        )


class SourceDocumentRepository:
    """Persistence operations for admin-only source documents."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def list_for_company(self, company_id: int) -> list[EvidenceItem]:
        rows = self.session.scalars(
            select(SourceDocumentModel)
            .where(SourceDocumentModel.company_id == company_id)
            .order_by(SourceDocumentModel.source_timestamp.desc())
        ).all()
        return [self._to_domain(row) for row in rows]

    def save_many(self, documents: Iterable[EvidenceItem]) -> None:
        for document in documents:
            row = SourceDocumentModel(
                company_id=document.company_id,
                source_type=document.source_type.value,
                external_source_id=document.external_source_id,
                title=document.title,
                body_text=document.content,
                author_email=document.author_email,
                source_timestamp=document.source_timestamp,
                ingested_at=document.ingested_at or datetime.now(timezone.utc),
                source_uri=document.source_uri,
                content_hash=document.content_hash,
                source_metadata_json=document.source_metadata or {},
            )
            self.session.add(row)
        self.session.flush()

    @staticmethod
    def _to_domain(row: SourceDocumentModel) -> EvidenceItem:
        return EvidenceItem(
            id=row.id,
            company_id=row.company_id,
            source_type=EvidenceSourceType(row.source_type),
            title=row.title or "",
            content=row.body_text,
            external_source_id=row.external_source_id,
            author_email=row.author_email,
            source_timestamp=row.source_timestamp,
            ingested_at=row.ingested_at,
            source_uri=row.source_uri,
            content_hash=row.content_hash,
            source_metadata=row.source_metadata_json or {},
        )


class AssessmentRepository:
    """Persistence operations for versioned assessments and their factors."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, assessment_id: int) -> AssessmentRecord | None:
        row = self.session.scalar(
            select(AssessmentModel)
            .where(AssessmentModel.id == assessment_id)
            .options(
                selectinload(AssessmentModel.factors),
                selectinload(AssessmentModel.evidence_links),
            )
        )
        return self._to_domain(row) if row else None

    def list_for_company(self, company_id: int) -> list[AssessmentRecord]:
        rows = self.session.scalars(
            select(AssessmentModel)
            .where(AssessmentModel.company_id == company_id)
            .order_by(AssessmentModel.version_number.desc())
            .options(
                selectinload(AssessmentModel.factors),
                selectinload(AssessmentModel.evidence_links),
            )
        ).all()
        return [self._to_domain(row) for row in rows]

    def get_active_draft(self, company_id: int) -> AssessmentRecord | None:
        row = self.session.scalar(
            select(AssessmentModel)
            .where(
                AssessmentModel.company_id == company_id,
                AssessmentModel.status == PublicationStatus.DRAFT.value,
            )
            .order_by(AssessmentModel.version_number.desc())
            .options(
                selectinload(AssessmentModel.factors),
                selectinload(AssessmentModel.evidence_links),
            )
        )
        return self._to_domain(row) if row else None

    def get_published(self, company_id: int) -> AssessmentRecord | None:
        row = self.session.scalar(
            select(AssessmentModel)
            .where(
                AssessmentModel.company_id == company_id,
                AssessmentModel.status == PublicationStatus.PUBLISHED.value,
            )
            .options(
                selectinload(AssessmentModel.factors),
                selectinload(AssessmentModel.evidence_links),
            )
        )
        return self._to_domain(row) if row else None

    def save(self, assessment: AssessmentRecord, *, version_number: int | None = None) -> AssessmentRecord:
        if assessment.id is not None:
            row = self.session.scalar(
                select(AssessmentModel)
                .where(AssessmentModel.id == assessment.id)
                .options(
                    selectinload(AssessmentModel.factors),
                    selectinload(AssessmentModel.evidence_links),
                )
            )
        else:
            row = AssessmentModel(
                company_id=assessment.company_id,
                version_number=version_number or self._next_version_number(assessment.company_id),
            )
            self.session.add(row)
            self.session.flush()

        if row is None:
            raise ValueError(f"Assessment id {assessment.id} was not found")

        row.status = assessment.status.value
        row.created_by = assessment.created_by
        row.updated_by = assessment.updated_by
        row.published_by = assessment.published_by
        row.calculation_version = assessment.calculation_version
        row.public_comment = assessment.public_comment
        row.is_public_comment_enabled = assessment.public_comment_enabled
        row.internal_notes = assessment.internal_notes
        row.as_of_date = assessment.as_of_date
        row.published_at = assessment.published_at
        row.aggregate_score = assessment.aggregate_score
        row.relative_score = assessment.relative_score
        row.beta_like_score = assessment.beta_like_score
        row.suggested_position_size = assessment.sizing.suggested_position_size
        row.llm_provider = assessment.llm_metadata.provider if assessment.llm_metadata else None
        row.llm_model = assessment.llm_metadata.model if assessment.llm_metadata else None
        row.llm_prompt_version = assessment.llm_metadata.prompt_version if assessment.llm_metadata else None
        row.llm_assumptions_json = assessment.llm_metadata.assumptions if assessment.llm_metadata else []
        row.raw_payload_json = {
            "factor_scores": assessment.factor_scores.as_dict(),
            "calculations": assessment.sizing.as_dict(),
            "raw_response": assessment.llm_metadata.raw_response if assessment.llm_metadata else None,
        }

        row.factors.clear()
        for factor in assessment.factors:
            row.factors.append(
                AssessmentFactorModel(
                    factor_key=factor.factor_key,
                    factor_label=factor.factor_label,
                    score=factor.score,
                    score_min=factor.score_min,
                    score_max=factor.score_max,
                    internal_rationale=factor.internal_rationale,
                    public_rationale_override=factor.public_rationale_override,
                    sort_order=factor.sort_order,
                )
            )

        row.evidence_links.clear()
        for link in assessment.evidence_links:
            row.evidence_links.append(
                AssessmentEvidenceLinkModel(
                    factor_key=link.factor_key,
                    source_document_id=link.source_document_id,
                    relevance_rank=link.relevance_rank,
                    evidence_note=link.evidence_note,
                    used_by_llm=link.used_by_llm,
                    used_in_final_review=link.used_in_final_review,
                )
            )

        self.session.flush()
        return self._to_domain(row)

    def archive_published_for_company(self, company_id: int) -> None:
        rows = self.session.scalars(
            select(AssessmentModel).where(
                AssessmentModel.company_id == company_id,
                AssessmentModel.status == PublicationStatus.PUBLISHED.value,
            )
        ).all()
        for row in rows:
            row.status = PublicationStatus.ARCHIVED.value
        self.session.flush()

    def publish(self, assessment_id: int, *, published_by: str | None = None, notes: str | None = None) -> AssessmentRecord:
        row = self.session.scalar(
            select(AssessmentModel)
            .where(AssessmentModel.id == assessment_id)
            .options(
                selectinload(AssessmentModel.factors),
                selectinload(AssessmentModel.evidence_links),
            )
        )
        if row is None:
            raise ValueError(f"Assessment id {assessment_id} was not found")
        if len(row.factors) != 4:
            raise ValueError("Assessment draft is incomplete and cannot be published")
        if any(factor.score is None for factor in row.factors):
            raise ValueError("Assessment draft contains unscored factors and cannot be published")

        self.archive_published_for_company(row.company_id)
        row.status = PublicationStatus.PUBLISHED.value
        row.published_by = published_by
        row.published_at = datetime.now(timezone.utc)

        company = self.session.get(CompanyModel, row.company_id)
        if company is None:
            raise ValueError(f"Company id {row.company_id} was not found")
        company.visibility = CompanyVisibility.PUBLISHED.value
        company.is_published = True

        self.session.add(
            PublishEventModel(
                company_id=row.company_id,
                assessment_id=row.id,
                published_by=published_by,
                published_at=row.published_at,
                notes=notes,
            )
        )

        self.session.flush()
        return self._to_domain(row)

    def _next_version_number(self, company_id: int) -> int:
        versions = self.session.scalars(
            select(AssessmentModel.version_number).where(AssessmentModel.company_id == company_id)
        ).all()
        return (max(versions) + 1) if versions else 1

    @staticmethod
    def _to_domain(row: AssessmentModel) -> AssessmentRecord:
        score_map = {factor.factor_key: factor.score for factor in row.factors}
        factor_scores = FactorScores(
            debt=int(score_map.get("debt", 0)),
            market_share_change=int(score_map.get("market_share_change", 0)),
            market_definition_change=int(score_map.get("market_definition_change", 0)),
            relative_valuation=int(score_map.get("relative_valuation", 0)),
        )
        sizing = SizingResult(
            total_score=row.aggregate_score,
            normalized_score=row.relative_score,
            custom_beta=row.beta_like_score,
            base_position_size=(row.raw_payload_json or {}).get("calculations", {}).get("base_position_size", 0.0),
            suggested_position_size=row.suggested_position_size,
        )
        return AssessmentRecord(
            id=row.id,
            company_id=row.company_id,
            factor_scores=factor_scores,
            sizing=sizing,
            aggregate_score=row.aggregate_score,
            relative_score=row.relative_score,
            beta_like_score=row.beta_like_score,
            status=PublicationStatus(row.status),
            calculation_version=row.calculation_version,
            created_by=row.created_by,
            updated_by=row.updated_by,
            published_by=row.published_by,
            public_comment=row.public_comment,
            public_comment_enabled=row.is_public_comment_enabled,
            internal_notes=row.internal_notes,
            llm_metadata=LLMDraftMetadata(
                provider=row.llm_provider,
                model=row.llm_model,
                prompt_version=row.llm_prompt_version,
                assumptions=list(row.llm_assumptions_json or []),
                raw_response=(row.raw_payload_json or {}).get("raw_response"),
            ),
            as_of_date=row.as_of_date,
            published_at=row.published_at,
            factors=[
                FactorAssessment(
                    factor_key=factor.factor_key,
                    factor_label=factor.factor_label,
                    score=factor.score,
                    score_min=factor.score_min,
                    score_max=factor.score_max,
                    internal_rationale=factor.internal_rationale,
                    public_rationale_override=factor.public_rationale_override,
                    sort_order=factor.sort_order,
                )
                for factor in sorted(row.factors, key=lambda item: item.sort_order)
            ],
            evidence_links=[
                AssessmentEvidenceLink(
                    id=link.id,
                    factor_key=link.factor_key,
                    source_document_id=link.source_document_id,
                    relevance_rank=link.relevance_rank,
                    evidence_note=link.evidence_note,
                    used_by_llm=link.used_by_llm,
                    used_in_final_review=link.used_in_final_review,
                )
                for link in row.evidence_links
            ],
        )
