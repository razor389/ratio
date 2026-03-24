//! SQLite-backed storage implementation with a cloud-migration-friendly interface boundary.

use std::path::Path;
use std::sync::{Arc, Mutex};

use anyhow::{anyhow, Context, Result};
use async_trait::async_trait;
use chrono::{DateTime, NaiveDate, NaiveDateTime, Utc};
use ratio_domain::{
    Assessment, AssessmentEvidenceLink, Company, CompanyVisibility, FactorKey, FactorScore,
    LlmDraftMetadata, PublicationStatus, SizingSnapshot, SourceDocument, SourceType,
};
use rusqlite::{params, Connection};
use serde_json::Value;

use crate::repositories::{AssessmentRepository, CompanyRepository, SourceDocumentRepository};

#[derive(Clone)]
pub struct SqliteStore {
    connection: Arc<Mutex<Connection>>,
}

impl SqliteStore {
    pub async fn connect(database_url: &str) -> Result<Self> {
        let path = parse_sqlite_path(database_url)?;
        if let Some(parent) = Path::new(&path).parent() {
            std::fs::create_dir_all(parent)?;
        }

        let connection = Connection::open(path)?;
        connection.pragma_update(None, "journal_mode", "WAL")?;

        Ok(Self {
            connection: Arc::new(Mutex::new(connection)),
        })
    }

    pub async fn migrate(&self) -> Result<()> {
        let sql = include_str!("../migrations/0001_initial.sql");
        let connection = self
            .connection
            .lock()
            .map_err(|_| anyhow!("sqlite connection lock poisoned"))?;
        connection.execute_batch(sql)?;
        Ok(())
    }

    pub async fn healthcheck(&self) -> Result<()> {
        let connection = self
            .connection
            .lock()
            .map_err(|_| anyhow!("sqlite connection lock poisoned"))?;
        connection.query_row("SELECT 1", [], |_row| Ok(()))?;
        Ok(())
    }
}

#[async_trait]
impl CompanyRepository for SqliteStore {
    async fn upsert_company(&self, company: &Company) -> Result<Company> {
        let connection = self
            .connection
            .lock()
            .map_err(|_| anyhow!("sqlite connection lock poisoned"))?;
        connection.execute(
            "INSERT INTO companies (
                ticker, company_name, display_name, sector, industry, description,
                is_tracked, is_published, visibility, display_order
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticker) DO UPDATE SET
                company_name = excluded.company_name,
                display_name = excluded.display_name,
                sector = excluded.sector,
                industry = excluded.industry,
                description = excluded.description,
                is_tracked = excluded.is_tracked,
                is_published = excluded.is_published,
                visibility = excluded.visibility,
                display_order = excluded.display_order,
                updated_at = CURRENT_TIMESTAMP",
            params![
                company.ticker,
                company.company_name,
                company.display_name,
                company.sector,
                company.industry,
                company.description,
                company.is_tracked,
                company.is_published,
                visibility_to_str(company.visibility),
                company.display_order,
            ],
        )?;

        let mut statement = connection.prepare(
            "SELECT id, ticker, company_name, display_name, sector, industry, description,
                    is_tracked, is_published, visibility, display_order, created_at, updated_at
             FROM companies
             WHERE ticker = ?",
        )?;

        statement
            .query_row([company.ticker.as_str()], map_company_row)
            .context("failed to fetch saved company")
    }

    async fn list_companies(&self) -> Result<Vec<Company>> {
        let connection = self
            .connection
            .lock()
            .map_err(|_| anyhow!("sqlite connection lock poisoned"))?;
        let mut statement = connection.prepare(
            "SELECT id, ticker, company_name, display_name, sector, industry, description,
                    is_tracked, is_published, visibility, display_order, created_at, updated_at
             FROM companies
             ORDER BY display_order ASC, ticker ASC",
        )?;

        let rows = statement.query_map([], map_company_row)?;
        rows.collect::<rusqlite::Result<Vec<_>>>()
            .map_err(Into::into)
    }
}

