//! Shared tracing subscriber setup for all backend processes.

use anyhow::Result;
use tracing_subscriber::fmt;
use tracing_subscriber::layer::SubscriberExt;
use tracing_subscriber::util::SubscriberInitExt;
use tracing_subscriber::EnvFilter;

use crate::settings::{LogFormat, Settings};

pub fn init_logging(settings: &Settings) -> Result<()> {
    let env_filter = EnvFilter::try_new(settings.log_level.clone())
        .or_else(|_| EnvFilter::try_new("info"))
        .expect("static log level fallback should be valid");

    let fmt_layer = fmt::layer().with_target(true);

    match settings.log_format {
        LogFormat::Json => tracing_subscriber::registry()
            .with(env_filter)
            .with(fmt_layer.json().flatten_event(true).with_current_span(true))
            .try_init()?,
        LogFormat::Text => tracing_subscriber::registry()
            .with(env_filter)
            .with(fmt_layer.compact())
            .try_init()?,
    }

    Ok(())
}
