//! Assessment, factor, and sizing entities for the Ratio methodology.

use chrono::{DateTime, NaiveDate, Utc};
use serde::{Deserialize, Serialize};
use thiserror::Error;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum PublicationStatus {
    Draft,
    Published,
    Archived,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum FactorKey {
    Debt,
    MarketShareChange,
    MarketDefinitionChange,
    RelativeValuation,
}

impl FactorKey {
    pub fn label(self) -> &'static str {
        match self {
            Self::Debt => "Debt",
            Self::MarketShareChange => "Change in Market Share",
            Self::MarketDefinitionChange => "Change in Definition of Market",
            Self::RelativeValuation => "Relative Valuation",
        }
    }
}

#[derive(Debug, Error)]
pub enum DomainError {
    #[error("{field} must be between {min} and {max}, got {value}")]
    InvalidScore {
        field: &'static str,
        min: i32,
        max: i32,
        value: i32,
    },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FourFactorScores {
    pub debt: i32,
    pub market_share_change: i32,
    pub market_definition_change: i32,
    pub relative_valuation: i32,
}

impl FourFactorScores {
    pub fn validate(&self, min: i32, max: i32) -> Result<(), DomainError> {
        for (field, value) in [
            ("debt", self.debt),
            ("market_share_change", self.market_share_change),
            ("market_definition_change", self.market_definition_change),
            ("relative_valuation", self.relative_valuation),
        ] {
            if value < min || value > max {
                return Err(DomainError::InvalidScore {
                    field,
                    min,
                    max,
                    value,
                });
            }
        }
        Ok(())
    }

    pub fn total(&self) -> i32 {
        self.debt
            + self.market_share_change
            + self.market_definition_change
            + self.relative_valuation
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FactorScore {
    pub factor_key: FactorKey,
    pub factor_label: String,
    pub score: i32,
    pub score_min: i32,
    pub score_max: i32,
    pub internal_rationale: Option<String>,
    pub public_rationale_override: Option<String>,
    pub sort_order: i32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AssessmentEvidenceLink {
    pub id: Option<i64>,
    pub source_document_id: i64,
    pub factor_key: Option<FactorKey>,
    pub relevance_rank: i32,
    pub evidence_note: Option<String>,
    pub used_by_llm: bool,
    pub used_in_final_review: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SizingSnapshot {
    pub aggregate_score: i32,
    pub relative_score: f64,
    pub beta_like_score: f64,
    pub base_position_size: f64,
    pub suggested_position_size: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LlmDraftMetadata {
    pub provider: Option<String>,
    pub model: Option<String>,
    pub prompt_version: Option<String>,
    pub assumptions: Vec<String>,
    pub confidence: Option<String>,
    pub raw_response: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Assessment {
    pub id: Option<i64>,
    pub company_id: i64,
    pub version_number: i32,
    pub status: PublicationStatus,
    pub created_by: Option<String>,
    pub updated_by: Option<String>,
    pub published_by: Option<String>,
    pub as_of_date: Option<NaiveDate>,
    pub public_comment: Option<String>,
    pub is_public_comment_enabled: bool,
    pub internal_notes: Option<String>,
    pub calculation_version: String,
    pub sizing: SizingSnapshot,
    pub factors: Vec<FactorScore>,
    pub evidence_links: Vec<AssessmentEvidenceLink>,
    pub llm_metadata: Option<LlmDraftMetadata>,
    pub created_at: Option<DateTime<Utc>>,
    pub updated_at: Option<DateTime<Utc>>,
    pub published_at: Option<DateTime<Utc>>,
}
