import os
import subprocess
import logging
import sys
import re
try:
    import winreg
except ImportError:
    winreg = None
from typing import Optional, Tuple

logger = logging.getLogger("VoiceAssistant.SystemOps")

# Common applications mapping
APP_MAPPINGS = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "calculate": "calc.exe",
    "calc": "calc.exe",
    "paint": "mspaint.exe",
    "mspaint": "mspaint.exe",
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "edge": "msedge.exe",
    "explorer": "explorer.exe",
    "file explorer": "explorer.exe",
    "task manager": "taskmgr.exe",
    "taskmgr": "taskmgr.exe",
    "cmd": "cmd.exe",
    "command prompt": "cmd.exe",
    "powershell": "powershell.exe",
    "spotify": "spotify:"
}

# Common folders mapping
FOLDER_MAPPINGS = {
    "downloads": os.path.expanduser("~/Downloads"),
    "documents": os.path.expanduser("~/Documents"),
    "desktop": os.path.expanduser("~/Desktop"),
    "pictures": os.path.expanduser("~/Pictures"),
    "music": os.path.expanduser("~/Music"),
    "videos": os.path.expanduser("~/Videos"),
    "home": os.path.expanduser("~")
}

def clean_app_name(app_name: str) -> str:
    """
    Cleans target app name from punctuation and common filler/stop words.
    """
    # 1. Convert to lowercase and strip whitespace
    name = app_name.lower().strip()
    
    # 2. Remove punctuation
    name = re.sub(r'[^\w\s]', '', name)
    
    # 3. Split into words to filter out trailing/leading filler words
    words = name.split()
    
    fillers = {"please", "for", "me", "app", "apk", "application", "program", "software", "exe", "executable", "can", "you", "open", "run", "launch", "start"}
    
    while words and words[0] in fillers:
        words.pop(0)
    while words and words[-1] in fillers:
        words.pop(-1)
        
    return " ".join(words)

def get_app_path_from_registry(app_name: str) -> Optional[str]:
    """
    Looks up executable path in Windows Registry (App Paths).
    """
    if winreg is None:
        return None
    names_to_try = [app_name]
    if not app_name.endswith(".exe"):
        names_to_try.append(f"{app_name}.exe")
        
    for name in names_to_try:
        for hive in [winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE]:
            for subkey in [
                rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{name}",
                rf"SOFTWARE\Wow6432Node\Microsoft\Windows\CurrentVersion\App Paths\{name}"
            ]:
                try:
                    with winreg.OpenKey(hive, subkey) as key:
                        val, _ = winreg.QueryValueEx(key, "")
                        if val:
                            val = os.path.expandvars(val)
                            val = val.strip().strip('"')
                            if os.path.exists(val):
                                return val
                except OSError:
                    continue
    return None

