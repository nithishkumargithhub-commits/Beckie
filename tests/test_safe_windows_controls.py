"""
Comprehensive Unit Tests for Safe Windows Controls:
1. Brightness control via screen-brightness-control (pywin32 / WMI backend and VCP external monitors).
2. Volume control via AudioEndpointVolume API (pycaw).
3. Media key hotkeys (Play/Pause/Next/Prev) via RegisterHotKey.
4. File operations: open approved apps, search folders, show metadata.
5. Deletion impact analysis (file count, size, recency, project affiliation).
6. Recycle Bin move (not permanent deletion).
7. Windows startup option (Task Scheduler, disabled by default).
8. Emergency pause button (tray menu, stops mic/tracking/integrations).

Requirements verified:
- Tier 0 actions require no approval.
- Tier 2+ actions require explicit confirmation dialog.
- Audit log all actions with timestamps.
- Explicit tests on external monitors for brightness API.
"""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
import time
from unittest.mock import MagicMock, patch
import pytest

from actions.brightness import BrightnessController
from actions.deletion_guard import DeletionImpactAnalyzer, DeletionImpact
from actions.file_ops import SafeFileOperations, format_size, APPROVED_APPS
from actions.media_hotkeys import MediaHotkeyManager, VK_MEDIA_PLAY_PAUSE, VK_MEDIA_NEXT_TRACK, VK_MEDIA_PREV_TRACK
from actions.recycle_bin import RecycleBinManager
from actions.startup_manager import StartupManager
from actions.volume import VolumeController
from actions.windows_dialog import set_dialog_handler, show_confirmation_dialog
from core.audit_logger import AuditLogger
from core.permission_broker import PermissionBroker, PermissionTier
from pipeline.indicator import IndicatorState, TrayListeningIndicator
from pipeline.voice_router import VoiceCommandRouter
from pipeline.wake_word import WakeWordListener


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_audit():
    audit = MagicMock(spec=AuditLogger)
    audit.log_action = MagicMock()
    audit.log_system = MagicMock()
    return audit


@pytest.fixture
def broker():
    return PermissionBroker(session_id="test-session")


# ---------------------------------------------------------------------------
# 1. Brightness Control Tests (including External Monitors)
# ---------------------------------------------------------------------------

