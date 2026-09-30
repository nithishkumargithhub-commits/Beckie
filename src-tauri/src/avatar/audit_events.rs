//! audit_events.rs – Local Audit Logging for Avatar Actions
//!
//! Writes append-only audit events to logs/avatar_audit.jsonl.
//! All operations are strictly local. Zero telemetry or network transmission.

use chrono::Utc;
use serde::{Deserialize, Serialize};
use std::fs::{create_dir_all, OpenOptions};
use std::io::Write;
use std::path::PathBuf;

#[derive(Debug, Serialize, Deserialize)]
pub struct AvatarAuditEvent {
    pub timestamp: String,
    pub action: String,
    pub details: serde_json::Value,
    #[serde(rename = "userApproved")]
    pub user_approved: bool,
}

pub fn log_avatar_audit_event(
    action: &str,
    details: serde_json::Value,
    user_approved: bool,
) -> Result<(), String> {
    let log_dir = PathBuf::from("logs");
    create_dir_all(&log_dir).map_err(|e| format!("Failed to create logs directory: {}", e))?;

    let log_path = log_dir.join("avatar_audit.jsonl");

    let event = AvatarAuditEvent {
        timestamp: Utc::now().to_rfc3339(),
        action: action.to_uppercase(),
        details,
        user_approved,
    };

    let serialized = serde_json::to_string(&event)
        .map_err(|e| format!("Failed to serialize audit event: {}", e))?;

    let mut file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(&log_path)
        .map_err(|e| format!("Failed to open avatar audit log: {}", e))?;

    writeln!(file, "{}", serialized)
        .map_err(|e| format!("Failed to write to avatar audit log: {}", e))?;

    Ok(())
}