def find_app_shortcut(app_name: str) -> Optional[str]:
    """
    Recursively searches Windows Start Menu for shortcuts matching the app name.
    """
    user_start_menu = os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs")
    system_start_menu = os.path.expandvars(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs")
    
    search_dirs = [user_start_menu, system_start_menu]
    app_name_lower = app_name.lower()
    
    # 1. Exact match of shortcut name
    for sdir in search_dirs:
        if not os.path.exists(sdir):
            continue
        for root, dirs, files in os.walk(sdir):
            for file in files:
                if file.lower().endswith(".lnk"):
                    name_without_ext = file[:-4].lower()
                    if name_without_ext == app_name_lower:
                        return os.path.join(root, file)
                        
    # 2. Substring match
    for sdir in search_dirs:
        if not os.path.exists(sdir):
            continue
        for root, dirs, files in os.walk(sdir):
            for file in files:
                if file.lower().endswith(".lnk"):
                    name_without_ext = file[:-4].lower()
                    if app_name_lower in name_without_ext or name_without_ext in app_name_lower:
                        return os.path.join(root, file)
                        
    return None

def open_app(app_name: str) -> tuple[bool, str]:
    """
    Tries to open the application specified by app_name.
    Returns (success, message).
    """
    cleaned_name = clean_app_name(app_name)
    if not cleaned_name:
        msg = "Please specify which application you want to open."
        logger.warning(msg)
        return False, msg
        
    logger.info(f"Requested to open application: {app_name} (cleaned: {cleaned_name})")
    
    # Resolve target command or path
    target_to_run = None
    resolve_method = None
    
    # 1. Exact match in APP_MAPPINGS
    if cleaned_name in APP_MAPPINGS:
        target_to_run = APP_MAPPINGS[cleaned_name]
        resolve_method = "mapping"
        
    # 2. Substring word boundary match in APP_MAPPINGS keys
    if not target_to_run:
        for key in APP_MAPPINGS:
            if re.search(r'\b' + re.escape(key) + r'\b', cleaned_name):
                target_to_run = APP_MAPPINGS[key]
                resolve_method = "substring mapping"
                break
                
    # 3. Substring key match in APP_MAPPINGS
    if not target_to_run:
        for key in APP_MAPPINGS:
            if cleaned_name in key:
                target_to_run = APP_MAPPINGS[key]
                resolve_method = "partial mapping"
                break
                
    # 4. Registry lookup (App Paths)
    if not target_to_run:
        reg_path = get_app_path_from_registry(cleaned_name)
        if reg_path:
            target_to_run = reg_path
            resolve_method = "registry"
            
    # 5. Start Menu shortcut lookup
    if not target_to_run:
        shortcut_path = find_app_shortcut(cleaned_name)
        if shortcut_path:
            target_to_run = shortcut_path
            resolve_method = "start menu shortcut"
            
    # 6. Fallback: try raw name/cleaned name directly
    if not target_to_run:
        target_to_run = cleaned_name
        resolve_method = "fallback raw name"
        
    logger.info(f"Resolved app '{cleaned_name}' to '{target_to_run}' via {resolve_method}")
    
    try:
        # Use os.startfile on Windows for cleaner and more robust execution.
        # SAPI protocol handler (e.g. "spotify:") and .lnk files work beautifully with os.startfile.
        if hasattr(os, "startfile"):
            os.startfile(target_to_run)
        else:
            subprocess.Popen(target_to_run, shell=True)
            
        msg = f"Opening {cleaned_name}"
        logger.info(msg)
        return True, msg
    except Exception as e:
        # If it failed, try subprocess.Popen as a secondary fallback
        try:
            subprocess.Popen(target_to_run, shell=True)
            msg = f"Opening {cleaned_name}"
            logger.info(f"{msg} via fallback popen")
            return True, msg
        except Exception as e2:
            msg = f"Could not open {cleaned_name}: {e2}"
            logger.error(msg)
            return False, msg

def open_folder(folder_name: str) -> tuple[bool, str]:
    """
    Opens a folder using Windows File Explorer.
    Returns (success, message).
    """
    folder_name_clean = folder_name.strip().rstrip("?.!")
    folder_name_lower = folder_name_clean.lower()
    logger.info(f"Requested to open folder: {folder_name_lower}")
    
    # Check mappings first
    target_path = FOLDER_MAPPINGS.get(folder_name_lower)
    
    # If not in mappings, check if it's an existing directory path
    if not target_path:
        if os.path.exists(folder_name_clean):
            target_path = folder_name_clean
        else:
            msg = f"Folder '{folder_name_clean}' not recognized or does not exist."
            logger.warning(msg)
            return False, msg
            
    try:
        # Normalize path for Windows
        target_path = os.path.abspath(target_path)
        os.startfile(target_path)
        msg = f"Opening folder {os.path.basename(target_path) or target_path}"
        logger.info(msg)
        return True, msg
    except Exception as e:
        msg = f"Could not open folder {folder_name_clean}: {e}"
        logger.error(msg)
        return False, msg

def lock_workstation() -> tuple[bool, str]:
    """
    Locks the Windows workstation.
    """
    logger.info("Locking workstation")
    try:
        subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], check=True, timeout=5.0)
        return True, "Locking workstation"
    except Exception as e:
        msg = f"Failed to lock workstation: {e}"
        logger.error(msg)
        return False, msg