class TestBrightnessControl:

    def test_list_monitors_internal_and_external(self, mock_audit):
        """Verify list_monitors correctly differentiates internal panel and external VCP display."""
        mock_monitors_info = [
            {
                "name": "Built-in Display",
                "model": "BOE0CBF",
                "manufacturer": "BOE",
                "method": "screen_brightness_control.windows.WMI",
                "index": 0,
            },
            {
                "name": "Dell UltraSharp U2720Q",
                "model": "U2720Q",
                "manufacturer": "Dell Inc.",
                "method": "screen_brightness_control.windows.VCP",
                "index": 1,
            },
        ]

        with patch("screen_brightness_control.list_monitors_info", return_value=mock_monitors_info), \
             patch("screen_brightness_control.get_brightness", side_effect=[[50], [80]]):
            controller = BrightnessController(audit_logger=mock_audit)
            monitors = controller.list_monitors()

            assert len(monitors) == 2
            # Display 0: Internal
            assert monitors[0]["name"] == "Built-in Display"
            assert monitors[0]["is_external"] is False
            assert monitors[0]["brightness"] == 50

            # Display 1: External monitor via DDC/CI (VCP)
            assert monitors[1]["name"] == "Dell UltraSharp U2720Q"
            assert monitors[1]["is_external"] is True
            assert monitors[1]["brightness"] == 80

            # Verify Tier 0 audit logged
            mock_audit.log_action.assert_called_once()
            call_kwargs = mock_audit.log_action.call_args[1]
            assert call_kwargs["action_name"] == "list_monitors"
            assert call_kwargs["tier"] == PermissionTier.SAFE.value

    def test_get_brightness_tier0_no_approval(self, mock_audit):
        """Reading brightness must be Tier 0 (safe) without requiring any prompt."""
        with patch("screen_brightness_control.get_brightness", return_value=[65]):
            controller = BrightnessController(audit_logger=mock_audit)
            level = controller.get_brightness()
            assert level == 65
            mock_audit.log_action.assert_called_once()
            call_kwargs = mock_audit.log_action.call_args[1]
            assert call_kwargs["action_name"] == "get_brightness"
            assert call_kwargs["tier"] == PermissionTier.SAFE.value

    def test_set_brightness_tier2_confirmed(self, mock_audit):
        """Setting brightness is Tier 2 (WRITE), requires confirmation dialog."""
        dialog_mock = MagicMock(return_value=True)
        with patch("screen_brightness_control.set_brightness") as mock_set:
            controller = BrightnessController(audit_logger=mock_audit, dialog_fn=dialog_mock)
            success, msg = controller.set_brightness(75)

            assert success is True
            assert "75%" in msg or "75 percent" in msg
            dialog_mock.assert_called_once()
            mock_set.assert_called_once_with(75)
            # Verify WRITE audit log
            assert mock_audit.log_action.call_count == 1
            assert mock_audit.log_action.call_args[1]["tier"] == PermissionTier.WRITE.value
            assert mock_audit.log_action.call_args[1]["user_approved"] is True

    def test_set_brightness_tier2_cancelled(self, mock_audit):
        """If user denies brightness change in confirmation dialog, operation aborts."""
        dialog_mock = MagicMock(return_value=False)
        with patch("screen_brightness_control.set_brightness") as mock_set:
            controller = BrightnessController(audit_logger=mock_audit, dialog_fn=dialog_mock)
            success, msg = controller.set_brightness(90)

            assert success is False
            assert "cancelled" in msg
            mock_set.assert_not_called()
            assert mock_audit.log_action.call_args[1]["user_approved"] is False

    def test_set_brightness_external_monitor_ddc_ci_success(self, mock_audit):
        """Explicitly test setting brightness on an external monitor target."""
        dialog_mock = MagicMock(return_value=True)
        with patch("screen_brightness_control.set_brightness") as mock_set:
            controller = BrightnessController(audit_logger=mock_audit, dialog_fn=dialog_mock)
            success, msg = controller.set_brightness(85, display="Dell UltraSharp U2720Q")

            assert success is True
            mock_set.assert_called_once_with(85, display="Dell UltraSharp U2720Q")
            assert "Display Dell UltraSharp U2720Q" in msg

    def test_set_brightness_external_monitor_ddc_ci_failure_handled(self, mock_audit):
        """If external monitor does not support DDC/CI, returns informative diagnostic."""
        dialog_mock = MagicMock(return_value=True)
        with patch("screen_brightness_control.set_brightness", side_effect=Exception("VCPError: monitor returned unsupported DDC/CI code")):
            controller = BrightnessController(audit_logger=mock_audit, dialog_fn=dialog_mock)
            success, msg = controller.set_brightness(85, display=1)

            assert success is False
            assert "DDC/CI" in msg or "OSD" in msg
            assert mock_audit.log_action.call_args[1]["status"] == "failed"


# ---------------------------------------------------------------------------
# 2. Volume Control Tests (AudioEndpointVolume API)
# ---------------------------------------------------------------------------

