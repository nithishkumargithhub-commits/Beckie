"""
JARVIS – Microphone Permission Manager (Windows native dialog via pywin32).

Prompts user for microphone access using Windows MessageBox dialog (win32gui / pywin32).
Integrates with PermissionBroker and AuditLogger to record permission state.
"""

from __future__ import annotations

import logging
import sys
from typing import Callable, Optional

logger = logging.getLogger("Jarvis.Pipeline.MicPermission")

_MIC_ACTION_NAME = "microphone_access"


class MicrophonePermissionManager:
    """Manages microphone access permission and native Windows prompt dialog."""

    def __init__(
        self,
        permission_broker=None,
        audit_logger=None,
        dialog_fn: Optional[Callable[[str, str], bool]] = None,
    ):
        self._broker = permission_broker
        self._audit = audit_logger
        self._dialog_fn = dialog_fn or self._default_windows_dialog
        self._cached_granted: Optional[bool] = None

    def has_permission(self) -> bool:
        """Check if microphone permission has already been approved for this session."""
        if self._cached_granted is not None:
            return self._cached_granted

        if self._broker is not None:
            if self._broker.is_granted(_MIC_ACTION_NAME):
                self._cached_granted = True
                return True

        return False

    def request_permission(self, parent_hwnd: int = 0) -> bool:
        """
        Request microphone access. If already granted, returns True immediately.
        Otherwise, displays a native Windows dialog prompt.
        """
        if self.has_permission():
            logger.debug("Microphone permission already granted for this session.")
            return True

        title = "JARVIS – Microphone Access Request"
        message = (
            "JARVIS requires access to your microphone to listen for voice commands.\n\n"
            "Privacy notice:\n"
            "• Wake-word detection runs 100% locally on your PC (openWakeWord).\n"
            "• Speech recognition is only active after the wake-word is detected.\n"
            "• Whisper STT is unloaded immediately after transcribing.\n\n"
            "Do you allow JARVIS to access your microphone?"
        )

        logger.info("Prompting user for microphone permission via Windows dialog...")
        granted = self._dialog_fn(title, message)
        self._cached_granted = granted

        if self._broker is not None:
            if granted:
                self._broker.grant_session_action(_MIC_ACTION_NAME)
            else:
                self._broker.revoke_session_action(_MIC_ACTION_NAME)

        if self._audit is not None:
            self._audit.log_permission(
                action_name=_MIC_ACTION_NAME,
                tier="read",
                granted=granted,
                user_approved=granted,
                resource="hardware:microphone",
            )

        if granted:
            logger.info("Microphone permission GRANTED by user.")
        else:
            logger.warning("Microphone permission DENIED by user.")

        return granted

    def revoke_permission(self) -> None:
        """Revoke microphone permission for current session."""
        self._cached_granted = False
        if self._broker is not None:
            self._broker.revoke_session_action(_MIC_ACTION_NAME)
        if self._audit is not None:
            self._audit.log_system("microphone_permission_revoked")
        logger.info("Microphone permission revoked.")

    @staticmethod
    def _default_windows_dialog(title: str, message: str) -> bool:
        """Native Windows MessageBox dialog via pywin32."""
        try:
            import win32con
            import win32gui
            # MB_YESNO | MB_ICONQUESTION | MB_TOPMOST
            flags = win32con.MB_YESNO | win32con.MB_ICONQUESTION | win32con.MB_TOPMOST
            result = win32gui.MessageBox(0, message, title, flags)
            return result == win32con.IDYES
        except Exception as exc:
            logger.warning("win32gui dialog failed (%s), falling back to console prompt", exc)
            try:
                ans = input(f"{title}\n{message}\nAllow? [y/N]: ").strip().lower()
                return ans in ("y", "yes")
            except Exception:
                return False