def shutdown_system() -> tuple[bool, str]:
    """
    Initiates a system shutdown.
    For safety, we schedule it with a delay (60 seconds) so it can be canceled.
    """
    logger.info("Initiating system shutdown (scheduled for 60 seconds)")
    try:
        # Schedule shutdown in 60 seconds
        subprocess.run(["shutdown", "/s", "/t", "60"], check=True, timeout=5.0)
        return True, "Shutting down the system in 60 seconds. You can type 'shutdown /a' in CMD to cancel."
    except Exception as e:
        msg = f"Failed to schedule shutdown: {e}"
        logger.error(msg)
        return False, msg

def restart_system() -> tuple[bool, str]:
    """
    Initiates a system restart.
    For safety, scheduled with a delay (60 seconds).
    """
    logger.info("Initiating system restart (scheduled for 60 seconds)")
    try:
        # Schedule restart in 60 seconds
        subprocess.run(["shutdown", "/r", "/t", "60"], check=True, timeout=5.0)
        return True, "Restarting the system in 60 seconds. You can type 'shutdown /a' in CMD to cancel."
    except Exception as e:
        msg = f"Failed to schedule restart: {e}"
        logger.error(msg)
        return False, msg

def abort_shutdown() -> tuple[bool, str]:
    """
    Cancels a pending shutdown or restart.
    """
    logger.info("Aborting pending shutdown/restart")
    try:
        subprocess.run(["shutdown", "/a"], check=True, timeout=5.0)
        return True, "Cancelled pending shutdown or restart."
    except Exception as e:
        msg = f"No pending shutdown to cancel, or failed to cancel: {e}"
        logger.warning(msg)
        return False, msg

def change_volume(action: str, value: int = None) -> tuple[bool, str]:
    """
    Controls master volume.
    action can be: "set", "increase", "decrease", "mute", "unmute", "status"
    """
    try:
        from pycaw.pycaw import AudioUtilities
        devices = AudioUtilities.GetSpeakers()
        volume = devices.EndpointVolume
        
        if action == "status":
            current = int(round(volume.GetMasterVolumeLevelScalar() * 100))
            is_muted = volume.GetMute()
            mute_str = " (muted)" if is_muted else ""
            return True, f"The volume is currently at {current} percent{mute_str}."
            
        elif action == "mute":
            volume.SetMute(1, None)
            return True, "Volume muted."
            
        elif action == "unmute":
            volume.SetMute(0, None)
            return True, "Volume unmuted."
            
        elif action == "set":
            if value is None:
                return False, "Please specify a volume level."
            val_clamped = max(0, min(100, value))
            volume.SetMasterVolumeLevelScalar(val_clamped / 100.0, None)
            if volume.GetMute():
                volume.SetMute(0, None)
            return True, f"Volume set to {val_clamped} percent."
            
        elif action == "increase":
            current = int(round(volume.GetMasterVolumeLevelScalar() * 100))
            step = value if value is not None else 10
            new_val = min(100, current + step)
            volume.SetMasterVolumeLevelScalar(new_val / 100.0, None)
            if volume.GetMute():
                volume.SetMute(0, None)
            return True, f"Volume increased to {new_val} percent."
            
        elif action == "decrease":
            current = int(round(volume.GetMasterVolumeLevelScalar() * 100))
            step = value if value is not None else 10
            new_val = max(0, current - step)
            volume.SetMasterVolumeLevelScalar(new_val / 100.0, None)
            if volume.GetMute():
                volume.SetMute(0, None)
            return True, f"Volume decreased to {new_val} percent."
            
        return False, f"Unknown volume action: {action}"
    except Exception as e:
        logger.error(f"Volume operation failed: {e}")
        return False, f"Failed to perform volume operation: {e}"

