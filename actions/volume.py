"""
JARVIS – Safe Windows Volume Control using AudioEndpointVolume API (pycaw).

Features:
- Direct hardware endpoint volume integration via pycaw / comtypes.
- Defensive COM thread initialization (CoInitialize) for multi-threaded safety.
- Tier 0 for reading volume and mute state (no approval required).
- Tier 2 (WRITE) for volume level modifications and mute toggles (requires explicit confirmation dialog).
- Comprehensive audit logging of all actions with timestamps.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Optional, Tuple

from actions.windows_dialog import show_confirmation_dialog
from core.audit_logger import AuditLogger
from core.permission_broker import PermissionBroker, PermissionTier

logger = logging.getLogger("Jarvis.Actions.Volume")


class VolumeController:
    """Controls master audio output via Windows AudioEndpointVolume COM interface."""

    def __init__(
        self,
        broker: Optional[PermissionBroker] = None,
        audit_logger: Optional[AuditLogger] = None,
        dialog_fn: Optional[Callable[[str, str, bool], bool]] = None,
    ):
        self.broker = broker
        self.audit_logger = audit_logger
        self.dialog_fn = dialog_fn or (lambda title, msg, is_destr: show_confirmation_dialog(title, msg, is_destr))
        self._volume_interface = None

    def _get_interface(self):
        """Acquire the IAudioEndpointVolume interface with COM initialization."""
        if self._volume_interface is not None:
            return self._volume_interface

        try:
            import comtypes

            comtypes.CoInitialize()

            from ctypes import POINTER, cast
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

            speakers = AudioUtilities.GetSpeakers()
            if hasattr(speakers, "EndpointVolume"):
                self._volume_interface = speakers.EndpointVolume
            elif hasattr(speakers, "Activate"):
                self._volume_interface = cast(
                    speakers.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None),
                    POINTER(IAudioEndpointVolume),
                )
            else:
                logger.error("AudioUtilities.GetSpeakers() returned unrecognized object: %r", speakers)
                self._volume_interface = None
        except Exception as exc:
            logger.error("Failed to initialize pycaw AudioEndpointVolume interface: %s", exc)
            self._volume_interface = None

        return self._volume_interface

    def get_volume(self) -> Optional[int]:
        """
        Get current master volume level percentage (0-100).
        Tier 0 (SAFE) – no approval required.
        """
        start_time = time.time()
        interface = self._get_interface()
        if not interface:
            return None

        try:
            scalar = interface.GetMasterVolumeLevelScalar()
            level = int(round(scalar * 100))

            if self.audit_logger is not None:
                self.audit_logger.log_action(
                    action_type="windows_control",
                    action_name="get_volume",
                    tier=PermissionTier.SAFE.value,
                    status="success",
                    user_approved=True,
                    actor="user",
                    resource="hardware:audio_master",
                    details={"volume_percent": level},
                    duration_ms=int((time.time() - start_time) * 1000),
                )
            return level
        except Exception as exc:
            logger.error("Error reading volume level: %s", exc)
            return None

    def is_muted(self) -> Optional[bool]:
        """
        Get current mute status.
        Tier 0 (SAFE) – no approval required.
        """
        start_time = time.time()
        interface = self._get_interface()
        if not interface:
            return None

        try:
            muted = bool(interface.GetMute())
            if self.audit_logger is not None:
                self.audit_logger.log_action(
                    action_type="windows_control",
                    action_name="is_muted",
                    tier=PermissionTier.SAFE.value,
                    status="success",
                    user_approved=True,
                    actor="user",
                    resource="hardware:audio_master",
                    details={"is_muted": muted},
                    duration_ms=int((time.time() - start_time) * 1000),
                )
            return muted
        except Exception as exc:
            logger.error("Error checking mute status: %s", exc)
            return None

    def set_volume(self, level: int, force_unconfirmed: bool = False) -> Tuple[bool, str]:
        """
        Set master volume level (0-100).
        Tier 2 (WRITE) – requires confirmation dialog before modification.
        """
        start_time = time.time()
        level = max(0, min(100, int(level)))
        action_name = "set_volume"

        # Tier 2 confirmation check
        user_approved = True
        if not force_unconfirmed:
            if self.broker is not None:
                perm = self.broker.request(
                    action_name=action_name,
                    resource="hardware:audio_master",
                    details={"level": level},
                    actor="user",
                )
                if not perm.granted:
                    msg = f"Volume adjustment to {level}% cancelled by user."
                    return False, msg
                user_approved = perm.user_approved
            else:
                title = "JARVIS – Confirm Volume Change"
                prompt_msg = (
                    f"Action: Set System Volume\n"
                    f"Requested Level: {level}%\n\n"
                    f"Do you want to apply this volume change?"
                )
                user_approved = self.dialog_fn(title, prompt_msg, False)
                if not user_approved:
                    msg = f"Volume change to {level}% cancelled by user."
                    self._log_audit(action_name, "cancelled", level, False, start_time, msg)
                    return False, msg

        interface = self._get_interface()
        if not interface:
            err = "Volume control interface unavailable."
            self._log_audit(action_name, "failed", level, user_approved, start_time, err)
            return False, err

        try:
            interface.SetMasterVolumeLevelScalar(level / 100.0, None)
            msg = f"Volume set to {level} percent."
            logger.info(msg)
            self._log_audit(action_name, "success", level, user_approved, start_time, msg)
            return True, msg
        except Exception as exc:
            err = f"Failed to set volume: {exc}"
            logger.error(err)
            self._log_audit(action_name, "failed", level, user_approved, start_time, err)
            return False, err

    def mute(self, force_unconfirmed: bool = False) -> Tuple[bool, str]:
        """
        Mute master audio output.
        Tier 2 (WRITE) – requires confirmation dialog.
        """
        return self._set_mute_state(mute_val=1, action_name="mute_volume", force_unconfirmed=force_unconfirmed)

    def unmute(self, force_unconfirmed: bool = False) -> Tuple[bool, str]:
        """
        Unmute master audio output.
        Tier 2 (WRITE) – requires confirmation dialog.
        """
        return self._set_mute_state(mute_val=0, action_name="unmute_volume", force_unconfirmed=force_unconfirmed)

    def toggle_mute(self, force_unconfirmed: bool = False) -> Tuple[bool, str]:
        """
        Toggle mute state.
        Tier 2 (WRITE) – requires confirmation dialog.
        """
        current = self.is_muted()
        if current is None:
            return False, "Could not determine mute status."
        new_state = 0 if current else 1
        action_name = "unmute_volume" if current else "mute_volume"
        return self._set_mute_state(mute_val=new_state, action_name=action_name, force_unconfirmed=force_unconfirmed)

    def _set_mute_state(self, mute_val: int, action_name: str, force_unconfirmed: bool) -> Tuple[bool, str]:
        start_time = time.time()
        verb = "Mute" if mute_val == 1 else "Unmute"

        user_approved = True
        if not force_unconfirmed:
            if self.broker is not None:
                perm = self.broker.request(
                    action_name=action_name,
                    resource="hardware:audio_master",
                    details={"mute": bool(mute_val)},
                    actor="user",
                )
                if not perm.granted:
                    msg = f"{verb} audio cancelled by user."
                    return False, msg
                user_approved = perm.user_approved
            else:
                title = f"JARVIS – Confirm {verb} Audio"
                prompt_msg = f"Do you want to {verb.lower()} system audio output?"
                user_approved = self.dialog_fn(title, prompt_msg, False)
                if not user_approved:
                    msg = f"{verb} audio cancelled by user."
                    self._log_audit(action_name, "cancelled", mute_val, False, start_time, msg)
                    return False, msg

        interface = self._get_interface()
        if not interface:
            err = "Volume control interface unavailable."
            self._log_audit(action_name, "failed", mute_val, user_approved, start_time, err)
            return False, err

        try:
            interface.SetMute(mute_val, None)
            msg = "System volume muted." if mute_val == 1 else "System volume unmuted."
            logger.info(msg)
            self._log_audit(action_name, "success", mute_val, user_approved, start_time, msg)
            return True, msg
        except Exception as exc:
            err = f"Failed to modify mute state: {exc}"
            logger.error(err)
            self._log_audit(action_name, "failed", mute_val, user_approved, start_time, err)
            return False, err

    def _log_audit(
        self,
        action_name: str,
        status: str,
        value: Any,
        approved: bool,
        start_time: float,
        message: str,
    ) -> None:
        if self.audit_logger is not None:
            self.audit_logger.log_action(
                action_type="windows_control",
                action_name=action_name,
                tier=PermissionTier.WRITE.value,
                status=status,
                user_approved=approved,
                actor="user",
                resource="hardware:audio_master",
                details={"value": value, "result": message},
                duration_ms=int((time.time() - start_time) * 1000),
            )


# Default module instance and convenience wrappers
volume_controller = VolumeController()


def get_volume() -> Optional[int]:
    return volume_controller.get_volume()


def is_muted() -> Optional[bool]:
    return volume_controller.is_muted()


def set_volume(level: int) -> str:
    _, msg = volume_controller.set_volume(level)
    return msg


def mute() -> str:
    _, msg = volume_controller.mute()
    return msg


def unmute() -> str:
    _, msg = volume_controller.unmute()
    return msg


def toggle_mute() -> str:
    _, msg = volume_controller.toggle_mute()
    return msg
