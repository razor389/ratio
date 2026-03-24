//! Centralized backend configuration and logging bootstrap.

pub mod logging;
pub mod settings;

pub use logging::init_logging;
pub use settings::{DatabaseSettings, LogFormat, MethodologySettings, ServerSettings, Settings};