def change_brightness(action: str, value: int = None) -> tuple[bool, str]:
    """
    Controls monitor brightness using screen_brightness_control or WMI fallback.
    action can be: "set", "increase", "decrease", "status"
    """
    # 1. Try screen_brightness_control library
    try:
        import screen_brightness_control as sbc
        current_b = sbc.get_brightness()
        current = current_b[0] if isinstance(current_b, list) and current_b else 50
        
        if action == "status":
            return True, f"The screen brightness is currently at {current} percent."
            
        new_val = current
        if action == "set":
            if value is None:
                return False, "Please specify a brightness level."
            new_val = max(0, min(100, value))
        elif action == "increase":
            step = value if value is not None else 10
            new_val = min(100, current + step)
        elif action == "decrease":
            step = value if value is not None else 10
            new_val = max(0, current - step)
        else:
            return False, f"Unknown brightness action: {action}"
            
        sbc.set_brightness(new_val)
        action_words = {"set": "set to", "increase": "increased to", "decrease": "decreased to"}
        return True, f"Screen brightness {action_words.get(action, 'set to')} {new_val} percent."
    except Exception as sbc_err:
        logger.info(f"screen_brightness_control unavailable/failed ({sbc_err}), falling back to PowerShell WMI.")

    # 2. PowerShell WMI fallback
    try:
        get_cmd = "powershell -Command \"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness\""
        res = subprocess.run(get_cmd, shell=True, capture_output=True, text=True, timeout=5.0)
        current = 50
        if res.returncode == 0 and res.stdout.strip():
            try:
                current = int(res.stdout.strip().split()[0])
            except (ValueError, IndexError):
                pass
                
        if action == "status":
            return True, f"The screen brightness is currently at {current} percent."
            
        new_val = current
        if action == "set":
            if value is None:
                return False, "Please specify a brightness level."
            new_val = max(0, min(100, value))
        elif action == "increase":
            step = value if value is not None else 10
            new_val = min(100, current + step)
        elif action == "decrease":
            step = value if value is not None else 10
            new_val = max(0, current - step)
        else:
            return False, f"Unknown brightness action: {action}"
            
        set_cmd = f"powershell -Command \"$objs = Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods; if ($objs) {{ foreach ($o in $objs) {{ $o.WmiSetBrightness(0, {new_val}) }} }}\""
        set_res = subprocess.run(set_cmd, shell=True, capture_output=True, text=True, timeout=5.0)
        if set_res.returncode == 0:
            action_words = {"set": "set to", "increase": "increased to", "decrease": "decreased to"}
            return True, f"Screen brightness {action_words.get(action, 'set to')} {new_val} percent."
        else:
            return False, "Screen brightness adjustment is not supported by your current display hardware or monitor connection."
            
    except Exception as e:
        logger.error(f"Brightness operation failed: {e}")
        return False, "Screen brightness adjustment is not supported on this monitor hardware setup."

def resolve_shortcut_target(lnk_path: str) -> Optional[str]:
    """
    Resolves the target executable path of a Windows shortcut (.lnk file) using PowerShell.
    """
    if not os.path.exists(lnk_path):
        return None
    try:
        # Resolve target path using PowerShell COM interface
        cmd = f'powershell -NoProfile -Command "(New-Object -ComObject WScript.Shell).CreateShortcut(\'{lnk_path}\').TargetPath"'
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5.0)
        if res.returncode == 0:
            target = res.stdout.strip()
            if target:
                return target
    except Exception as e:
        logger.warning(f"Failed to resolve shortcut target for {lnk_path}: {e}")
    return None

