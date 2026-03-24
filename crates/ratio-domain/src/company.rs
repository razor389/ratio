//! Company entities shared by admin and public backend layers.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum CompanyVisibility {
    DraftOnly,
    Published,
    Hidden,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Company {
    pub id: Option<i64>,
    pub ticker: String,
    pub company_name: String,
    pub display_name: Option<String>,
    pub sector: Option<String>,
    pub industry: Option<String>,
    pub description: Option<String>,
    pub visibility: CompanyVisibility,
    pub is_tracked: bool,
    pub is_published: bool,
    pub display_order: i32,
    pub created_at: Option<DateTime<Utc>>,
    pub updated_at: Option<DateTime<Utc>>,
}
