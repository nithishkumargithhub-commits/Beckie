import re
import time
import threading
import logging
from typing import Tuple, Optional
import tkinter as tk
from tkinter import messagebox

logger = logging.getLogger("VoiceAssistant.TimerAlarm")

active_timers = []
stopwatch_start_time: Optional[float] = None

def parse_duration_seconds(text) -> int:
    """
    Parses spoken duration text or numeric seconds into total seconds.
    e.g. '10 minutes', '5 seconds', '1 hour 30 minutes' or 10
    """
    if isinstance(text, (int, float)):
        return int(text)
    text_clean = str(text).lower()
    total_seconds = 0

    hours = re.search(r'(\d+)\s*(?:hour|hr)', text_clean)
    if hours:
        total_seconds += int(hours.group(1)) * 3600

    minutes = re.search(r'(\d+)\s*(?:minute|min)', text_clean)
    if minutes:
        total_seconds += int(minutes.group(1)) * 60

    seconds = re.search(r'(\d+)\s*(?:second|sec)', text_clean)
    if seconds:
        total_seconds += int(seconds.group(1))

    if total_seconds == 0:
        # Fallback regex for pure number (assume minutes)
        digits = re.search(r'(\d+)', text_clean)
        if digits:
            total_seconds = int(digits.group(1)) * 60

    return total_seconds

def _show_timer_popup(timer_label: str):
    """
    Shows a GUI popup window when a countdown timer completes.
    """
    def run_popup():
        try:
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            messagebox.showinfo("Jarvis Timer Alert ⏰", f"⏰ Timer Completed!\n\n{timer_label}")
            root.destroy()
        except Exception as e:
            logger.error(f"Error showing timer popup: {e}")

    threading.Thread(target=run_popup, daemon=True).start()

def _timer_worker(duration_sec: int, label: str, speaker_cb=None):
    """
    Background worker thread waiting for countdown timer completion.
    """
    logger.info(f"Timer started: '{label}' for {duration_sec} seconds.")
    time.sleep(duration_sec)
    logger.info(f"Timer expired: '{label}'")
    _show_timer_popup(label)
    if speaker_cb:
        try:
            speaker_cb(f"Attention please. Your timer for {label} has completed!")
        except Exception:
            pass

def set_countdown_timer(target_text, speaker_cb=None) -> Tuple[bool, str]:
    """
    Sets an asynchronous countdown timer.
    """
    sec = parse_duration_seconds(target_text)
    if sec <= 0:
        return False, "Please specify a valid duration for the timer, such as 5 minutes or 30 seconds."

    label = str(target_text) if isinstance(target_text, str) and target_text.strip() else f"{sec} seconds"
    t = threading.Thread(target=_timer_worker, args=(sec, label, speaker_cb), daemon=True)
    t.start()
    active_timers.append(t)

    min_val = sec // 60
    sec_rem = sec % 60
    time_str = ""
    if min_val > 0:
        time_str += f"{min_val} minute{'s' if min_val > 1 else ''} "
    if sec_rem > 0:
        time_str += f"{sec_rem} second{'s' if sec_rem > 1 else ''}"

    msg = f"Timer set for {time_str.strip()}."
    logger.info(msg)
    return True, msg

def handle_stopwatch(action: str) -> Tuple[bool, str]:
    """
    Handles stopwatch operations: 'start', 'stop', 'check', 'reset'
    """
    global stopwatch_start_time
    act = action.lower().strip()

    if act in ["start", "begin"]:
        stopwatch_start_time = time.time()
        msg = "Stopwatch started."
        logger.info(msg)
        return True, msg

    elif act in ["stop", "pause"]:
        if stopwatch_start_time is None:
            return False, "Stopwatch is not currently running."
        elapsed = time.time() - stopwatch_start_time
        stopwatch_start_time = None
        mins = int(elapsed // 60)
        secs = int(elapsed % 60)
        msg = f"Stopwatch stopped at {mins} minutes and {secs} seconds."
        logger.info(msg)
        return True, msg

    elif act in ["status", "check", "time"]:
        if stopwatch_start_time is None:
            return False, "Stopwatch is not currently running."
        elapsed = time.time() - stopwatch_start_time
        mins = int(elapsed // 60)
        secs = int(elapsed % 60)
        msg = f"Stopwatch elapsed time is {mins} minutes and {secs} seconds."
        return True, msg

    elif act == "reset":
        stopwatch_start_time = None
        msg = "Stopwatch reset."
        return True, msg

    else:
        return False, "Unknown stopwatch command. Say 'start stopwatch' or 'stop stopwatch'."
