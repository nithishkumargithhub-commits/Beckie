"""
test_avatar_pipeline.py - Comprehensive Unit Tests for BECKIE Local 3D Avatar System

Tests:
1. Safe local asset discovery (only approved directories, path traversal prevention)
2. Rigorous GLTF/GLB binary parser and truthful capability detection
3. Non-deceptive rigging and feature enforcement (unrigged static mesh rules)
4. State persistence, revocable user permissions, and append-only audit log
5. Blender headless conversion status, preview, and report endpoints
6. FastAPI avatar REST API endpoints and asset streaming security
7. Strict Section 4 Manifest Schema compliance
"""

import os
import json
import pytest
from fastapi.testclient import TestClient
from server import app
from backend.avatar.avatar_discovery import AvatarDiscoveryService, get_avatar_discovery
from backend.avatar.avatar_analyzer import AvatarAssetAnalyzer
from backend.avatar.avatar_state import AvatarStateManager
from backend.avatar.avatar_audit import AvatarAuditLogger, get_audit_logger
from backend.avatar.blender_converter import BlenderConverterService

client = TestClient(app)


def test_asset_discovery_safe_paths():
    """Verify scanner finds local assets and rejects malicious paths."""
    discovery = get_avatar_discovery()
    assets = discovery.discover_local_assets()
    assert len(assets) > 0

    # Ensure MidPoly.fbx or beckie-avatar.glb asset is detected
    found = any("MidPoly" in a["fileName"] or "beckie-avatar" in a["fileName"] for a in assets)
    assert found is True

    # Security: Verify path traversal is strictly rejected
    is_valid, err = discovery.validate_path_safety("../../windows/system32/cmd.exe")
    assert is_valid is False
    assert "Path traversal" in err or "Unsupported" in err

    # Security: Remote URLs strictly rejected
    is_valid_remote, err_remote = discovery.validate_path_safety("https://sketchfab.com/models/test.glb")
    assert is_valid_remote is False
    assert "Remote URLs" in err_remote


def test_avatar_analyzer_runtime_asset():
    """Verify truthful capability analysis of local runtime GLB."""
    discovery = get_avatar_discovery()
    target_rel = "assets/avatars/beckie/generated/beckie-avatar.glb"
    target_abs = os.path.join(discovery.base_dir, os.path.normpath(target_rel))

    assert os.path.exists(target_abs), f"Test asset missing: {target_abs}"

    analyzer = AvatarAssetAnalyzer()
    manifest = analyzer.analyze_glb_file(target_abs, target_rel)

    # Validate truthful metrics
    assert manifest["format"].lower() == "glb"
    assert manifest["meshCount"] > 0
    assert manifest["triangleCount"] > 0
    assert manifest["hasSkeleton"] is False
    assert len(manifest["boneNames"]) == 0
    assert len(manifest["animationClips"]) == 0

    # Validate feature detection
    features = manifest["detectedFeatures"]
    assert "humanoidRigConfidence" in features
    assert "hasHeadBone" in features
    assert "hasWings" in features
    assert "hasWeaponLikeMesh" in features

    # Validate capabilities: non-deceptive constraints
    caps = manifest["detectedCapabilities"]
    assert caps["canIdle"] is True
    assert caps["canWalk"] is False  # Cannot walk (unrigged or no walk clip)
    assert caps["canFly"] is False   # Cannot fly (no wing bones + fly clip)
    assert caps["canHover"] is True  # Ambient procedural hover allowed
    assert caps["canTalk"] is False  # No facial blendshapes

    assert manifest["recommendedMode"] in ["static_ambient", "rigged_idle", "rigged_interactive"]


def test_avatar_blender_endpoints():
    """Verify Blender detection, conversion preview, and conversion report endpoints."""
    # 1. Blender status endpoint
    res_status = client.get("/api/avatar/blender-status")
    assert res_status.status_code == 200
    st_data = res_status.json()
    assert "isAvailable" in st_data
    assert "instructions" in st_data
    assert "Blender is required to convert MidPoly.fbx to GLB." in st_data["instructions"]

    # 2. Conversion preview endpoint
    res_prev = client.post("/api/avatar/convert-preview", json={"sourcePath": "assets/avatars/beckie/source/MidPoly.fbx"})
    assert res_prev.status_code == 200
    prev_data = res_prev.json()
    assert prev_data["status"] == "success"
    assert "preview" in prev_data
    assert prev_data["preview"]["sourceFile"] == "assets/avatars/beckie/source/MidPoly.fbx"
    assert prev_data["preview"]["isBinaryFbx"] is True

    # 3. Conversion report endpoint
    res_rep = client.get("/api/avatar/conversion-report")
    assert res_rep.status_code == 200
    rep_data = res_rep.json()
    assert "report" in rep_data
    if rep_data["report"]:
        assert "sourceFile" in rep_data["report"]
        assert "outputFile" in rep_data["report"]


