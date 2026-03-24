//! Database bootstrap and migration helpers.

use anyhow::Result;
use tracing::info;

use crate::sqlite::SqliteStore;
use ratio_config::Settings;

pub async fn bootstrap_database(settings: &Settings) -> Result<SqliteStore> {
    let store = SqliteStore::connect(&settings.database.url).await?;
    store.migrate().await?;

    info!(
        database_url = %settings.database.url,
        "database bootstrap complete"
    );

    Ok(store)
}
