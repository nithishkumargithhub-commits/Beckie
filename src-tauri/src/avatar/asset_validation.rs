//! Avatar Asset Security Validation
//!
//! Validates:
//! - Local filesystem path only
//! - No path traversal (../, ..\\)
//! - No remote protocols (http, https, ftp)
//! - Supported 3D formats (.glb, .gltf, .fbx, .obj, .blend)
//! - Warns on assets exceeding 250 MB

use std::path::{Path, PathBuf};

pub const MAX_SAFE_FILE_SIZE_BYTES: u64 = 250 * 1024 * 1024; // 250 MB
pub const SUPPORTED_EXTENSIONS: &[&str] = &["glb", "gltf", "fbx", "obj", "blend"];

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct ValidationResult {
    pub is_valid: bool,
    pub is_runtime_ready: bool,
    pub is_large: bool,
    pub format: String,
    pub size_bytes: u64,
    pub size_mb: f64,
    pub normalized_path: String,
    pub error: Option<String>,
    pub warning: Option<String>,
}

pub fn validate_asset_path(raw_path: &str) -> ValidationResult {
    let lower = raw_path.to_lowercase();

    // 1. Reject remote URLs
    if lower.starts_with("http://") || lower.starts_with("https://") || lower.starts_with("ftp://") {
        return ValidationResult {
            is_valid: false,
            is_runtime_ready: false,
            is_large: false,
            format: "".into(),
            size_bytes: 0,
            size_mb: 0.0,
            normalized_path: raw_path.into(),
            error: Some("Remote URLs are strictly prohibited. Local 3D assets only.".into()),
            warning: None,
        };
    }

    // 2. Reject path traversal
    if raw_path.contains("..") {
        return ValidationResult {
            is_valid: false,
            is_runtime_ready: false,
            is_large: false,
            format: "".into(),
            size_bytes: 0,
            size_mb: 0.0,
            normalized_path: raw_path.into(),
            error: Some("Path traversal sequence '..' detected and rejected.".into()),
            warning: None,
        };
    }

    let path = Path::new(raw_path);
    if !path.exists() {
        return ValidationResult {
            is_valid: false,
            is_runtime_ready: false,
            is_large: false,
            format: "".into(),
            size_bytes: 0,
            size_mb: 0.0,
            normalized_path: raw_path.into(),
            error: Some("Asset file does not exist on local disk.".into()),
            warning: None,
        };
    }

    // 3. Format validation
    let ext = match path.extension().and_then(|e| e.to_str()).map(|e| e.to_lowercase()) {
        Some(e) => e,
        None => {
            return ValidationResult {
                is_valid: false,
                is_runtime_ready: false,
                is_large: false,
                format: "".into(),
                size_bytes: 0,
                size_mb: 0.0,
                normalized_path: raw_path.into(),
                error: Some("File has no extension. Supported: glb, gltf, fbx, obj, blend".into()),
                warning: None,
            };
        }
    };

    if !SUPPORTED_EXTENSIONS.contains(&ext.as_str()) {
        return ValidationResult {
            is_valid: false,
            is_runtime_ready: false,
            is_large: false,
            format: ext.clone(),
            size_bytes: 0,
            size_mb: 0.0,
            normalized_path: raw_path.into(),
            error: Some(format!("Unsupported format '{}'. Supported: {}", ext, SUPPORTED_EXTENSIONS.join(", "))),
            warning: None,
        };
    }

    // 4. File size check
    let metadata = match std::fs::metadata(path) {
        Ok(m) => m,
        Err(e) => {
            return ValidationResult {
                is_valid: false,
                is_runtime_ready: false,
                is_large: false,
                format: ext,
                size_bytes: 0,
                size_mb: 0.0,
                normalized_path: raw_path.into(),
                error: Some(format!("Failed to read asset metadata: {}", e)),
                warning: None,
            };
        }
    };

    let size_bytes = metadata.len();
    let size_mb = (size_bytes as f64) / (1024.0 * 1024.0);
    let is_large = size_bytes > MAX_SAFE_FILE_SIZE_BYTES;
    let is_runtime_ready = ext == "glb" || ext == "gltf";

    let warning = if is_large {
        Some(format!("Asset is large ({:.1} MB). May impact VRAM and memory on high-resolution viewports.", size_mb))
    } else {
        None
    };

    ValidationResult {
        is_valid: true,
        is_runtime_ready,
        is_large,
        format: ext,
        size_bytes,
        size_mb: (size_mb * 10.0).round() / 10.0,
        normalized_path: path.to_string_lossy().to_string().replace('\\', "/"),
        error: None,
        warning,
    }
}