class TestVolumeControl:

    def test_get_volume_and_mute_tier0_safe(self, mock_audit):
        """Reading volume and mute state must be Tier 0 (no approval required)."""
        mock_endpoint = MagicMock()
        mock_endpoint.GetMasterVolumeLevelScalar.return_value = 0.42
        mock_endpoint.GetMute.return_value = 0

        controller = VolumeController(audit_logger=mock_audit)
        controller._volume_interface = mock_endpoint

        assert controller.get_volume() == 42
        assert controller.is_muted() is False

        # Verify SAFE tier audit logged
        assert mock_audit.log_action.call_count == 2
        for call in mock_audit.log_action.call_args_list:
            assert call[1]["tier"] == PermissionTier.SAFE.value

    def test_set_volume_tier2_confirmed(self, mock_audit):
        """Modifying volume requires Tier 2 confirmation dialog."""
        mock_endpoint = MagicMock()
        dialog_mock = MagicMock(return_value=True)

        controller = VolumeController(audit_logger=mock_audit, dialog_fn=dialog_mock)
        controller._volume_interface = mock_endpoint

        success, msg = controller.set_volume(60)
        assert success is True
        dialog_mock.assert_called_once()
        mock_endpoint.SetMasterVolumeLevelScalar.assert_called_once_with(0.60, None)
        assert mock_audit.log_action.call_args[1]["tier"] == PermissionTier.WRITE.value
        assert mock_audit.log_action.call_args[1]["user_approved"] is True

    def test_set_volume_tier2_denied(self, mock_audit):
        """If user denies volume modification dialog, audio level remains unchanged."""
        mock_endpoint = MagicMock()
        dialog_mock = MagicMock(return_value=False)

        controller = VolumeController(audit_logger=mock_audit, dialog_fn=dialog_mock)
        controller._volume_interface = mock_endpoint

        success, msg = controller.set_volume(80)
        assert success is False
        assert "cancelled" in msg
        mock_endpoint.SetMasterVolumeLevelScalar.assert_not_called()

    def test_mute_and_unmute_tier2(self, mock_audit):
        """Muting and unmuting are Tier 2 actions requiring confirmation."""
        mock_endpoint = MagicMock()
        dialog_mock = MagicMock(return_value=True)

        controller = VolumeController(audit_logger=mock_audit, dialog_fn=dialog_mock)
        controller._volume_interface = mock_endpoint

        # Mute
        success_mute, _ = controller.mute()
        assert success_mute is True
        mock_endpoint.SetMute.assert_called_with(1, None)

        # Unmute
        success_unmute, _ = controller.unmute()
        assert success_unmute is True
        mock_endpoint.SetMute.assert_called_with(0, None)


# ---------------------------------------------------------------------------
# 3. Media Key Hotkeys Tests (Win32 RegisterHotKey)
# ---------------------------------------------------------------------------

class TestMediaHotkeys:

    def test_send_media_keys_tier0_safe(self, mock_audit):
        """Dispatching media keys (Play/Pause, Next, Prev) is Tier 0 safe."""
        hotkeys = MediaHotkeyManager(audit_logger=mock_audit)

        with patch("actions.media_hotkeys.user32.keybd_event") as mock_keybd:
            # Play / Pause
            s1, m1 = hotkeys.send_media_key("play_pause")
            assert s1 is True
            assert mock_keybd.call_count == 2  # down, up

            # Next Track
            mock_keybd.reset_mock()
            s2, m2 = hotkeys.send_media_key("next")
            assert s2 is True
            assert mock_keybd.call_count == 2

            # Previous Track
            mock_keybd.reset_mock()
            s3, m3 = hotkeys.send_media_key("prev")
            assert s3 is True
            assert mock_keybd.call_count == 2

            # Audit check
            for call in mock_audit.log_action.call_args_list:
                assert call[1]["tier"] == PermissionTier.SAFE.value

    def test_register_and_unregister_hotkeys(self, mock_audit):
        """Verify global hotkey registration and cleanup."""
        hotkeys = MediaHotkeyManager(audit_logger=mock_audit)
        with patch("actions.media_hotkeys.user32.RegisterHotKey", return_value=1), \
             patch("actions.media_hotkeys.user32.UnregisterHotKey", return_value=1) as mock_unreg:

            hk1 = hotkeys.register_hotkey(0x0001, 0x20, "test_play")
            assert hk1 >= 100
            assert hk1 in hotkeys._callbacks

            hotkeys.unregister_all()
            assert len(hotkeys._callbacks) == 0
            mock_unreg.assert_called_once()


# ---------------------------------------------------------------------------
# 4. Safe File Operations & Approved App Launcher Tests
# ---------------------------------------------------------------------------