#[async_trait]
impl SourceDocumentRepository for SqliteStore {
    async fn insert_source_documents(&self, documents: &[SourceDocument]) -> Result<()> {
        let mut connection = self
            .connection
            .lock()
            .map_err(|_| anyhow!("sqlite connection lock poisoned"))?;
        let transaction = connection.transaction()?;

        for document in documents {
            transaction.execute(
                "INSERT INTO source_documents (
                    company_id, source_type, external_source_id, title, body_text, author_email,
                    source_timestamp, ingested_at, source_metadata_json, content_hash
                 ) VALUES (?, ?, ?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP), ?, ?)",
                params![
                    document.company_id,
                    source_type_to_str(document.source_type),
                    document.external_source_id,
                    document.title,
                    document.body_text,
                    document.author_email,
                    document.source_timestamp.map(|dt| dt.to_rfc3339()),
                    document.ingested_at.map(|dt| dt.to_rfc3339()),
                    document.source_metadata_json.to_string(),
                    document.content_hash,
                ],
            )?;
        }

        transaction.commit()?;
        Ok(())
    }

    async fn list_source_documents_for_company(
        &self,
        company_id: i64,
    ) -> Result<Vec<SourceDocument>> {
        let connection = self
            .connection
            .lock()
            .map_err(|_| anyhow!("sqlite connection lock poisoned"))?;
        let mut statement = connection.prepare(
            "SELECT id, company_id, source_type, external_source_id, title, body_text, author_email,
                    source_timestamp, ingested_at, source_metadata_json, content_hash
             FROM source_documents
             WHERE company_id = ?
             ORDER BY source_timestamp DESC, ingested_at DESC",
        )?;

        let rows = statement.query_map([company_id], map_source_document_row)?;
        rows.collect::<rusqlite::Result<Vec<_>>>()
            .map_err(Into::into)
    }
}

#[async_trait]
impl AssessmentRepository for SqliteStore {
    async fn insert_draft_assessment(&self, assessment: &Assessment) -> Result<Assessment> {
        let mut connection = self
            .connection
            .lock()
            .map_err(|_| anyhow!("sqlite connection lock poisoned"))?;
        let transaction = connection.transaction()?;

        let next_version: i32 = transaction.query_row(
            "SELECT COALESCE(MAX(version_number), 0) + 1 FROM assessments WHERE company_id = ?",
            [assessment.company_id],
            |row| row.get(0),
        )?;

        transaction.execute(
            "INSERT INTO assessments (
                company_id, version_number, status, created_by, updated_by, published_by, as_of_date,
                public_comment, is_public_comment_enabled, internal_notes, llm_provider, llm_model,
                llm_prompt_version, llm_assumptions_json, llm_confidence, raw_response,
                calculation_version, aggregate_score, relative_score, beta_like_score, base_position_size,
                suggested_position_size, published_at
             ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            params![
                assessment.company_id,
                next_version,
                publication_status_to_str(assessment.status),
                assessment.created_by,
                assessment.updated_by,
                assessment.published_by,
                assessment.as_of_date.map(|date| date.to_string()),
                assessment.public_comment,
                assessment.is_public_comment_enabled,
                assessment.internal_notes,
                assessment.llm_metadata.as_ref().and_then(|meta| meta.provider.clone()),
                assessment.llm_metadata.as_ref().and_then(|meta| meta.model.clone()),
                assessment.llm_metadata.as_ref().and_then(|meta| meta.prompt_version.clone()),
                serde_json::to_string(
                    &assessment
                        .llm_metadata
                        .as_ref()
                        .map(|meta| meta.assumptions.clone())
                        .unwrap_or_default(),
                )?,
                assessment.llm_metadata.as_ref().and_then(|meta| meta.confidence.clone()),
                assessment.llm_metadata.as_ref().and_then(|meta| meta.raw_response.clone()),
                assessment.calculation_version,
                assessment.sizing.aggregate_score,
                assessment.sizing.relative_score,
                assessment.sizing.beta_like_score,
                assessment.sizing.base_position_size,
                assessment.sizing.suggested_position_size,
                assessment.published_at.map(|dt| dt.to_rfc3339()),
            ],
        )?;

        let assessment_id = transaction.last_insert_rowid();

        for factor in &assessment.factors {
            transaction.execute(
                "INSERT INTO assessment_factors (
                    assessment_id, factor_key, factor_label, score, score_min, score_max,
                    internal_rationale, public_rationale_override, sort_order
                 ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                params![
                    assessment_id,
                    factor_key_to_str(factor.factor_key),
                    factor.factor_label,
                    factor.score,
                    factor.score_min,
                    factor.score_max,
                    factor.internal_rationale,
                    factor.public_rationale_override,
                    factor.sort_order,
                ],
            )?;
        }

        transaction.commit()?;

        let mut saved = assessment.clone();
        saved.id = Some(assessment_id);
        saved.version_number = next_version;
        Ok(saved)
    }

