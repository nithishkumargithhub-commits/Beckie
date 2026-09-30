//! Avatar Local Asset Discovery and Safe Import
//!
//! Restricts searches to approved local folders only.
//! Never executes arbitrary scripts alongside models.
//! Preserves original files unchanged.

use super::asset_validation::{validate_asset_path, ValidationResult};
use std::path::{Path, PathBuf};

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct DiscoveredAsset {
    pub file_name: String,
    pub relative_path: String,
    pub full_path: String,
    pub format: String,
    pub size_mb: f64,
    pub is_runtime_ready: bool,
    pub is_large: bool,
    pub folder_label: String,
}

pub fn get_project_root() -> PathBuf {
    std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."))
}

pub fn get_approved_directories() -> Vec<PathBuf> {
    let root = get_project_root();
    vec![
        root.join("assets").join("avatars").join("beckie").join("source"),
        root.join("assets").join("avatars").join("beckie").join("generated"),
        root.join("corrupted-archangel-six-wings-boss"),
        root.join("jarvis-main-folder"),
    ]
}

pub fn discover_assets() -> Vec<DiscoveredAsset> {
    let mut results = Vec::new();
    let root = get_project_root();

    for dir in get_approved_directories() {
        if !dir.exists() {
            continue;
        }

        let folder_label = dir.file_name()
            .and_then(|n| n.to_str())
            .unwrap_or("source")
            .to_string();

        scan_directory_recursive(&dir, &root, &folder_label, &mut results);
    }

    // Sort with runtime ready (.glb / .gltf) first
    results.sort_by(|a, b| {
        b.is_runtime_ready.cmp(&a.is_runtime_ready)
            .then_with(|| a.file_name.cmp(&b.file_name))
    });

    results
}

fn scan_directory_recursive(
    dir: &Path,
    root: &Path,
    folder_label: &str,
    results: &mut Vec<DiscoveredAsset>,
) {
    if let Ok(entries) = std::fs::read_dir(dir) {
        for entry in entries.flatten() {
            let path = entry.path();
            if path.is_dir() {
                scan_directory_recursive(&path, root, folder_label, results);
            } else if path.is_file() {
                let path_str = path.to_string_lossy().to_string();
                let val = validate_asset_path(&path_str);
                if val.is_valid {
                    let file_name = path.file_name()
                        .and_then(|n| n.to_str())
                        .unwrap_or("")
                        .to_string();

                    let relative_path = path.strip_prefix(root)
                        .map(|p| p.to_string_lossy().to_string().replace('\\', "/"))
                        .unwrap_or_else(|_| path_str.clone());

                    results.push(DiscoveredAsset {
                        file_name,
                        relative_path,
                        full_path: path_str.replace('\\', "/"),
                        format: val.format,
                        size_mb: val.size_mb,
                        is_runtime_ready: val.is_runtime_ready,
                        is_large: val.is_large,
                        folder_label: folder_label.to_string(),
                    });
                }
            }
        }
    }
}