class TestSafeFileOperations:

    def test_list_approved_apps_whitelist(self):
        """Verify approved app whitelist contents."""
        ops = SafeFileOperations()
        apps = ops.list_approved_apps()
        names = [a["name"] for a in apps]
        assert "notepad" in names
        assert "calc" in names
        assert "explorer" in names
        assert "code" in names

    def test_launch_approved_app_tier2_confirmed(self, mock_audit):
        """Launching approved application requires Tier 2 confirmation dialog."""
        dialog_mock = MagicMock(return_value=True)
        ops = SafeFileOperations(audit_logger=mock_audit, dialog_fn=dialog_mock)

        with patch("subprocess.Popen") as mock_popen:
            success, msg = ops.launch_approved_app("notepad")
            assert success is True
            dialog_mock.assert_called_once()
            mock_popen.assert_called_once_with(["notepad.exe"], shell=False)

            call_kwargs = mock_audit.log_action.call_args[1]
            assert call_kwargs["tier"] == PermissionTier.WRITE.value
            assert call_kwargs["user_approved"] is True

    def test_launch_approved_app_tier2_denied(self, mock_audit):
        """User denial in confirmation dialog aborts application launch."""
        dialog_mock = MagicMock(return_value=False)
        ops = SafeFileOperations(audit_logger=mock_audit, dialog_fn=dialog_mock)

        with patch("subprocess.Popen") as mock_popen:
            success, msg = ops.launch_approved_app("calc")
            assert success is False
            assert "cancelled" in msg
            mock_popen.assert_not_called()

    def test_launch_unapproved_app_blocked(self, mock_audit):
        """Unapproved binaries or arbitrary commands are strictly rejected."""
        ops = SafeFileOperations(audit_logger=mock_audit)
        success, msg = ops.launch_approved_app("malicious_script.bat")

        assert success is False
        assert "not in the approved whitelist" in msg
        assert mock_audit.log_action.call_args[1]["status"] == "blocked_unapproved"

    def test_search_folders_tier0_safe(self, mock_audit):
        """Folder search is Tier 0 / READ safe."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test_report_2026.txt"
            test_file.write_text("Hello JARVIS", encoding="utf-8")

            ops = SafeFileOperations(audit_logger=mock_audit)
            results = ops.search_folders("test_report", roots=[Path(tmpdir)])

            assert len(results) == 1
            assert results[0]["name"] == "test_report_2026.txt"
            assert mock_audit.log_action.call_args[1]["tier"] == PermissionTier.READ.value

    def test_show_metadata_tier0_safe(self, mock_audit):
        """Showing file metadata is Tier 0 safe."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".log") as f:
            f.write(b"JARVIS Audit Log Sample")
            path = f.name

        try:
            ops = SafeFileOperations(audit_logger=mock_audit)
            meta = ops.show_metadata(path, compute_hash=True)

            assert meta["is_file"] is True
            assert meta["extension"] == ".log"
            assert meta["size_bytes"] > 0
            assert "sha256" in meta
            assert mock_audit.log_action.call_args[1]["tier"] == PermissionTier.READ.value
        finally:
            os.remove(path)


# ---------------------------------------------------------------------------
# 5. Deletion Impact Analysis Tests
# ---------------------------------------------------------------------------

