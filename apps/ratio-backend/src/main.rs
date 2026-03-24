//! Backend application entrypoint with logging, DB bootstrap, and a health endpoint.

use anyhow::Result;
use axum::{extract::State, response::IntoResponse, routing::get, Router};
use ratio_config::{init_logging, Settings};
use ratio_storage::{bootstrap_database, SqliteStore};
use std::sync::Arc;
use tracing::{info, info_span};

#[derive(Clone)]
struct AppState {
    store: Arc<SqliteStore>,
}

#[tokio::main]
async fn main() -> Result<()> {
    let settings = Settings::from_env()?;
    init_logging(&settings)?;
    let app_span = info_span!(
        "runtime",
        service = %settings.app_name,
        runtime = "rust",
        environment = %settings.environment,
        component = "api"
    );
    let _app_guard = app_span.enter();

    std::fs::create_dir_all(&settings.data_dir)?;
    std::fs::create_dir_all(&settings.output_dir)?;

    let store = Arc::new(bootstrap_database(&settings).await?);
    let app = Router::new()
        .route("/healthz", get(healthcheck))
        .with_state(AppState { store });

    let listener = tokio::net::TcpListener::bind(settings.server.bind_address()).await?;
    info!(addr = %listener.local_addr()?, "ratio backend listening");
    axum::serve(listener, app).await?;

    Ok(())
}

async fn healthcheck(State(state): State<AppState>) -> impl IntoResponse {
    match state.store.healthcheck().await {
        Ok(()) => "ok",
        Err(_) => "degraded",
    }
}
