//! Tauri Commands for Local Avatar Management

use crate::avatar::{
    asset_import::{discover_assets, DiscoveredAsset},
    asset_validation::{validate_asset_path, ValidationResult},
    audit_events::log_avatar_audit_event,
    blender_conversion::{
        convert_fbx_to_glb, detect_blender, get_conversion_preview, BlenderDetectionResult,
        ConversionPreview, ConversionReport,
    },
    local_file_picker::{handle_picked_path, PickedAssetResult},
};

#[tauri::command]
pub async fn discover_avatar_assets() -> Result<Vec<DiscoveredAsset>, String> {
    Ok(discover_assets())
}

#[tauri::command]
pub async fn validate_avatar_asset(path: String) -> Result<ValidationResult, String> {
    Ok(validate_asset_path(&path))
}

#[tauri::command]
pub async fn pick_local_avatar_file(path: String) -> Result<PickedAssetResult, String> {
    Ok(handle_picked_path(&path))
}

#[tauri::command]
pub async fn detect_blender_command() -> Result<BlenderDetectionResult, String> {
    Ok(detect_blender())
}

#[tauri::command]
pub async fn get_fbx_conversion_preview(source_path: String) -> Result<ConversionPreview, String> {
    get_conversion_preview(&source_path)
}

#[tauri::command]
pub async fn convert_fbx_to_glb_command(source_path: String) -> Result<ConversionReport, String> {
    convert_fbx_to_glb(&source_path)
}

#[tauri::command]
pub async fn log_avatar_audit(
    action: String,
    details: serde_json::Value,
    user_approved: bool,
) -> Result<(), String> {
    log_avatar_audit_event(&action, details, user_approved)
}
