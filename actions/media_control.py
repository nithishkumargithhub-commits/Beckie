import ctypes
import logging

logger = logging.getLogger("VoiceAssistant.MediaControl")

# Win32 keybd_event API function
keybd_event = ctypes.windll.user32.keybd_event

# Virtual Key Codes for Media Keys
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_PLAY_PAUSE = 0xB3

KEYEVENTF_KEYUP = 0x0002

def _press_media_key(vk_code: int):
    # Key down
    keybd_event(vk_code, 0, 0, 0)
    # Key up
    keybd_event(vk_code, 0, KEYEVENTF_KEYUP, 0)

def control_media(action: str) -> tuple[bool, str]:
    """
    Simulates media playback hotkeys.
    action can be: "play_pause" (or "play", "pause", "toggle"), "next", "prev" (or "previous")
    """
    action = action.strip().lower()
    try:
        if action in ["play_pause", "play", "pause", "toggle"]:
            _press_media_key(VK_MEDIA_PLAY_PAUSE)
            msg = "Toggled media playback."
            logger.info(msg)
            return True, msg
        elif action in ["next", "skip"]:
            _press_media_key(VK_MEDIA_NEXT_TRACK)
            msg = "Skipping to the next track."
            logger.info(msg)
            return True, msg
        elif action in ["prev", "previous", "back"]:
            _press_media_key(VK_MEDIA_PREV_TRACK)
            msg = "Going back to the previous track."
            logger.info(msg)
            return True, msg
        else:
            return False, f"Unknown media action: {action}"
    except Exception as e:
        logger.error(f"Media control error: {e}")
        return False, f"Failed to perform media action: {e}"