    async fn list_assessments_for_company(&self, company_id: i64) -> Result<Vec<Assessment>> {
        let connection = self
            .connection
            .lock()
            .map_err(|_| anyhow!("sqlite connection lock poisoned"))?;
        let mut statement = connection.prepare(
            "SELECT id, company_id, version_number, status, created_by, updated_by, published_by, as_of_date,
                    public_comment, is_public_comment_enabled, internal_notes, llm_provider, llm_model,
                    llm_prompt_version, llm_assumptions_json, llm_confidence, raw_response,
                    calculation_version, aggregate_score, relative_score, beta_like_score,
                    base_position_size, suggested_position_size, created_at, updated_at, published_at
             FROM assessments
             WHERE company_id = ?
             ORDER BY version_number DESC",
        )?;

        let assessment_rows = statement.query_map([company_id], |row| {
            Ok((
                row.get::<_, i64>("id")?,
                row.get::<_, i64>("company_id")?,
                row.get::<_, i32>("version_number")?,
                row.get::<_, String>("status")?,
                row.get::<_, Option<String>>("created_by")?,
                row.get::<_, Option<String>>("updated_by")?,
                row.get::<_, Option<String>>("published_by")?,
                row.get::<_, Option<String>>("as_of_date")?,
                row.get::<_, Option<String>>("public_comment")?,
                row.get::<_, bool>("is_public_comment_enabled")?,
                row.get::<_, Option<String>>("internal_notes")?,
                row.get::<_, Option<String>>("llm_provider")?,
                row.get::<_, Option<String>>("llm_model")?,
                row.get::<_, Option<String>>("llm_prompt_version")?,
                row.get::<_, String>("llm_assumptions_json")?,
                row.get::<_, Option<String>>("llm_confidence")?,
                row.get::<_, Option<String>>("raw_response")?,
                row.get::<_, String>("calculation_version")?,
                row.get::<_, i32>("aggregate_score")?,
                row.get::<_, f64>("relative_score")?,
                row.get::<_, f64>("beta_like_score")?,
                row.get::<_, f64>("base_position_size")?,
                row.get::<_, f64>("suggested_position_size")?,
                row.get::<_, Option<String>>("created_at")?,
                row.get::<_, Option<String>>("updated_at")?,
                row.get::<_, Option<String>>("published_at")?,
            ))
        })?;

        let mut assessments = Vec::new();
        for row in assessment_rows {
            let (
                assessment_id,
                company_id,
                version_number,
                status,
                created_by,
                updated_by,
                published_by,
                as_of_date,
                public_comment,
                is_public_comment_enabled,
                internal_notes,
                llm_provider,
                llm_model,
                llm_prompt_version,
                llm_assumptions_json,
                llm_confidence,
                raw_response,
                calculation_version,
                aggregate_score,
                relative_score,
                beta_like_score,
                base_position_size,
                suggested_position_size,
                created_at,
                updated_at,
                published_at,
            ) = row?;

            let mut factor_statement = connection.prepare(
                "SELECT factor_key, factor_label, score, score_min, score_max,
                        internal_rationale, public_rationale_override, sort_order
                 FROM assessment_factors
                 WHERE assessment_id = ?
                 ORDER BY sort_order ASC",
            )?;
            let factors = factor_statement
                .query_map([assessment_id], |factor_row| {
                    Ok(FactorScore {
                        factor_key: factor_key_from_str(
                            &factor_row.get::<_, String>("factor_key")?,
                        )
                        .map_err(map_anyhow_to_sqlite)?,
                        factor_label: factor_row.get("factor_label")?,
                        score: factor_row.get("score")?,
                        score_min: factor_row.get("score_min")?,
                        score_max: factor_row.get("score_max")?,
                        internal_rationale: factor_row.get("internal_rationale")?,
                        public_rationale_override: factor_row.get("public_rationale_override")?,
                        sort_order: factor_row.get("sort_order")?,
                    })
                })?
                .collect::<rusqlite::Result<Vec<_>>>()?;

            assessments.push(Assessment {
                id: Some(assessment_id),
                company_id,
                version_number,
                status: publication_status_from_str(&status)?,
                created_by,
                updated_by,
                published_by,
                as_of_date: parse_date_option(as_of_date.as_deref())?,
                public_comment,
                is_public_comment_enabled,
                internal_notes,
                calculation_version,
                sizing: SizingSnapshot {
                    aggregate_score,
                    relative_score,
                    beta_like_score,
                    base_position_size,
                    suggested_position_size,
                },
                factors,
                evidence_links: Vec::<AssessmentEvidenceLink>::new(),
                llm_metadata: Some(LlmDraftMetadata {
                    provider: llm_provider,
                    model: llm_model,
                    prompt_version: llm_prompt_version,
                    assumptions: serde_json::from_str(&llm_assumptions_json).unwrap_or_default(),
                    confidence: llm_confidence,
                    raw_response,
                }),
                created_at: parse_datetime_option(created_at.as_deref())?,
                updated_at: parse_datetime_option(updated_at.as_deref())?,
                published_at: parse_datetime_option(published_at.as_deref())?,
            });
        }

        Ok(assessments)
    }
}

