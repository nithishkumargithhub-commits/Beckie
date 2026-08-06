import config

def get_introduction() -> str:
    """
    Returns a static string introducing the assistant and listing its capabilities.
    """
    intro_text = (
        f"Hello! I am {config.ASSISTANT_NAME}, version {config.VERSION}, your personal voice assistant. "
        "Here are my current capabilities: "
        "1. Open applications, by saying 'open app' followed by the application name, for example, 'open notepad' or 'open chrome'. "
        "2. Open folders, by saying 'open folder' followed by the folder name, like 'open folder downloads' or 'open folder documents'. "
        "3. System control operations, such as locking your screen with 'lock workstation', or shutting down and restarting with 'shutdown' or 'restart'. Destructive operations require confirmation. "
        "4. System adjustments, like changing volume ('set volume to 50', 'mute') or screen brightness ('increase brightness', 'decrease brightness'). "
        "5. Local to-do list management, including 'add task', 'list tasks', 'complete task 1', or 'clear to-do list'. "
        "6. Weather forecasting, such as 'weather in Seattle'. "
        "7. Tell jokes when you ask for one. "
        "8. Web search and general knowledge answering using Google Search. "
        "9. Introduce myself, by asking 'introduce yourself' or 'who are you'."
    )
    return intro_text
