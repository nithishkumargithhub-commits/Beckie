import ctypes
import logging

logger = logging.getLogger("VoiceAssistant.WindowManager")

# Win32 API functions
GetForegroundWindow = ctypes.windll.user32.GetForegroundWindow
ShowWindow = ctypes.windll.user32.ShowWindow
PostMessageW = ctypes.windll.user32.PostMessageW

# ShowWindow commands
SW_MINIMIZE = 6
SW_MAXIMIZE = 3
SW_RESTORE = 9

# PostMessage messages
WM_CLOSE = 0x0010

def manage_window(action: str) -> tuple[bool, str]:
    """
    Manages the active foreground window.
    action can be: "minimize", "maximize", "close"
    """
    action = action.strip().lower()
    hwnd = GetForegroundWindow()
    if not hwnd:
        return False, "I could not find an active window to control."
        
    try:
        if action == "minimize":
            ShowWindow(hwnd, SW_MINIMIZE)
            msg = "Minimizing the active window."
            logger.info(msg)
            return True, msg
        elif action == "maximize":
            ShowWindow(hwnd, SW_MAXIMIZE)
            msg = "Maximizing the active window."
            logger.info(msg)
            return True, msg
        elif action == "close":
            PostMessageW(hwnd, WM_CLOSE, 0, 0)
            msg = "Closing the active window."
            logger.info(msg)
            return True, msg
        else:
            return False, f"Unknown window action: {action}"
    except Exception as e:
        logger.error(f"Window management error: {e}")
        return False, f"Failed to perform window action: {e}"