fn map_company_row(row: &rusqlite::Row<'_>) -> rusqlite::Result<Company> {
    Ok(Company {
        id: Some(row.get("id")?),
        ticker: row.get("ticker")?,
        company_name: row.get("company_name")?,
        display_name: row.get("display_name")?,
        sector: row.get("sector")?,
        industry: row.get("industry")?,
        description: row.get("description")?,
        visibility: visibility_from_str(&row.get::<_, String>("visibility")?)
            .map_err(map_anyhow_to_sqlite)?,
        is_tracked: row.get("is_tracked")?,
        is_published: row.get("is_published")?,
        display_order: row.get("display_order")?,
        created_at: parse_datetime_option(row.get::<_, Option<String>>("created_at")?.as_deref())
            .map_err(map_anyhow_to_sqlite)?,
        updated_at: parse_datetime_option(row.get::<_, Option<String>>("updated_at")?.as_deref())
            .map_err(map_anyhow_to_sqlite)?,
    })
}

fn map_source_document_row(row: &rusqlite::Row<'_>) -> rusqlite::Result<SourceDocument> {
    Ok(SourceDocument {
        id: Some(row.get("id")?),
        company_id: row.get("company_id")?,
        source_type: source_type_from_str(&row.get::<_, String>("source_type")?)
            .map_err(map_anyhow_to_sqlite)?,
        external_source_id: row.get("external_source_id")?,
        title: row.get("title")?,
        body_text: row.get("body_text")?,
        author_email: row.get("author_email")?,
        source_timestamp: parse_datetime_option(
            row.get::<_, Option<String>>("source_timestamp")?.as_deref(),
        )
        .map_err(map_anyhow_to_sqlite)?,
        ingested_at: parse_datetime_option(row.get::<_, Option<String>>("ingested_at")?.as_deref())
            .map_err(map_anyhow_to_sqlite)?,
        source_metadata_json: row
            .get::<_, String>("source_metadata_json")
            .ok()
            .and_then(|value| serde_json::from_str::<Value>(&value).ok())
            .unwrap_or(Value::Null),
        content_hash: row.get("content_hash")?,
    })
}

