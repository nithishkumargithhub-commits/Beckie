"""
JARVIS – Offline Windows Media Control Action.
Delegates to MediaHotkeyManager for Win32 virtual key dispatching and audit logging.
"""

from __future__ import annotations

import logging
from actions.media_hotkeys import media_hotkeys, VK_MEDIA_NEXT_TRACK, VK_MEDIA_PREV_TRACK, VK_MEDIA_PLAY_PAUSE

logger = logging.getLogger("VoiceAssistant.MediaControl")


def control_media(action: str) -> tuple[bool, str]:
    """
    Simulates media playback hotkeys.
    action can be: 'play_pause' (or 'play', 'pause', 'toggle'), 'next', 'prev' (or 'previous')
    """
    return media_hotkeys.send_media_key(action)
