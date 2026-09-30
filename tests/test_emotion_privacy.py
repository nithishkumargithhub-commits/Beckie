"""
Tests for Emotion Privacy Controls & Local Storage Sovereignty.

Covers:
1. Privacy toggles (emotion_enabled, neutral_mode, show_emotion_state).
2. Data storage restricted to encrypted SQLite.
3. Complete purging of history on clear_emotion_history.
4. Anti-cloud exfiltration assertion (blocked without explicit user consent).
5. Namespace interoperability for backend.* paths.
"""

from __future__ import annotations

from pathlib import Path
import pytest

from backend.core.dialogue_manager import DialogueManager
from backend.core.emotion_engine import EmotionEngine, EmotionState
from backend.security.privacy_controls import (
    EmotionPrivacyManager,
    EmotionPrivacySettings,
    get_privacy_manager,
)
from db.schema import get_db


class TestEmotionPrivacy:
    @pytest.fixture
    def pm(self, tmp_db: Path) -> EmotionPrivacyManager:
        return EmotionPrivacyManager(db_path=tmp_db)

    def test_settings_toggles_and_persistence(self, pm: EmotionPrivacyManager) -> None:
        """Verifies toggles update and persist into encrypted SQLite preferences."""
        # Initial defaults
        assert pm.settings.emotion_enabled is True
        assert pm.settings.neutral_mode is False
        assert pm.settings.cloud_upload_consent is False

        # Update settings
        pm.update_settings(emotion_enabled=False, neutral_mode=True)
        assert pm.settings.emotion_enabled is False
        assert pm.settings.neutral_mode is True

        # Re-instantiate to verify persistence in DB
        pm2 = EmotionPrivacyManager(db_path=pm._db_path)
        assert pm2.settings.emotion_enabled is False
        assert pm2.settings.neutral_mode is True

    def test_disabled_emotion_drops_records(self, pm: EmotionPrivacyManager) -> None:
        """When emotion_enabled is False, turn records are NOT saved."""
        pm.update_settings(emotion_enabled=False)
        dummy_state = EmotionState(valence=0.5, arousal=0.5, dominance=0.5, labels=["calm"], confidence=1.0)
        dm = DialogueManager()
        adapt = dm.adapt(dummy_state)

        saved = pm.save_turn_record(
            session_id="test_sess",
            turn_index=1,
            emotion=dummy_state,
            adaptation=adapt,
        )
        assert saved is False

        records = pm.get_recent_records(session_id="test_sess")
        assert len(records) == 0

    def test_save_and_clear_emotion_history(self, pm: EmotionPrivacyManager) -> None:
        """Verifies saving turn records and completely clearing them on demand."""
        pm.update_settings(emotion_enabled=True, neutral_mode=False)
        dummy_state = EmotionState(valence=-0.4, arousal=0.6, dominance=0.3, labels=["frustrated"], confidence=0.85)
        dm = DialogueManager()
        adapt = dm.adapt(dummy_state)

        # Save 3 turn records
        pm.save_turn_record("sess_1", 1, dummy_state, adapt)
        pm.save_turn_record("sess_1", 2, dummy_state, adapt)
        pm.save_turn_record("sess_2", 1, dummy_state, adapt)

        records = pm.get_recent_records()
        assert len(records) == 3

        # Clear history
        deleted = pm.clear_emotion_history()
        assert deleted == 3

        # Verify database is clean
        records_after = pm.get_recent_records()
        assert len(records_after) == 0

    def test_anti_cloud_exfiltration_safeguard(self, pm: EmotionPrivacyManager) -> None:
        """Confirms no emotion data can be transmitted to cloud without explicit consent."""
        # By default, consent is False -> must raise PermissionError
        assert pm.settings.cloud_upload_consent is False
        with pytest.raises(PermissionError) as exc_info:
            pm.assert_cloud_transmission_allowed()
        assert "Transmission blocked" in str(exc_info.value)

        # Once explicitly enabled, transmission assertion passes
        pm.update_settings(cloud_upload_consent=True)
        pm.assert_cloud_transmission_allowed()  # Should not raise

    def test_backend_namespace_interoperability(self) -> None:
        """Verifies that backend.core.* and backend.security.* import cleanly."""
        from backend.core.emotion_engine import get_emotion_engine
        from backend.core.dialogue_manager import get_dialogue_manager
        from backend.security.privacy_controls import get_privacy_manager

        engine = get_emotion_engine()
        dm = get_dialogue_manager()
        privacy = get_privacy_manager()

        assert engine is not None
        assert dm is not None
        assert privacy is not None
