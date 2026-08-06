import logging
from typing import Tuple
from actions.system_ops import open_app, change_volume, change_brightness

logger = logging.getLogger("VoiceAssistant.Macros")

def run_preset_macro(macro_name: str) -> Tuple[bool, str]:
    """
    Executes a predefined multi-step automation routine.
    Supported macro_name: 'work', 'study', 'gaming', 'night'
    """
    name_clean = macro_name.lower().strip()
    logger.info(f"Executing voice macro routine: '{name_clean}'")

    if "work" in name_clean:
        open_app("chrome")
        open_app("code")
        change_volume("set", 40)
        change_brightness("set", 80)
        msg = "Work Mode activated. Opened Chrome and VS Code, set brightness to 80 percent and volume to 40 percent."
        logger.info(msg)
        return True, msg

    elif "study" in name_clean:
        open_app("notepad")
        change_volume("mute")
        change_brightness("set", 70)
        msg = "Study Mode activated. Opened Notepad, muted volume and set brightness to 70 percent."
        logger.info(msg)
        return True, msg

    elif "gaming" in name_clean or "game" in name_clean:
        open_app("steam")
        change_volume("set", 80)
        change_brightness("set", 100)
        msg = "Gaming Mode activated. Boosted volume to 80 percent and set screen brightness to 100 percent."
        logger.info(msg)
        return True, msg

    elif "night" in name_clean or "dark" in name_clean or "sleep" in name_clean:
        change_brightness("set", 20)
        change_volume("set", 20)
        msg = "Night Mode activated. Dimmed brightness to 20 percent and lowered volume to 20 percent."
        logger.info(msg)
        return True, msg

    else:
        return False, f"Macro routine '{macro_name}' is not recognized. Available macros are: Work Mode, Study Mode, Gaming Mode, and Night Mode."
