//! Environment-driven settings for the Rust API/backend runtime.

use std::env;
use std::net::{IpAddr, SocketAddr};
use std::path::PathBuf;

use anyhow::{Context, Result};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LogFormat {
    Json,
    Text,
}

#[derive(Debug, Clone)]
pub struct ServerSettings {
    pub host: IpAddr,
    pub port: u16,
}

impl ServerSettings {
    pub fn bind_address(&self) -> SocketAddr {
        SocketAddr::from((self.host, self.port))
    }
}

#[derive(Debug, Clone)]
pub struct DatabaseSettings {
    pub url: String,
}

#[derive(Debug, Clone)]
pub struct MethodologySettings {
    pub factor_count: i32,
    pub benchmark_total_score: f64,
    pub base_position_size: f64,
    pub beta_floor: f64,
    pub max_position_size: Option<f64>,
    pub default_calculation_version: String,
}

#[derive(Debug, Clone)]
pub struct Settings {
    pub app_name: String,
    pub environment: String,
    pub debug: bool,
    pub log_level: String,
    pub log_format: LogFormat,
    pub data_dir: PathBuf,
    pub output_dir: PathBuf,
    pub server: ServerSettings,
    pub database: DatabaseSettings,
    pub methodology: MethodologySettings,
}

impl Settings {
    pub fn from_env() -> Result<Self> {
        let _ = dotenvy::dotenv();

        let app_name = env_string("APP_NAME", "ratio-api");
        let environment = env_string("APP_ENV", "development");
        let debug = env_bool("DEBUG", false);
        let log_level = env_string("LOG_LEVEL", "info");
        let log_format = match env_string("LOG_FORMAT", "json").to_lowercase().as_str() {
            "text" => LogFormat::Text,
            _ => LogFormat::Json,
        };

        let root_dir =
            env::current_dir().context("failed to determine current working directory")?;
        let data_dir = PathBuf::from(env_string(
            "RATIO_DATA_DIR",
            root_dir.join("data").to_string_lossy().as_ref(),
        ));
        let output_dir = PathBuf::from(env_string(
            "RATIO_OUTPUT_DIR",
            root_dir.join("output").to_string_lossy().as_ref(),
        ));

        let database_url = env_string(
            "DATABASE_URL",
            &format!("sqlite://{}", data_dir.join("ratio.db").to_string_lossy()),
        );

        let host = env_string("BACKEND_HOST", "127.0.0.1")
            .parse()
            .context("BACKEND_HOST must be a valid IP address")?;
        let port = env_string("BACKEND_PORT", "3000")
            .parse()
            .context("BACKEND_PORT must be a valid u16")?;

        Ok(Self {
            app_name,
            environment,
            debug,
            log_level,
            log_format,
            data_dir,
            output_dir,
            server: ServerSettings { host, port },
            database: DatabaseSettings { url: database_url },
            methodology: MethodologySettings {
                factor_count: env_string("FACTOR_COUNT", "4")
                    .parse()
                    .context("FACTOR_COUNT must be an integer")?,
                benchmark_total_score: env_string("BENCHMARK_TOTAL_SCORE", "20")
                    .parse()
                    .context("BENCHMARK_TOTAL_SCORE must be numeric")?,
                base_position_size: env_string("BASE_POSITION_SIZE", "0.05")
                    .parse()
                    .context("BASE_POSITION_SIZE must be numeric")?,
                beta_floor: env_string("BETA_FLOOR", "0.25")
                    .parse()
                    .context("BETA_FLOOR must be numeric")?,
                max_position_size: env_optional("MAX_POSITION_SIZE")
                    .map(|value| value.parse().context("MAX_POSITION_SIZE must be numeric"))
                    .transpose()?,
                default_calculation_version: env_string("DEFAULT_CALCULATION_VERSION", "beta-v1"),
            },
        })
    }
}

fn env_string(name: &str, default: &str) -> String {
    env::var(name).unwrap_or_else(|_| default.to_string())
}

fn env_optional(name: &str) -> Option<String> {
    env::var(name).ok().filter(|value| !value.trim().is_empty())
}

fn env_bool(name: &str, default: bool) -> bool {
    env_optional(name)
        .map(|value| matches!(value.to_lowercase().as_str(), "1" | "true" | "yes" | "on"))
        .unwrap_or(default)
}
