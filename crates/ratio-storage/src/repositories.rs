//! Repository traits used by services so storage can evolve independently.

use anyhow::Result;
use async_trait::async_trait;

use ratio_domain::{Assessment, Company, SourceDocument};

#[async_trait]
pub trait CompanyRepository {
    async fn upsert_company(&self, company: &Company) -> Result<Company>;
    async fn list_companies(&self) -> Result<Vec<Company>>;
}

#[async_trait]
pub trait SourceDocumentRepository {
    async fn insert_source_documents(&self, documents: &[SourceDocument]) -> Result<()>;
    async fn list_source_documents_for_company(
        &self,
        company_id: i64,
    ) -> Result<Vec<SourceDocument>>;
}

#[async_trait]
pub trait AssessmentRepository {
    async fn insert_draft_assessment(&self, assessment: &Assessment) -> Result<Assessment>;
    async fn list_assessments_for_company(&self, company_id: i64) -> Result<Vec<Assessment>>;
}