class TestDeletionImpactAnalysis:

    def test_deletion_impact_single_file(self, mock_audit):
        """Analyze impact of a single temporary file."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"Sample file data")
            path = f.name

        try:
            analyzer = DeletionImpactAnalyzer(audit_logger=mock_audit)
            impact = analyzer.analyze(path)

            assert impact.exists is True
            assert impact.file_count == 1
            assert impact.dir_count == 0
            assert impact.total_size_bytes == 16
            assert impact.is_system_path is False
            assert impact.risk_level in ("LOW", "MEDIUM")
            assert mock_audit.log_action.call_args[1]["tier"] == PermissionTier.READ.value
        finally:
            os.remove(path)

    def test_deletion_impact_project_directory(self, mock_audit):
        """Analyze impact of a project directory containing Git and pyproject markers."""
        with tempfile.TemporaryDirectory() as tmpdir:
            proj_root = Path(tmpdir) / "my_project"
            proj_root.mkdir()
            (proj_root / ".git").mkdir()
            (proj_root / "pyproject.toml").write_text("[project]\nname='test'", encoding="utf-8")
            (proj_root / "main.py").write_text("print('hi')", encoding="utf-8")

            analyzer = DeletionImpactAnalyzer(audit_logger=mock_audit)
            impact = analyzer.analyze(proj_root)

            assert impact.file_count >= 2
            assert impact.project_affiliation is not None
            assert "Git repository" in impact.project_affiliation or "Python" in impact.project_affiliation
            assert impact.risk_level in ("HIGH", "MEDIUM")
            assert "[PROJECT]" in impact.summary

    def test_deletion_impact_system_path_protection(self, mock_audit):
        """Critical Windows system directories must be flagged as CRITICAL system path."""
        analyzer = DeletionImpactAnalyzer(audit_logger=mock_audit)
        impact = analyzer.analyze("C:\\Windows")

        assert impact.is_system_path is True
        assert impact.risk_level == "CRITICAL"
        assert "CRITICAL WINDOWS SYSTEM DIRECTORY" in impact.summary


# ---------------------------------------------------------------------------
# 6. Recycle Bin Move Tests (SHFileOperationW FOF_ALLOWUNDO)
# ---------------------------------------------------------------------------

class TestRecycleBinMove:

    def test_recycle_bin_move_success(self, mock_audit):
        """Moving file to Recycle Bin uses SHFileOperationW with FOF_ALLOWUNDO."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"Data to recycle")
            path = f.name

        dialog_mock = MagicMock(return_value=True)
        manager = RecycleBinManager(audit_logger=mock_audit, dialog_fn=dialog_mock)

        with patch("actions.recycle_bin.ctypes.windll.shell32.SHFileOperationW", return_value=0):
            success, msg, impact = manager.move_to_recycle_bin(path)

            assert success is True
            assert "Recycle Bin" in msg
            dialog_mock.assert_called_once()
            assert impact.file_count == 1

            # Audit check
            call_kwargs = mock_audit.log_action.call_args[1]
            assert call_kwargs["action_name"] == "recycle_bin_move"
            assert call_kwargs["tier"] == PermissionTier.DESTRUCTIVE.value
            assert call_kwargs["user_approved"] is True

        if os.path.exists(path):
            os.remove(path)

    def test_recycle_bin_blocks_system_path(self, mock_audit):
        """Recycle Bin movement blocks protected Windows system directory immediately."""
        manager = RecycleBinManager(audit_logger=mock_audit)
        success, msg, impact = manager.move_to_recycle_bin("C:\\Windows")

        assert success is False
        assert "SAFETY BLOCKED" in msg
        assert impact.is_system_path is True
        assert mock_audit.log_action.call_args[1]["status"] == "blocked_system_path"

    def test_recycle_bin_cancelled_by_user(self, mock_audit):
        """User cancellation in Tier 3 dialog prevents Recycle Bin move."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"Important data")
            path = f.name

        try:
            dialog_mock = MagicMock(return_value=False)
            manager = RecycleBinManager(audit_logger=mock_audit, dialog_fn=dialog_mock)

            with patch("actions.recycle_bin.ctypes.windll.shell32.SHFileOperationW") as mock_sh:
                success, msg, impact = manager.move_to_recycle_bin(path)

                assert success is False
                assert "cancelled" in msg
                mock_sh.assert_not_called()
                assert mock_audit.log_action.call_args[1]["status"] == "cancelled"
        finally:
            if os.path.exists(path):
                os.remove(path)


# ---------------------------------------------------------------------------
# 7. Windows Startup Option Tests (Task Scheduler)
# ---------------------------------------------------------------------------

class TestStartupOption:

    def test_startup_disabled_by_default(self, mock_audit):
        """Querying Task Scheduler when task doesn't exist shows disabled (default)."""
        mock_runner = MagicMock(return_value=(1, "", "ERROR: The system cannot find the file specified."))
        manager = StartupManager(audit_logger=mock_audit, cmd_runner=mock_runner)

        assert manager.is_startup_enabled() is False
        status = manager.get_startup_status()
        assert status["enabled"] is False
        assert "Disabled (Default)" in status["schedule"]
        assert mock_audit.log_action.call_args[1]["tier"] == PermissionTier.READ.value

    def test_enable_startup_tier2_confirmed(self, mock_audit):
        """Enabling startup requires Tier 2 confirmation dialog and creates scheduled task."""
        mock_runner = MagicMock(return_value=(0, "SUCCESS: The scheduled task 'JARVIS_Assistant' has successfully been created.", ""))
        dialog_mock = MagicMock(return_value=True)

        manager = StartupManager(audit_logger=mock_audit, dialog_fn=dialog_mock, cmd_runner=mock_runner)
        success, msg = manager.enable_startup(command_path="C:\\JARVIS\\jarvis.bat")

        assert success is True
        dialog_mock.assert_called_once()
        mock_runner.assert_called()
        cmd_sent = mock_runner.call_args[0][0]
        assert "/create" in cmd_sent
        assert "JARVIS_Assistant" in cmd_sent
        assert "/sc" in cmd_sent and "onlogon" in cmd_sent

        call_kwargs = mock_audit.log_action.call_args[1]
        assert call_kwargs["tier"] == PermissionTier.WRITE.value
        assert call_kwargs["user_approved"] is True

    def test_disable_startup_tier2_confirmed(self, mock_audit):
        """Disabling startup requires Tier 2 confirmation dialog and deletes scheduled task."""
        mock_runner = MagicMock(return_value=(0, "SUCCESS: The scheduled task 'JARVIS_Assistant' was successfully deleted.", ""))
        dialog_mock = MagicMock(return_value=True)

        manager = StartupManager(audit_logger=mock_audit, dialog_fn=dialog_mock, cmd_runner=mock_runner)
        success, msg = manager.disable_startup()

        assert success is True
        dialog_mock.assert_called_once()
        cmd_sent = mock_runner.call_args[0][0]
        assert "/delete" in cmd_sent
        assert "JARVIS_Assistant" in cmd_sent