def test_avatar_audit_and_state():
    """Verify append-only audit logger and state persistence."""
    logger = get_audit_logger()
    initial_count = len(logger.get_recent_entries(100))

    logger.log("test_audit_action", {"test_key": "val123"}, user_approved=True)
    updated_entries = logger.get_recent_entries(100)
    assert len(updated_entries) == initial_count + 1
    assert updated_entries[0]["action"].upper() == "TEST_AUDIT_ACTION"
    assert updated_entries[0]["userApproved"] is True

    # State manager
    sm = AvatarStateManager()
    state = sm.get_state()
    assert "enabled" in state
    assert "quality" in state

    # Test permissions update
    new_perms = {"ambientMovement": True, "proceduralHover": True}
    res = sm.update_permissions(new_perms, user_approved=True)
    assert res["ambientMovement"] is True
    assert res["proceduralHover"] is True

    # Revert to default
    sm.update_permissions({"ambientMovement": False, "proceduralHover": False}, user_approved=True)


def test_api_avatar_endpoints():
    """Verify FastAPI avatar endpoints."""
    # 1. Discover
    res = client.get("/api/avatar/discover")
    assert res.status_code == 200
    data = res.json()
    assert "assets" in data
    assert len(data["assets"]) > 0

    # 2. Validate
    res_val = client.post("/api/avatar/validate", json={"path": "assets/avatars/beckie/generated/beckie-avatar.glb"})
    assert res_val.status_code == 200
    val_data = res_val.json()
    assert val_data["isValid"] is True

    # 3. Path traversal blocked on API
    res_bad = client.post("/api/avatar/validate", json={"path": "../../etc/passwd"})
    assert res_bad.status_code == 200
    assert res_bad.json()["isValid"] is False

    # 4. Manifest
    res_man = client.get("/api/avatar/manifest")
    assert res_man.status_code == 200
    m = res_man.json().get("manifest")
    assert m is not None
    assert m["recommendedMode"] in ["static_ambient", "rigged_idle", "rigged_interactive"]

    # 5. State & Permissions
    res_st = client.get("/api/avatar/state")
    assert res_st.status_code == 200

    # 6. Audit
    res_aud = client.get("/api/avatar/audit?limit=5")
    assert res_aud.status_code == 200
    assert "entries" in res_aud.json()

    # 7. Asset Streaming Security
    # Traversal should fail with 400 or 403
    res_stream_bad = client.get("/api/avatar/asset-file?path=../../windows/win.ini")
    assert res_stream_bad.status_code in [400, 403]

    # Approved asset path succeeds
    res_stream_ok = client.get("/api/avatar/asset-file?path=assets/avatars/beckie/generated/beckie-avatar.glb", headers={"Range": "bytes=0-100"})
    assert res_stream_ok.status_code in [200, 206]


def test_manifest_schema_compliance():
    """Verify Section 4 schema compliance on beckie-avatar-manifest.json."""
    manifest_path = os.path.join(os.path.dirname(__file__), "..", "assets", "avatars", "beckie", "manifests", "beckie-avatar-manifest.json")
    assert os.path.exists(manifest_path)

    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Core required fields
    required_keys = [
        "assetId", "displayName", "sourceFile", "runtimeFile", "format",
        "analyzedAt", "fileSizeBytes", "meshCount", "triangleCount",
        "materialCount", "textureCount", "hasSkeleton", "boneNames",
        "animationClips", "detectedFeatures", "detectedCapabilities",
        "recommendedMode", "warnings"
    ]
    for key in required_keys:
        assert key in data, f"Missing required Section 4 key: {key}"

    # Detected features required fields
    feat = data["detectedFeatures"]
    assert "humanoidRigConfidence" in feat
    assert "hasHeadBone" in feat
    assert "hasNeckBone" in feat
    assert "hasJawBone" in feat
    assert "hasHandBones" in feat
    assert "hasLegBones" in feat
    assert "hasWings" in feat
    assert "wingBoneNames" in feat
    assert "hasWeaponLikeMesh" in feat
    assert "weaponMeshNames" in feat
    assert "hasMouthBlendshapes" in feat
    assert "morphTargetNames" in feat

    # Detected capabilities required fields
    caps = data["detectedCapabilities"]
    assert "canRender" in caps
    assert "canIdle" in caps
    assert "canWalk" in caps
    assert "canHover" in caps
    assert "canFly" in caps
    assert "canTalk" in caps
    assert "canGesture" in caps
    assert "canUseSafeWeaponPose" in caps
