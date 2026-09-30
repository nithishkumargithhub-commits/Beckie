"""Avatar Local State & Permissions Manager.

Persists avatar configuration, user consent flags, and quality settings.
Adheres strictly to local-first rules:
- Flying, weapon posing, procedural wing movement are OFF by default until explicit user approval.
- Ambient random motion is OFF by default.
- Permissions do not auto-persist unless 'rememberChoice' is explicitly enabled.
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from .avatar_audit import get_audit_logger

logger = logging.getLogger("Avatar.State")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATE_PATH = os.path.join(BASE_DIR, "assets", "avatars", "beckie", "generated", "avatar-state.json")

DEFAULT_PERMISSIONS = {
    "enabled": True,
    "ambientMovement": False,
    "proceduralHover": False,
    "flightBehavior": False,
    "weaponPose": False,
    "reducedMotion": False,
    "suspendUnderLoad": True,
    "quality": "Balanced",  # Low, Balanced, High
    "volume": 0.8,
    "rememberChoice": False,
}


class AvatarStateManager:
    """Manages active avatar selection and revocable user permissions."""

    def __init__(self, state_path: str = STATE_PATH):
        self.state_path = state_path
        os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
        self._state: Dict[str, Any] = self._load()

    def _load(self) -> Dict[str, Any]:
        """Load avatar state from disk or initialize with safe defaults."""
        if os.path.exists(self.state_path):
            try:
                with open(self.state_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # If user chose not to remember permissions across restart, reset sensitive toggles
                    if not data.get("rememberChoice", False):
                        data["ambientMovement"] = False
                        data["proceduralHover"] = False
                        data["flightBehavior"] = False
                        data["weaponPose"] = False
                    return data
            except Exception as e:
                logger.warning(f"[AvatarState] Could not load state from disk: {e}")

        initial = {
            "activeAssetId": None,
            "activeManifestPath": None,
            "runtimeFilePath": None,
            **DEFAULT_PERMISSIONS,
        }
        self._save(initial)
        return initial

    def _save(self, state: Dict[str, Any]) -> None:
        try:
            with open(self.state_path, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"[AvatarState] Failed to save state: {e}")

    def get_state(self) -> Dict[str, Any]:
        return dict(self._state)

    def update_permissions(self, updates: Dict[str, Any], user_approved: bool = True) -> Dict[str, Any]:
        """Update user permissions and write audit log entry."""
        audit = get_audit_logger()
        previous = dict(self._state)

        for key, val in updates.items():
            if key in DEFAULT_PERMISSIONS or key in ["activeAssetId", "activeManifestPath", "runtimeFilePath"]:
                self._state[key] = val

        self._save(self._state)

        # Audit permission changes
        changed_keys = {k: self._state[k] for k in updates if previous.get(k) != self._state.get(k)}
        if changed_keys:
            audit.log(
                action="PERMISSION_CHANGED",
                asset_id=self._state.get("activeAssetId"),
                source_file=self._state.get("runtimeFilePath"),
                details={"changedPermissions": changed_keys},
                user_approved=user_approved,
            )

        return dict(self._state)

    def set_active_asset(self, asset_id: str, manifest_path: str, runtime_path: str) -> Dict[str, Any]:
        """Activate an analyzed asset for runtime rendering."""
        self._state["activeAssetId"] = asset_id
        self._state["activeManifestPath"] = manifest_path
        self._state["runtimeFilePath"] = runtime_path
        self._save(self._state)

        get_audit_logger().log(
            action="ASSET_ACTIVATED",
            asset_id=asset_id,
            source_file=runtime_path,
            details={"manifestPath": manifest_path},
            user_approved=True,
        )
        return dict(self._state)

    def reset_asset(self) -> Dict[str, Any]:
        """Reset avatar active asset."""
        old_id = self._state.get("activeAssetId")
        old_file = self._state.get("runtimeFilePath")
        self._state["activeAssetId"] = None
        self._state["activeManifestPath"] = None
        self._state["runtimeFilePath"] = None
        self._save(self._state)

        get_audit_logger().log(
            action="ASSET_DEACTIVATED",
            asset_id=old_id,
            source_file=old_file,
            user_approved=True,
        )
        return dict(self._state)


_singleton_state_manager: Optional[AvatarStateManager] = None


def get_avatar_state_manager() -> AvatarStateManager:
    global _singleton_state_manager
    if _singleton_state_manager is None:
        _singleton_state_manager = AvatarStateManager()
    return _singleton_state_manager
