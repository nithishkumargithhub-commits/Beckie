"""
JARVIS – Windows Native Confirmation Dialog Utility.

Provides standard Win32 MessageBox confirmation dialogs for Tier 2+ actions
(WRITE and DESTRUCTIVE) with explicit prompt details, action summaries,
and testable injection points.
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

logger = logging.getLogger("Jarvis.Actions.WindowsDialog")

# Test hook / custom provider: if set, overrides the dialog display
_custom_dialog_handler: Optional[Callable[[str, str, bool], bool]] = None


def set_dialog_handler(handler: Optional[Callable[[str, str, bool], bool]]) -> None:
    """Set a custom dialog handler (primarily for testing or UI redirect)."""
    global _custom_dialog_handler
    _custom_dialog_handler = handler


def show_confirmation_dialog(
    title: str,
    message: str,
    is_destructive: bool = False,
    parent_hwnd: int = 0,
) -> bool:
    """
    Display a native Windows confirmation dialog for Tier 2+ actions.

    Parameters:
        title: Dialog window title.
        message: Multi-line description of the action and its impact.
        is_destructive: True if Tier 3 DESTRUCTIVE (shows Warning/Exclamation icon).
        parent_hwnd: Parent window handle (0 for desktop).

    Returns:
        bool: True if user clicked Yes / confirmed, False otherwise.
    """
    if _custom_dialog_handler is not None:
        return _custom_dialog_handler(title, message, is_destructive)

    try:
        import win32con
        import win32gui

        icon = win32con.MB_ICONWARNING if is_destructive else win32con.MB_ICONQUESTION
        flags = win32con.MB_YESNO | icon | win32con.MB_TOPMOST | win32con.MB_DEFBUTTON2
        result = win32gui.MessageBox(parent_hwnd, message, title, flags)
        return result == win32con.IDYES
    except Exception as exc:
        logger.warning("win32gui MessageBox failed (%s), falling back to console prompt", exc)
        try:
            print(f"\n[JARVIS CONFIRMATION] {title}")
            print(message)
            prompt = "Type YES to confirm: " if is_destructive else "Allow? [y/N]: "
            ans = input(prompt).strip().lower()
            if is_destructive:
                return ans in ("yes", "y")
            return ans in ("y", "yes")
        except (EOFError, KeyboardInterrupt):
            return False
