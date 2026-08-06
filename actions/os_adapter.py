import sys
import os
import subprocess
import logging
from typing import Tuple

logger = logging.getLogger("VoiceAssistant.OSAdapter")

IS_WINDOWS = sys.platform == "win32"
IS_MACOS = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")

def set_volume(level_percent: float) -> Tuple[bool, str]:
    """
    Sets system output volume across Windows, macOS, and Linux.
    """
    level_clamped = max(0.0, min(100.0, float(level_percent)))
    
    if IS_WINDOWS:
        try:
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            from comtypes import CLSCTX_ALL
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = interface.QueryInterface(IAudioEndpointVolume)
            # Volume scalar from 0.0 to 1.0
            volume.SetMasterVolumeLevelScalar(level_clamped / 100.0, None)
            return True, f"System volume set to {int(level_clamped)}%."
        except Exception as e:
            logger.error(f"Pycaw volume change failed on Windows: {e}")
            return False, f"Failed to set volume: {e}"
            
    elif IS_MACOS:
        try:
            vol_val = int(level_clamped)
            subprocess.run(["osascript", "-e", f"set volume output volume {vol_val}"], check=True)
            return True, f"System volume set to {vol_val}%."
        except Exception as e:
            return False, f"Failed to set volume on macOS: {e}"
            
    elif IS_LINUX:
        try:
            vol_val = int(level_clamped)
            subprocess.run(["amixer", "sset", "'Master'", f"{vol_val}%"], check=True)
            return True, f"System volume set to {vol_val}%."
        except Exception as e:
            return False, f"Failed to set volume on Linux: {e}"
            
    return False, "Unsupported operating system platform."

def set_brightness(level_percent: float) -> Tuple[bool, str]:
    """
    Sets display screen brightness across platforms.
    """
    level_clamped = max(0.0, min(100.0, float(level_percent)))
    
    try:
        import screen_brightness_control as sbc
        sbc.set_brightness(int(level_clamped))
        return True, f"Display brightness set to {int(level_clamped)}%."
    except Exception as e:
        logger.warning(f"screen_brightness_control failed: {e}")
        
    if IS_MACOS:
        try:
            val = level_clamped / 100.0
            subprocess.run(["brightness", str(val)], check=True)
            return True, f"Display brightness set to {int(level_clamped)}%."
        except Exception as err:
            return False, f"Failed to set brightness on macOS: {err}"
            
    return False, f"Could not adjust brightness: screen_brightness_control unsupported on this hardware."

def lock_screen() -> Tuple[bool, str]:
    """
    Locks the user workstation.
    """
    if IS_WINDOWS:
        try:
            import ctypes
            ctypes.windll.user32.LockWorkStation()
            return True, "Workstation locked successfully."
        except Exception as e:
            return False, f"Failed to lock workstation: {e}"
    elif IS_MACOS:
        subprocess.run(["pmset", "displaysleepnow"])
        return True, "Workstation locked successfully."
    elif IS_LINUX:
        subprocess.run(["xdg-screensaver", "lock"])
        return True, "Workstation locked successfully."
        
    return False, "Unsupported platform."
