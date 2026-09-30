"""
JARVIS – Media Key Hotkeys Manager using Win32 RegisterHotKey API.

Features:
- Global system hotkey registration via ctypes.windll.user32.RegisterHotKey.
- Dedicated Win32 message pump thread dispatching WM_HOTKEY events.
- Handles Play/Pause, Next Track, Previous Track, and Stop.
- Virtual media key simulation via keybd_event.
- Tier 0 (SAFE) – no approval required for media controls.
- Full audit logging of registrations and triggers with timestamps.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import logging
import threading
import time
from typing import Any, Callable, Dict, Optional, Tuple

from core.audit_logger import AuditLogger
from core.permission_broker import PermissionBroker, PermissionTier

logger = logging.getLogger("Jarvis.Actions.MediaHotkeys")

# Win32 Virtual Key Codes
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_STOP = 0xB2
VK_MEDIA_PLAY_PAUSE = 0xB3

# Hotkey Modifier flags
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

# Windows Messages
WM_HOTKEY = 0x0312
KEYEVENTF_KEYUP = 0x0002

user32 = ctypes.windll.user32


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", wintypes.POINT),
    ]


class MediaHotkeyManager:
    """Manages global media key hotkeys and dispatches playback commands."""

    def __init__(
        self,
        broker: Optional[PermissionBroker] = None,
        audit_logger: Optional[AuditLogger] = None,
    ):
        self.broker = broker
        self.audit_logger = audit_logger
        self._callbacks: Dict[int, Tuple[str, Callable[[], None]]] = {}
        self._next_hotkey_id = 100
        self._is_running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def send_media_key(self, action: str) -> Tuple[bool, str]:
        """
        Synthesize a hardware media key press.
        Tier 0 (SAFE) – no approval required.

        Actions: 'play_pause', 'play', 'pause', 'toggle', 'next', 'prev', 'stop'
        """
        start_time = time.time()
        act = action.strip().lower()

        vk_code = None
        action_name = "media_play_pause"
        msg = "Toggled media playback."

        if act in ("play_pause", "play", "pause", "toggle"):
            vk_code = VK_MEDIA_PLAY_PAUSE
            action_name = "media_play_pause"
            msg = "Toggled media playback (Play/Pause)."
        elif act in ("next", "skip"):
            vk_code = VK_MEDIA_NEXT_TRACK
            action_name = "media_next"
            msg = "Skipped to next media track."
        elif act in ("prev", "previous", "back"):
            vk_code = VK_MEDIA_PREV_TRACK
            action_name = "media_prev"
            msg = "Returned to previous media track."
        elif act in ("stop",):
            vk_code = VK_MEDIA_STOP
            action_name = "media_stop"
            msg = "Stopped media playback."
        else:
            return False, f"Unknown media action: {action}"

        try:
            # Key down then key up
            user32.keybd_event(vk_code, 0, 0, 0)
            user32.keybd_event(vk_code, 0, KEYEVENTF_KEYUP, 0)
            logger.info("Dispatched media key: %s (VK 0x%02X)", action_name, vk_code)

            if self.audit_logger is not None:
                self.audit_logger.log_action(
                    action_type="windows_control",
                    action_name=action_name,
                    tier=PermissionTier.SAFE.value,
                    status="success",
                    user_approved=True,
                    actor="user",
                    resource="hardware:media_keys",
                    details={"action": act, "vk_code": hex(vk_code)},
                    duration_ms=int((time.time() - start_time) * 1000),
                )
            return True, msg
        except Exception as exc:
            err = f"Failed to send media key {action}: {exc}"
            logger.error(err)
            return False, err

    def register_hotkey(
        self,
        modifiers: int,
        vk: int,
        action_name: str,
        callback: Optional[Callable[[], None]] = None,
    ) -> int:
        """
        Register a global hotkey with a given modifier combination and virtual key.
        Returns the hotkey ID.
        """
        with self._lock:
            hk_id = self._next_hotkey_id
            self._next_hotkey_id += 1

            # Default callback triggers send_media_key if not custom
            cb = callback or (lambda a=action_name: self.send_media_key(a))
            self._callbacks[hk_id] = (action_name, cb)

            success = bool(user32.RegisterHotKey(0, hk_id, modifiers | MOD_NOREPEAT, vk))
            if success:
                logger.info(
                    "Registered hotkey ID=%d for '%s' (modifiers=0x%04X, vk=0x%02X)",
                    hk_id,
                    action_name,
                    modifiers,
                    vk,
                )
            else:
                logger.warning(
                    "Failed to register hotkey ID=%d for '%s' (error=%d)",
                    hk_id,
                    action_name,
                    ctypes.GetLastError(),
                )

            if self.audit_logger is not None:
                self.audit_logger.log_action(
                    action_type="windows_control",
                    action_name="register_hotkey",
                    tier=PermissionTier.SAFE.value,
                    status="success" if success else "failed",
                    user_approved=True,
                    actor="system",
                    resource=f"hotkey:{action_name}",
                    details={"hotkey_id": hk_id, "registered": success},
                )

            return hk_id

    def setup_default_media_hotkeys(self) -> None:
        """
        Register standard media key shortcuts:
        - Ctrl + Alt + Space: Play / Pause
        - Ctrl + Alt + Right: Next Track
        - Ctrl + Alt + Left:  Previous Track
        """
        VK_SPACE = 0x20
        VK_RIGHT = 0x27
        VK_LEFT = 0x25

        mods = MOD_CONTROL | MOD_ALT
        self.register_hotkey(mods, VK_SPACE, "play_pause")
        self.register_hotkey(mods, VK_RIGHT, "next")
        self.register_hotkey(mods, VK_LEFT, "prev")

    def unregister_all(self) -> None:
        """Unregister all registered hotkeys."""
        with self._lock:
            for hk_id in list(self._callbacks.keys()):
                user32.UnregisterHotKey(0, hk_id)
            self._callbacks.clear()
        logger.info("Unregistered all global hotkeys.")

    def start_listener(self) -> None:
        """Start the background Win32 message pump for hotkeys."""
        if self._is_running:
            return
        self._is_running = True
        self._thread = threading.Thread(target=self._message_loop, daemon=True)
        self._thread.start()
        logger.info("Media hotkey message loop started.")

    def stop_listener(self) -> None:
        """Stop message pump and unregister hotkeys."""
        self._is_running = False
        self.unregister_all()
        logger.info("Media hotkey message loop stopped.")

    def _message_loop(self) -> None:
        """Win32 message pump processing WM_HOTKEY."""
        msg = MSG()
        while self._is_running:
            # Non-blocking peek message
            has_msg = user32.PeekMessageW(ctypes.byref(msg), 0, 0, 0, 1)  # PM_REMOVE = 1
            if has_msg:
                if msg.message == WM_HOTKEY:
                    hk_id = msg.wParam
                    with self._lock:
                        entry = self._callbacks.get(hk_id)
                    if entry:
                        action_name, callback = entry
                        logger.info("WM_HOTKEY triggered for '%s' (id=%d)", action_name, hk_id)
                        try:
                            callback()
                        except Exception as exc:
                            logger.error("Error executing hotkey callback for '%s': %s", action_name, exc)
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            else:
                time.sleep(0.05)


# Global singleton instance
media_hotkeys = MediaHotkeyManager()
