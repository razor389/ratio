//! Admin-only source documents captured from internal evidence systems.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SourceType {
    OutlookEmail,
    ForumPost,
    InternalNote,
    ExternalLink,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SourceDocument {
    pub id: Option<i64>,
    pub company_id: i64,
    pub source_type: SourceType,
    pub external_source_id: Option<String>,
    pub title: Option<String>,
    pub body_text: String,
    pub author_email: Option<String>,
    pub source_timestamp: Option<DateTime<Utc>>,
    pub ingested_at: Option<DateTime<Utc>>,
    pub source_metadata_json: serde_json::Value,
    pub content_hash: Option<String>,
}