fn parse_sqlite_path(database_url: &str) -> Result<String> {
    database_url
        .strip_prefix("sqlite://")
        .map(str::to_string)
        .ok_or_else(|| anyhow!("DATABASE_URL must use sqlite:// for the local backend scaffold"))
}

fn parse_datetime_option(value: Option<&str>) -> Result<Option<DateTime<Utc>>> {
    let Some(value) = value else {
        return Ok(None);
    };

    if let Ok(parsed) = DateTime::parse_from_rfc3339(value) {
        return Ok(Some(parsed.with_timezone(&Utc)));
    }

    let parsed = NaiveDateTime::parse_from_str(value, "%Y-%m-%d %H:%M:%S")
        .with_context(|| format!("failed to parse datetime: {value}"))?;
    Ok(Some(DateTime::<Utc>::from_naive_utc_and_offset(
        parsed, Utc,
    )))
}

fn parse_date_option(value: Option<&str>) -> Result<Option<NaiveDate>> {
    let Some(value) = value else {
        return Ok(None);
    };
    Ok(Some(
        NaiveDate::parse_from_str(value, "%Y-%m-%d")
            .with_context(|| format!("failed to parse date: {value}"))?,
    ))
}

fn visibility_to_str(value: CompanyVisibility) -> &'static str {
    match value {
        CompanyVisibility::DraftOnly => "draft_only",
        CompanyVisibility::Published => "published",
        CompanyVisibility::Hidden => "hidden",
    }
}

fn visibility_from_str(value: &str) -> Result<CompanyVisibility> {
    match value {
        "draft_only" => Ok(CompanyVisibility::DraftOnly),
        "published" => Ok(CompanyVisibility::Published),
        "hidden" => Ok(CompanyVisibility::Hidden),
        _ => Err(anyhow!("unknown company visibility: {value}")),
    }
}

fn source_type_to_str(value: SourceType) -> &'static str {
    match value {
        SourceType::OutlookEmail => "outlook_email",
        SourceType::ForumPost => "forum_post",
        SourceType::InternalNote => "internal_note",
        SourceType::ExternalLink => "external_link",
    }
}

fn source_type_from_str(value: &str) -> Result<SourceType> {
    match value {
        "outlook_email" => Ok(SourceType::OutlookEmail),
        "forum_post" => Ok(SourceType::ForumPost),
        "internal_note" => Ok(SourceType::InternalNote),
        "external_link" => Ok(SourceType::ExternalLink),
        _ => Err(anyhow!("unknown source type: {value}")),
    }
}

fn publication_status_to_str(value: PublicationStatus) -> &'static str {
    match value {
        PublicationStatus::Draft => "draft",
        PublicationStatus::Published => "published",
        PublicationStatus::Archived => "archived",
    }
}

fn publication_status_from_str(value: &str) -> Result<PublicationStatus> {
    match value {
        "draft" => Ok(PublicationStatus::Draft),
        "published" => Ok(PublicationStatus::Published),
        "archived" => Ok(PublicationStatus::Archived),
        _ => Err(anyhow!("unknown publication status: {value}")),
    }
}

fn factor_key_to_str(value: FactorKey) -> &'static str {
    match value {
        FactorKey::Debt => "debt",
        FactorKey::MarketShareChange => "market_share_change",
        FactorKey::MarketDefinitionChange => "market_definition_change",
        FactorKey::RelativeValuation => "relative_valuation",
    }
}

fn factor_key_from_str(value: &str) -> Result<FactorKey> {
    match value {
        "debt" => Ok(FactorKey::Debt),
        "market_share_change" => Ok(FactorKey::MarketShareChange),
        "market_definition_change" => Ok(FactorKey::MarketDefinitionChange),
        "relative_valuation" => Ok(FactorKey::RelativeValuation),
        _ => Err(anyhow!("unknown factor key: {value}")),
    }
}

fn map_anyhow_to_sqlite(error: anyhow::Error) -> rusqlite::Error {
    rusqlite::Error::FromSqlConversionFailure(
        0,
        rusqlite::types::Type::Text,
        Box::new(std::io::Error::new(
            std::io::ErrorKind::InvalidData,
            error.to_string(),
        )),
    )
}
