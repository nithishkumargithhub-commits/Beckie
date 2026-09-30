"""
JARVIS – Emotion Privacy Controls & Local Storage Manager.

Manages user privacy toggles:
  - emotion_enabled: Enables or disables all emotion inference and tracking.
  - neutral_mode: Forces assistant behavior and emotion state to neutral baseline.
  - show_emotion_state: Controls UI visibility of emotion metrics.
  - clear_emotion_history: Completely purges emotion records from encrypted SQLite.

Security & Sovereignty Invariant:
  - All emotion records live strictly in local encrypted SQLite (SQLCipher).
  - No emotion data is ever transmitted to cloud services without explicit, recorded consent.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("Jarvis.Security.PrivacyControls")


@dataclass
class EmotionPrivacySettings:
    """User preferences for emotion understanding and privacy."""
    emotion_enabled: bool = True
    neutral_mode: bool = False
    show_emotion_state: bool = True
    cloud_upload_consent: bool = False

    def to_dict(self) -> Dict[str, bool]:
        return {
            "emotion_enabled": self.emotion_enabled,
            "neutral_mode": self.neutral_mode,
            "show_emotion_state": self.show_emotion_state,
            "cloud_upload_consent": self.cloud_upload_consent,
        }


class EmotionPrivacyManager:
    """
    Enforces local-only encryption, preference management, and complete data purge.
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        from db.schema import DB_PATH
        self._db_path = db_path or DB_PATH
        self._settings = self._load_settings()

    @property
    def settings(self) -> EmotionPrivacySettings:
        return self._settings

    # ------------------------------------------------------------------
    # Settings Management (Encrypted Preferences Table)
    # ------------------------------------------------------------------

    def _load_settings(self) -> EmotionPrivacySettings:
        """Loads preferences from the encrypted database."""
        from db.schema import get_db
        try:
            with get_db(self._db_path) as conn:
                rows = conn.execute(
                    "SELECT key, value FROM preferences WHERE namespace = 'emotion'"
                ).fetchall()
                if not rows:
                    return EmotionPrivacySettings()

                data = {r["key"]: json.loads(r["value"]) for r in rows}
                return EmotionPrivacySettings(
                    emotion_enabled=data.get("emotion_enabled", True),
                    neutral_mode=data.get("neutral_mode", False),
                    show_emotion_state=data.get("show_emotion_state", True),
                    cloud_upload_consent=data.get("cloud_upload_consent", False),
                )
        except Exception as exc:
            logger.debug("Preferences table not yet initialised; using defaults (%s)", exc)
            return EmotionPrivacySettings()

    def update_settings(
        self,
        emotion_enabled: Optional[bool] = None,
        neutral_mode: Optional[bool] = None,
        show_emotion_state: Optional[bool] = None,
        cloud_upload_consent: Optional[bool] = None,
    ) -> EmotionPrivacySettings:
        """Updates and persists emotion privacy preferences."""
        if emotion_enabled is not None:
            self._settings.emotion_enabled = emotion_enabled
        if neutral_mode is not None:
            self._settings.neutral_mode = neutral_mode
        if show_emotion_state is not None:
            self._settings.show_emotion_state = show_emotion_state
        if cloud_upload_consent is not None:
            self._settings.cloud_upload_consent = cloud_upload_consent

        from db.schema import get_db
        try:
            with get_db(self._db_path) as conn:
                for k, v in self._settings.to_dict().items():
                    conn.execute(
                        """
                        INSERT INTO preferences (namespace, key, value, is_secret)
                        VALUES ('emotion', ?, ?, 0)
                        ON CONFLICT(namespace, key) DO UPDATE SET value = excluded.value
                        """,
                        (k, json.dumps(v)),
                    )
            logger.info("Emotion privacy settings updated: %s", self._settings)
        except Exception as exc:
            logger.error("Failed to persist emotion privacy settings: %s", exc)

        # Sync with singletons
        try:
            from core.emotion_engine import get_emotion_engine
            from core.dialogue_manager import get_dialogue_manager
            engine = get_emotion_engine()
            engine.neutral_mode = self._settings.neutral_mode or not self._settings.emotion_enabled
            dm = get_dialogue_manager()
            dm.neutral_mode = self._settings.neutral_mode or not self._settings.emotion_enabled
        except Exception:
            pass

        return self._settings

    # ------------------------------------------------------------------
    # Data Storage in Encrypted SQLite
    # ------------------------------------------------------------------

    def save_turn_record(
        self,
        session_id: str,
        turn_index: int,
        emotion: Any,
        adaptation: Any,
    ) -> bool:
        """
        Stores emotion inference strictly in encrypted SQLite.
        If emotion_enabled is False, drops the record immediately.
        """
        if not self._settings.emotion_enabled:
            return False

        from db.schema import get_db
        try:
            with get_db(self._db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO emotion_records
                        (session_id, turn_index, valence, arousal, dominance,
                         labels_json, confidence, tone_style, challenge_level,
                         step_size, is_neutral_mode, cloud_consent)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session_id,
                        turn_index,
                        emotion.valence,
                        emotion.arousal,
                        emotion.dominance,
                        json.dumps(emotion.labels),
                        emotion.confidence,
                        adaptation.tone_style,
                        adaptation.challenge_level,
                        adaptation.step_size,
                        1 if (self._settings.neutral_mode or emotion.is_neutral_mode) else 0,
                        1 if self._settings.cloud_upload_consent else 0,
                    ),
                )
            return True
        except Exception as exc:
            logger.error("Failed to save emotion record to encrypted DB: %s", exc)
            return False

    def get_recent_records(self, session_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Queries recent emotion inferences from encrypted SQLite."""
        from db.schema import get_db
        try:
            with get_db(self._db_path) as conn:
                if session_id:
                    rows = conn.execute(
                        """
                        SELECT * FROM emotion_records
                        WHERE session_id = ?
                        ORDER BY timestamp DESC LIMIT ?
                        """,
                        (session_id, limit),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT * FROM emotion_records ORDER BY timestamp DESC LIMIT ?",
                        (limit,),
                    ).fetchall()
                return [dict(r) for r in rows]
        except Exception as exc:
            logger.error("Failed to query emotion records: %s", exc)
            return []

    def clear_emotion_history(self, session_id: Optional[str] = None) -> int:
        """
        Permanently purges emotion history from memory and the encrypted database.
        Returns the number of deleted records.
        """
        # 1. Clear memory history
        try:
            from core.emotion_engine import get_emotion_engine
            get_emotion_engine().clear_history()
        except Exception:
            pass

        # 2. Clear encrypted DB records
        from db.schema import get_db
        deleted_count = 0
        try:
            with get_db(self._db_path) as conn:
                if session_id:
                    cur = conn.execute("DELETE FROM emotion_records WHERE session_id = ?", (session_id,))
                else:
                    cur = conn.execute("DELETE FROM emotion_records")
                deleted_count = cur.rowcount
            logger.info("Cleared %d emotion records from encrypted storage.", deleted_count)
        except Exception as exc:
            logger.error("Failed to clear emotion records from DB: %s", exc)

        # 3. Audit log the deletion
        try:
            from core.audit_logger import get_audit_logger
            get_audit_logger().log(
                action_type="privacy_control",
                action_name="clear_emotion_history",
                status="completed",
                tier="destructive",
                user_approved=True,
                actor="user",
                details={"deleted_count": deleted_count, "session_id": session_id},
            )
        except Exception:
            pass

        return deleted_count

    # ------------------------------------------------------------------
    # Data Exfiltration Protection (Requirement)
    # ------------------------------------------------------------------

    def assert_cloud_transmission_allowed(self) -> None:
        """
        Enforces that no emotion data can ever be transmitted to external/cloud services
        without explicit user consent. Raises PermissionError if unconsented.
        """
        if not self._settings.cloud_upload_consent:
            raise PermissionError(
                "Transmission blocked: Emotion telemetry upload is prohibited without explicit, recorded user consent."
            )


# Module-level instance
_default_privacy_manager: Optional[EmotionPrivacyManager] = None


def get_privacy_manager(db_path: Optional[Path] = None) -> EmotionPrivacyManager:
    global _default_privacy_manager
    if _default_privacy_manager is None or (db_path and db_path != _default_privacy_manager._db_path):
        _default_privacy_manager = EmotionPrivacyManager(db_path=db_path)
    return _default_privacy_manager
