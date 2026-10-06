//! The few preferences the desktop app remembers between runs.
//!
//! Kept in a small JSON file beside the database rather than in it: they
//! belong to this machine's window, not to the library, and a library
//! restored from a backup should not bring someone else's theme with it.

use serde::{Deserialize, Serialize};
use std::path::PathBuf;

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct Settings {
    /// `None` follows the system.
    #[serde(default)]
    pub dark: Option<bool>,
}

fn path() -> PathBuf {
    crate::sidecar::data_dir().join("desktop-settings.json")
}

/// The saved settings, or the defaults if there are none or they are unreadable.
pub fn load() -> Settings {
    std::fs::read_to_string(path())
        .ok()
        .and_then(|contents| serde_json::from_str(&contents).ok())
        .unwrap_or_default()
}

/// Best effort: a preference that fails to save is not worth an error.
pub fn save(settings: &Settings) {
    if let Ok(contents) = serde_json::to_string_pretty(settings) {
        let _ = std::fs::create_dir_all(crate::sidecar::data_dir());
        let _ = std::fs::write(path(), contents);
    }
}