def close_app(app_name: str) -> tuple[bool, str]:
    """
    Finds and terminates running processes matching the app_name using psutil.
    Resolves executable names using APP_MAPPINGS, Registry, and Start Menu shortcuts.
    Returns (success, message).
    """
    import psutil
    cleaned_name = clean_app_name(app_name)
    if not cleaned_name:
        return False, "Please specify which application you want to close."
        
    logger.info(f"Requested to close application: {app_name} (cleaned: {cleaned_name})")
    
    # We will gather all possible executable search names
    process_search_names = set()
    
    # 1. Add raw / cleaned names
    process_search_names.add(cleaned_name.lower())
    if not cleaned_name.endswith(".exe"):
        process_search_names.add(f"{cleaned_name}.exe".lower())
        
    # Helper to process target paths / executables
    def add_target(val: str):
        if not val:
            return
        val = val.strip().lower()
        if val.endswith(":"):
            # Protocol handler case: e.g. "spotify:" -> "spotify.exe"
            val_clean = val[:-1]
            process_search_names.add(f"{val_clean}.exe")
        else:
            basename = os.path.basename(val)
            if basename:
                process_search_names.add(basename.lower())
                if not basename.endswith(".exe"):
                    process_search_names.add(f"{basename}.exe".lower())
                    
    # 2. APP_MAPPINGS Exact Match
    if cleaned_name in APP_MAPPINGS:
        add_target(APP_MAPPINGS[cleaned_name])
        
    # 3. APP_MAPPINGS Word Boundary Substring Match (mimicking open_app)
    for key in APP_MAPPINGS:
        if re.search(r'\b' + re.escape(key) + r'\b', cleaned_name):
            add_target(APP_MAPPINGS[key])
            
    # 4. APP_MAPPINGS Substring Match
    for key in APP_MAPPINGS:
        if cleaned_name in key or key in cleaned_name:
            add_target(APP_MAPPINGS[key])
            
    # 5. Registry Lookup (App Paths)
    reg_path = get_app_path_from_registry(cleaned_name)
    if reg_path:
        add_target(reg_path)
        
    # 6. Start Menu Shortcut Lookup and Resolution
    shortcut_path = find_app_shortcut(cleaned_name)
    if shortcut_path:
        target_path = resolve_shortcut_target(shortcut_path)
        if target_path:
            add_target(target_path)
            
    logger.info(f"Resolved process search names for '{cleaned_name}': {list(process_search_names)}")
    
    closed_count = 0
    errors = []
    
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            pname = proc.info['name']
            if pname and pname.lower() in process_search_names:
                proc.terminate()
                closed_count += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
            errors.append(str(e))
            
    if closed_count > 0:
        msg = f"Closed {cleaned_name}."
        logger.info(f"{msg} Terminated {closed_count} processes.")
        return True, msg
    else:
        # Fallback search - what if the process name contains the cleaned app name as a substring?
        # e.g. "Google Chrome" is open, process is "chrome.exe". But we resolved that.
        # What if they said "Steam" but the process name is "Steam.exe"? That is also resolved.
        # But let's try a substring match against all running process names as a last-resort fallback.
        # To avoid terminating unrelated processes (e.g. closing "win" shouldn't kill "wininit.exe"),
        # we check if the cleaned name is a full word boundary in the process name (without extension),
        # or if they match exactly.
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                pname = proc.info['name']
                if pname:
                    pname_lower = pname.lower()
                    name_without_ext = pname_lower.rsplit('.', 1)[0]
                    # Check if cleaned_name matches name_without_ext exactly or as a word boundary
                    if cleaned_name == name_without_ext or re.search(r'\b' + re.escape(cleaned_name) + r'\b', name_without_ext):
                        proc.terminate()
                        closed_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
                errors.append(str(e))
                
        if closed_count > 0:
            msg = f"Closed {cleaned_name}."
            logger.info(f"{msg} Terminated {closed_count} processes via substring fallback.")
            return True, msg
            
        msg = f"Could not find any running processes for {cleaned_name}."
        logger.warning(msg)
        return False, msg

def signout_system() -> tuple[bool, str]:
    """
    Signs out the current Windows user (logoff).
    """
    logger.info("Initiating system sign out")
    try:
        subprocess.run(["shutdown", "/l"], check=True, timeout=5.0)
        return True, "Signing out of your Windows account."
    except Exception as e:
        msg = f"Failed to sign out: {e}"
        logger.error(msg)
        return False, msg

from actions.os_adapter import set_volume, set_brightness, lock_screen as lock_workstation_os

def change_volume(level: float) -> tuple[bool, str]:
    """Sets system output volume using OS adapter."""
    return set_volume(level)

def change_brightness(level: float) -> tuple[bool, str]:
    """Sets screen brightness using OS adapter."""
    return set_brightness(level)
