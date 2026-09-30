//! Local File Picker and Path Resolver for Avatars

use super::asset_validation::{validate_asset_path, ValidationResult};
use std::path::PathBuf;

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct PickedAssetResult {
    pub success: bool,
    pub validation: Option<ValidationResult>,
    pub error: Option<String>,
}

pub fn handle_picked_path(selected_path: &str) -> PickedAssetResult {
    let validation = validate_asset_path(selected_path);
    if !validation.is_valid {
        return PickedAssetResult {
            success: false,
            validation: Some(validation.clone()),
            error: validation.error,
        };
    }

    PickedAssetResult {
        success: true,
        validation: Some(validation),
        error: None,
    }
}