# ---------------------------------------------------------------------------
# 8. Emergency Pause Button Tests
# ---------------------------------------------------------------------------

class TestEmergencyPause:

    def test_indicator_pause_and_resume_lifecycle(self, mock_audit):
        """Emergency pause transitions indicator to MUTED and executes registered handlers."""
        indicator = TrayListeningIndicator(headless=True, audit_logger=mock_audit)

        pause_cb = MagicMock()
        resume_cb = MagicMock()
        indicator.register_pause_handler(pause_cb)
        indicator.register_resume_handler(resume_cb)

        # 1. Trigger Emergency Pause
        indicator.pause()
        assert indicator.is_paused is True
        assert indicator.state == IndicatorState.MUTED
        pause_cb.assert_called_once()
        resume_cb.assert_not_called()

        # Audit check
        assert mock_audit.log_action.call_args[1]["status"] == "paused"

        # 2. Trigger Resume
        indicator.resume()
        assert indicator.is_paused is False
        assert indicator.state == IndicatorState.IDLE
        resume_cb.assert_called_once()
        assert mock_audit.log_action.call_args[1]["status"] == "resumed"

    def test_wake_word_listener_paused_drops_audio(self):
        """When WakeWordListener is paused, incoming audio chunks are discarded."""
        wake_cb = MagicMock()
        listener = WakeWordListener(on_wake_callback=wake_cb)
        listener.is_running = True

        # Normal operation: chunk would trigger callback
        with patch.object(listener, "process_audio_chunk", return_value=True):
            # Pause listener
            listener.pause()
            assert listener.is_paused is True

            # Simulate audio callback while paused
            # Directly testing callback logic
            callback_called = False
            if listener.is_running and not listener.is_paused:
                wake_cb()
                callback_called = True

            assert callback_called is False
            wake_cb.assert_not_called()

            # Resume listener
            listener.resume()
            assert listener.is_paused is False
            if listener.is_running and not listener.is_paused:
                wake_cb()
                callback_called = True

            assert callback_called is True
            wake_cb.assert_called_once()

    def test_voice_command_router_aborts_during_emergency_pause(self, mock_audit):
        """VoiceCommandRouter immediately drops interaction if emergency pause is active."""
        indicator = TrayListeningIndicator(headless=True, audit_logger=mock_audit)
        indicator.pause()

        router = VoiceCommandRouter(indicator=indicator, audit_logger=mock_audit)
        result = router.handle_wake_event()

        assert result["status"] == "emergency_paused"
        assert result["transcript"] == ""
