"""Application service for drafting, revising, and publishing assessments."""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..core.config import Settings, get_settings
from ..domain import (
    AssessmentRecord,
    CompanyRecord,
    CompanyVisibility,
    FactorAssessment,
    FactorScores,
    PublicationStatus,
)
from ..db.repositories import AssessmentRepository, CompanyRepository
from .sizing import calculate_sizing


class AssessmentService:
    """Coordinate company persistence, sizing, and publication state changes."""

    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.companies = CompanyRepository(session)
        self.assessments = AssessmentRepository(session)

    def create_or_update_company(self, ticker: str, company_name: str) -> CompanyRecord:
        """Create a company if needed or refresh its display name."""
        company = CompanyRecord(ticker=ticker.upper(), company_name=company_name)
        saved = self.companies.save(company)
        self.session.commit()
        return saved

    def create_draft_assessment(
        self,
        company_id: int,
        scores: FactorScores,
        *,
        public_comment: str | None = None,
        public_comment_enabled: bool = False,
        methodology_version: str | None = None,
        internal_notes: str | None = None,
        created_by: str | None = None,
    ) -> AssessmentRecord:
        """Create a new draft assessment revision from factor scores."""
        sizing = calculate_sizing(scores, self.settings)
        factors = [
            FactorAssessment("debt", "Debt", scores.debt, internal_rationale=None, sort_order=1),
            FactorAssessment("market_share_change", "Change in Market Share", scores.market_share_change, internal_rationale=None, sort_order=2),
            FactorAssessment("market_definition_change", "Change in Definition of Market", scores.market_definition_change, internal_rationale=None, sort_order=3),
            FactorAssessment("relative_valuation", "Relative Valuation", scores.relative_valuation, internal_rationale=None, sort_order=4),
        ]
        assessment = AssessmentRecord(
            company_id=company_id,
            factor_scores=scores,
            sizing=sizing,
            aggregate_score=sizing.total_score,
            relative_score=sizing.normalized_score,
            beta_like_score=sizing.custom_beta,
            status=PublicationStatus.DRAFT,
            calculation_version=methodology_version or self.settings.default_methodology_version,
            created_by=created_by,
            updated_by=created_by,
            public_comment=public_comment,
            public_comment_enabled=public_comment_enabled,
            internal_notes=internal_notes,
            factors=factors,
        )
        saved = self.assessments.save(assessment)
        self.session.commit()
        return saved

    def publish_assessment(self, assessment_id: int, *, published_by: str | None = None, notes: str | None = None) -> AssessmentRecord:
        """Publish an existing assessment and expose its company publicly."""
        published = self.assessments.publish(assessment_id, published_by=published_by, notes=notes)
        company = self.companies.get(published.company_id)
        if company is None:
            raise ValueError(f"Company id {published.company_id} was not found")

        company.visibility = CompanyVisibility.PUBLISHED
        company.is_published = True
        self.companies.save(company)
        self.session.commit()
        return published
