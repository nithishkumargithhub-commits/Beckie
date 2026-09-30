import os
import sys

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BASE_DIR not in sys.path:
    sys.path.insert(0, _BASE_DIR)

import logging
import re
from enum import Enum
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from google import genai
import config


logger = logging.getLogger("VoiceAssistant.Classifier")

class IntentEnum(str, Enum):
    OPEN_APP = "open_app"
    CLOSE_APP = "close_app"
    OPEN_FOLDER = "open_folder"
    RUN_CODE = "run_code"
    GENERATE_CODE = "generate_code"
    SYSTEM_OP = "system_op"
    SET_REMINDER = "set_reminder"
    LIST_REMINDERS = "list_reminders"
    CHECK_EMAIL = "check_email"
    SEND_EMAIL = "send_email"
    GOOGLE_TASK_ADD = "google_task_add"
    GOOGLE_TASK_LIST = "google_task_list"
    GOOGLE_TASK_COMPLETE = "google_task_complete"
    INTRODUCE_SELF = "introduce_self"
    SET_VOLUME = "set_volume"
    SET_BRIGHTNESS = "set_brightness"
    TODO_ADD = "todo_add"
    TODO_LIST = "todo_list"
    TODO_COMPLETE = "todo_complete"
    TODO_CLEAR = "todo_clear"
    GET_WEATHER = "get_weather"
    TELL_JOKE = "tell_joke"
    WEB_SEARCH = "web_search"
    SET_PASSWORD = "set_password"
    PULL_DATABASE = "pull_database"
    WINDOW_MANAGE = "window_manage"
    MEDIA_CONTROL = "media_control"
    NOTE_DICTATE = "note_dictate"
    SYSTEM_HEALTH = "system_health"
    PLAY_SONG = "play_song"
    SCREEN_VISION = "screen_vision"
    RUN_MACRO = "run_macro"
    TIMER_ALARM = "timer_alarm"
    CLIPBOARD_OP = "clipboard_op"
    SEARCH_FILE = "search_file"
    SMART_HOME = "smart_home"
    UNKNOWN = "unknown"

class IntentAnalysis(BaseModel):
    intent: IntentEnum = Field(description="The classified intent of the user spoken command.")
    target: str = Field(description="The primary target of the action, such as application name, folder name/path, file path, reminder description, or system operation action.")
    params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Any extra parameters extracted from the command. For set_reminder, this should contain 'datetime' or 'time' in ISO format if specified. For system_op, it can contain the specific action (e.g. 'lock', 'shutdown', 'restart')."
    )

class IntentClassifier:
    def __init__(self):
        # Retrieve API key
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            logger.warning(
                "GEMINI_API_KEY environment variable is not set. "
                "The assistant will fallback to mock intent parsing or fail on API calls."
            )
            self.client = None
        else:
            try:
                # Initialize GenAI Client
                self.client = genai.Client(api_key=self.api_key)
                logger.info("Gemini GenAI client initialized successfully.")
            except Exception as e:
                logger.error(f"Error initializing Gemini GenAI client: {e}")
                self.client = None

    def classify(self, text: str) -> IntentAnalysis:
        """
        Classifies the given command text into a structured IntentAnalysis schema.
        Falls back to basic parsing if the API key is not available.
        """
        text_clean = text.strip()
        if not text_clean:
            return IntentAnalysis(intent=IntentEnum.UNKNOWN, target="")

        logger.info(f"Classifying command: '{text_clean}'")

        if not self.client:
            logger.warning("No Gemini client initialized. Using rule-based fallback.")
            return self._fallback_rule_based_classifier(text_clean)

        try:
            # System prompt/instruction to guide the classification
            prompt = (
                f"You are the intent classifier module of a Windows Personal Voice Assistant named {config.ASSISTANT_NAME}. "
                "Analyze the following transcript of a user speaking a command and map it to the requested schema. "
                "Here are mapping guidelines:\n"
                "- If the user wants to open an application (e.g., chrome, notepad, calculator), intent='open_app', target=application name.\n"
                "- If the user wants to close/exit/terminate/kill an application (e.g., close spotify, exit chrome, close notepad), intent='close_app', target=application name.\n"
                "- If the user wants to open a folder (e.g., downloads, documents, desktop, specific paths), intent='open_folder', target=folder name/path.\n"
                "- If the user wants to introduce the assistant, intent='introduce_self', target=''.\n"
                "- If the user wants to control monitor/screen brightness (increase/decrease/set/check), intent='set_brightness', target=brightness action ('increase', 'decrease', 'set', or 'status'), params={'value': number or null}.\n"
                "- If the user wants to control system volume (increase/decrease/set/mute/unmute/check), intent='set_volume', target=volume action ('increase', 'decrease', 'set', 'mute', 'unmute', or 'status'), params={'value': number or null}.\n"
                "- If the user wants to add a task to their to-do list, intent='todo_add', target=task description.\n"
                "- If the user wants to view/list their to-do list, intent='todo_list', target=''.\n"
                "- If the user wants to complete/finish/check off a task on their to-do list, intent='todo_complete', target=task description or number.\n"
                "- If the user wants to clear/empty their to-do list, intent='todo_clear', target=''.\n"
                "- If the user wants to check the weather, intent='get_weather', target=city name.\n"
                "- If the user wants to hear a joke, intent='tell_joke', target=''.\n"
                "- If the user wants to generate python code, intent='generate_code', target=prompt.\n"
                "- If the user wants to run a python file or code, intent='run_code', target=file path or ''.\n"
                "- If the user wants to lock/shutdown/restart/cancel shutdown, intent='system_op', target=action, params={'action': action}.\n"
                "- If the user wants to set, change, update or disable their voice password, intent='set_password', target=new password phrase if spoken, params={'action': 'set' or 'change' or 'disable'}.\n"
                "- If the user wants to query, pull, search or retrieve their previous conversations, history, notes, or data from the database, intent='pull_database', target=search query.\n"
                "- If the user wants to control open/active windows (minimize, maximize, close), intent='window_manage', target=action ('minimize', 'maximize', 'close').\n"
                "- If the user wants to control media playback (play, pause, next, skip, previous, back), intent='media_control', target=action ('play_pause', 'next', 'prev').\n"
                "- If the user wants to play a song, music, video, or track on Spotify, YouTube, or web (e.g., 'play shape of you on spotify', 'play spotify shape of you', 'play music on youtube', 'search for lofi on youtube', 'find perfect song on web'), intent='play_song', target=song/video query, params={'platform': 'spotify' or 'youtube' or 'web'}.\n"
                "- If the user wants to start or stop dictating voice notes, intent='note_dictate', target=action ('start', 'stop').\n"
                "- If the user wants to check PC health/status, cpu usage, RAM space, disk, or battery, intent='system_health', target='status'.\n"
                "- If the user wants to analyze what is visible on screen, monitor, or screenshot (e.g., 'what is on my screen', 'explain my screen', 'read screen'), intent='screen_vision', target=question or prompt.\n"
                "- If the user wants to activate a voice macro or routine (e.g., 'work mode', 'study mode', 'gaming mode', 'night mode'), intent='run_macro', target=macro name.\n"
                "- If the user wants to set a countdown timer or stopwatch (e.g., 'set timer for 10 minutes', 'start stopwatch', 'stop stopwatch'), intent='timer_alarm', target=duration or action.\n"
                "- If the user wants to analyze, explain, summarize, fix, or read text in clipboard (e.g., 'explain clipboard', 'summarize clipboard', 'fix spelling in clipboard'), intent='clipboard_op', target=action ('explain', 'summarize', 'fix', 'read').\n"
                "- If the user wants to search for a file on their computer (e.g., 'find my resume pdf', 'search file project'), intent='search_file', target=filename/query.\n"
                "- If the user asks a general question, general knowledge, or wants to search the web, intent='web_search', target=query.\n\n"
                f"User command: \"{text_clean}\""
            )

            # Convert Pydantic model to dict schema and remove 'additionalProperties' for compatibility
            schema_dict = IntentAnalysis.model_json_schema()
            
            def clean_schema(d):
                if isinstance(d, dict):
                    d.pop("additionalProperties", None)
                    for v in d.values():
                        clean_schema(v)
                elif isinstance(d, list):
                    for item in d:
                        clean_schema(item)
                        
            clean_schema(schema_dict)

            candidate_models = [config.GEMINI_MODEL]
            for m in ['gemini-3.8-flash', 'gemini-3.1-flash-lite-preview', 'gemini-3.5-flash']:
                if m not in candidate_models:
                    candidate_models.append(m)

            response = None
            last_err = None
            used_model = config.GEMINI_MODEL

            for m_name in candidate_models:
                try:
                    response = self.client.models.generate_content(
                        model=m_name,
                        contents=prompt,
                        config={
                            "response_mime_type": "application/json",
                            "response_schema": schema_dict
                        }
                    )
                    if response and response.text:
                        used_model = m_name
                        break
                except Exception as ex:
                    last_err = ex
                    logger.warning(f"Gemini model {m_name} transient error: {ex}. Trying next candidate...")

            if not response or not response.text:
                raise last_err or RuntimeError("All candidate Gemini models failed to generate content.")

            # Parse JSON response text back into Pydantic model
            result = IntentAnalysis.model_validate_json(response.text)
            logger.info(f"Successfully parsed intent using {used_model}: {result}")
            return result

        except Exception as e:
            logger.error(f"Gemini API classification failed: {e}. Falling back to rule-based classification.")
            return self._fallback_rule_based_classifier(text_clean)

    def _fallback_rule_based_classifier(self, text: str) -> IntentAnalysis:
        """
        Simple keyword-based router fallback if the Gemini API key is missing or calls fail.
        """
        text_lower = text.lower().strip()
        
        # 1. Introduce Self
        if any(p in text_lower for p in ["introduce yourself", "who are you", "what can you do", "introduce self", "your name", "who is jarvis"]):
            return IntentAnalysis(intent=IntentEnum.INTRODUCE_SELF, target="")

        # 2. Voice Password Operations
        if "password" in text_lower or "pass code" in text_lower:
            action = "set"
            if any(p in text_lower for p in ["change", "update", "reset"]):
                action = "change"
            elif any(p in text_lower for p in ["disable", "remove", "delete", "turn off"]):
                action = "disable"
            
            target_pass = ""
            for phrase in ["password to ", "password as "]:
                if phrase in text_lower:
                    parts = text.split(phrase, 1)
                    if len(parts) > 1:
                        target_pass = parts[1].strip()
                        break
            return IntentAnalysis(intent=IntentEnum.SET_PASSWORD, target=target_pass, params={"action": action})

        # 3. Database Retrieval/Pull
        if any(p in text_lower for p in ["pull database", "retrieve history", "retrieve my history", "search history", "search my history", "what did i say", "conversation history"]):
            query = ""
            for phrase in ["search history for ", "search my history for ", "what did i say about ", "retrieve history about ", "retrieve history for ", "pull database for "]:
                if phrase in text_lower:
                    parts = text.split(phrase, 1)
                    if len(parts) > 1:
                        query = parts[1].strip()
                        break
            if not query:
                if "what did i say" in text_lower:
                    parts = text.split("what did i say", 1)
                    query = parts[1].replace("about", "").strip()
                elif "pull database" in text_lower:
                    parts = text.split("pull database", 1)
                    query = parts[1].strip()
            return IntentAnalysis(intent=IntentEnum.PULL_DATABASE, target=query)

        # 4. Smart Home Control
        if any(p in text_lower for p in ["turn on light", "turn off light", "switch on", "switch off", "smart plug", "living room light", "turn on fan", "turn off fan", "turn on ac", "turn off ac"]):
            return IntentAnalysis(intent=IntentEnum.SMART_HOME, target=text)

        # 4.5. Tell Joke
        if any(p in text_lower for p in ["joke", "tell a joke", "tell me a joke", "make me laugh"]):
            return IntentAnalysis(intent=IntentEnum.TELL_JOKE, target="")

        # 5. Weather
        if "weather" in text_lower or "temperature" in text_lower or "forecast" in text_lower:
            city = ""
            for phrase in ["weather in ", "weather for ", "weather of "]:
                if phrase in text_lower:
                    parts = text_lower.split(phrase, 1)
                    if len(parts) > 1:
                        city = parts[1].strip().title()
                        break
            if not city:
                parts = text_lower.split("weather", 1)
                city = parts[1].replace("in", "").replace("for", "").strip().title()
            return IntentAnalysis(intent=IntentEnum.GET_WEATHER, target=city)

        # 6. Window Management (Close, Minimize, Maximize Active Windows)
        if any(p in text_lower for p in ["window", "active screen", "foreground window", "foreground app", "active window", "this app", "this window", "minimize this", "maximize this", "close this"]):
            action = "status"
            if any(p in text_lower for p in ["minimize", "hide", "reduce"]):
                action = "minimize"
            elif any(p in text_lower for p in ["maximize", "zoom", "expand"]):
                action = "maximize"
            elif any(p in text_lower for p in ["close", "exit", "quit"]):
                action = "close"
            return IntentAnalysis(intent=IntentEnum.WINDOW_MANAGE, target=action)

        # 6.5 Play Song / Video (Spotify / YouTube / Web)
        is_song_request = (
            any(kw in text_lower for kw in ["song", "music", "video", "track", "audio", "lofi", "playlist"]) and
            any(verb in text_lower for verb in ["find", "search", "play", "get", "open", "listen"])
        ) or (
            text_lower.startswith("play ") and text_lower != "play"
        ) or "youtube" in text_lower or ("spotify" in text_lower and any(w in text_lower for w in ["play", "search", "find", "listen", "song", "track", "music"]))

        if is_song_request:
            if "spotify" in text_lower:
                platform = "spotify"
            elif any(p in text_lower for p in [" on web", " on the web", " on google", " google ", "in google"]):
                platform = "web"
            else:
                platform = "youtube"
            return IntentAnalysis(intent=IntentEnum.PLAY_SONG, target=text, params={"platform": platform})

        # 7. Media Control
        if any(p in text_lower for p in ["music", "song", "track", "media", "playback", "play", "pause", "skip", "previous", "next", "spotify"]):
            # Check if it's an application open request first (e.g. "open spotify")
            if any(p in text_lower for p in ["open", "launch", "start", "run"]):
                pass # skip media control, let it fall through to open_app
            else:
                action = ""
                if any(p in text_lower for p in ["play", "pause", "toggle", "resume", "stop"]):
                    action = "play_pause"
                elif any(p in text_lower for p in ["next", "skip"]):
                    action = "next"
                elif any(p in text_lower for p in ["previous", "prev", "back"]):
                    action = "prev"
                if action:
                    return IntentAnalysis(intent=IntentEnum.MEDIA_CONTROL, target=action)

        # 8. Dictation Mode
        if "dictating" in text_lower or "dictation" in text_lower or "voice note" in text_lower:
            action = "start"
            if any(p in text_lower for p in ["stop", "end", "finish", "cancel"]):
                action = "stop"
            return IntentAnalysis(intent=IntentEnum.NOTE_DICTATE, target=action)

        # 9. System Health Checks
        if any(p in text_lower for p in ["system health", "cpu usage", "memory usage", "battery level", "battery percent", "disk space", "c drive", "hardware info", "pc status"]):
            return IntentAnalysis(intent=IntentEnum.SYSTEM_HEALTH, target="status")

        # 10. Volume Control
        if any(p in text_lower for p in ["volume", "mute", "unmute", "sound", "audio", "louder", "quieter", "softer", "silent"]):
            if "mute" in text_lower and "unmute" not in text_lower:
                return IntentAnalysis(intent=IntentEnum.SET_VOLUME, target="mute", params={"action": "mute"})
            if "unmute" in text_lower:
                return IntentAnalysis(intent=IntentEnum.SET_VOLUME, target="unmute", params={"action": "unmute"})
            
            if any(p in text_lower for p in ["status", "check", "what is", "current", "how high", "level"]):
                return IntentAnalysis(intent=IntentEnum.SET_VOLUME, target="status", params={"action": "status"})
                
            numbers = re.findall(r"\d+", text_lower)
            val = int(numbers[0]) if numbers else None
            
            if any(p in text_lower for p in ["increase", "raise", "up", "higher", "louder"]):
                return IntentAnalysis(intent=IntentEnum.SET_VOLUME, target="increase", params={"action": "increase", "value": val})
            if any(p in text_lower for p in ["decrease", "lower", "down", "reduce", "quieter", "softer"]):
                return IntentAnalysis(intent=IntentEnum.SET_VOLUME, target="decrease", params={"action": "decrease", "value": val})
            
            if val is not None:
                return IntentAnalysis(intent=IntentEnum.SET_VOLUME, target="set", params={"action": "set", "value": val})
            return IntentAnalysis(intent=IntentEnum.SET_VOLUME, target="status", params={"action": "status"})

        # 11. Brightness Control
        if any(p in text_lower for p in ["brightness", "screen light", "display brightness", "monitor brightness"]):
            if any(p in text_lower for p in ["status", "check", "what is", "current", "level"]):
                return IntentAnalysis(intent=IntentEnum.SET_BRIGHTNESS, target="status", params={"action": "status"})
                
            numbers = re.findall(r"\d+", text_lower)
            val = int(numbers[0]) if numbers else None
            
            if any(p in text_lower for p in ["increase", "raise", "up", "brighter", "higher"]):
                return IntentAnalysis(intent=IntentEnum.SET_BRIGHTNESS, target="increase", params={"action": "increase", "value": val})
            if any(p in text_lower for p in ["decrease", "lower", "down", "dim", "darker", "reduce"]):
                return IntentAnalysis(intent=IntentEnum.SET_BRIGHTNESS, target="decrease", params={"action": "decrease", "value": val})
            
            if val is not None:
                return IntentAnalysis(intent=IntentEnum.SET_BRIGHTNESS, target="set", params={"action": "set", "value": val})
            return IntentAnalysis(intent=IntentEnum.SET_BRIGHTNESS, target="status", params={"action": "status"})

        # 12. To-Do List operations
        if any(p in text_lower for p in ["to do list", "todo list", "task", "checklist", "to-do"]):
            if any(p in text_lower for p in ["clear", "empty", "remove all", "delete all"]):
                return IntentAnalysis(intent=IntentEnum.TODO_CLEAR, target="")
                
            if any(p in text_lower for p in ["complete", "finish", "check off", "mark", "done"]):
                target_desc = ""
                for phrase in ["complete task ", "complete ", "mark task ", "mark ", "finish task ", "finish ", "check off "]:
                    if phrase in text_lower:
                        parts = text.split(phrase, 1)
                        target_desc = parts[1].strip()
                        break
                if not target_desc:
                    target_desc = text_lower.replace("to do list", "").replace("todo list", "").replace("task", "").replace("done", "").replace("complete", "").replace("mark", "").strip()
                return IntentAnalysis(intent=IntentEnum.TODO_COMPLETE, target=target_desc)
                
            if any(p in text_lower for p in ["list", "show", "what is on", "view"]):
                return IntentAnalysis(intent=IntentEnum.TODO_LIST, target="")
                
            target_desc = ""
            for phrase in ["add task ", "add to my to do list ", "add to to do list ", "add to my todo list ", "add to todo list ", "add ", "remind me to "]:
                if phrase in text_lower:
                    parts = text.split(phrase, 1)
                    target_desc = parts[1].strip()
                    break
            if not target_desc:
                target_desc = text_lower.replace("to do list", "").replace("todo list", "").replace("task", "").replace("add", "").strip()
            return IntentAnalysis(intent=IntentEnum.TODO_ADD, target=target_desc)

        # 13. System operations
        if any(p in text_lower for p in ["lock screen", "lock workstation", "lock pc", "lock computer"]):
            return IntentAnalysis(intent=IntentEnum.SYSTEM_OP, target="lock", params={"action": "lock"})
        if any(p in text_lower for p in ["shutdown", "shut down", "turn off pc", "turn off computer", "power off"]):
            return IntentAnalysis(intent=IntentEnum.SYSTEM_OP, target="shutdown", params={"action": "shutdown"})
        if any(p in text_lower for p in ["restart", "reboot"]):
            return IntentAnalysis(intent=IntentEnum.SYSTEM_OP, target="restart", params={"action": "restart"})
        if any(p in text_lower for p in ["cancel shutdown", "abort shutdown", "stop shutdown"]):
            return IntentAnalysis(intent=IntentEnum.SYSTEM_OP, target="cancel shutdown", params={"action": "cancel shutdown"})

        # 14. Code generation / execution
        if any(p in text_lower for p in ["generate code", "generate python", "write python", "create python", "write code"]):
            return IntentAnalysis(intent=IntentEnum.GENERATE_CODE, target=text)
        if any(p in text_lower for p in ["run code", "execute code", "run python", "run file"]):
            file_name = ""
            if "run file" in text_lower:
                parts = text.split("run file", 1)
                file_name = parts[1].strip()
            return IntentAnalysis(intent=IntentEnum.RUN_CODE, target=file_name)

        # 15. Reminders (Calendar)
        if any(p in text_lower for p in ["list reminders", "show reminders", "my reminders", "upcoming reminders", "calendar events", "what are my reminders", "get reminders"]):
            return IntentAnalysis(intent=IntentEnum.LIST_REMINDERS, target="")

        if any(p in text_lower for p in ["set reminder", "set a reminder", "remind me"]):
            target_desc = text
            for phrase in ["set a reminder to ", "set reminder to ", "remind me to "]:
                if phrase in text_lower:
                    parts = text.split(phrase, 1)
                    target_desc = parts[1].strip()
                    break
            return IntentAnalysis(intent=IntentEnum.SET_REMINDER, target=target_desc)

        # 15b. Gmail
        if any(p in text_lower for p in ["check email", "check my email", "unread emails", "check gmail", "read email"]):
            return IntentAnalysis(intent=IntentEnum.CHECK_EMAIL, target="")

        if "send email" in text_lower or "send an email" in text_lower:
            return IntentAnalysis(intent=IntentEnum.SEND_EMAIL, target=text)

        # 15c. Google Tasks
        if any(p in text_lower for p in ["list google tasks", "show google tasks", "my google tasks", "get google tasks"]):
            return IntentAnalysis(intent=IntentEnum.GOOGLE_TASK_LIST, target="")

        if "add task" in text_lower or "add google task" in text_lower or "create task" in text_lower:
            t_target = text
            for phrase in ["add task to ", "add task ", "add google task ", "create task "]:
                if phrase in text_lower:
                    parts = text.split(phrase, 1)
                    t_target = parts[1].strip()
                    break
            return IntentAnalysis(intent=IntentEnum.GOOGLE_TASK_ADD, target=t_target)

        if "complete task" in text_lower or "finish task" in text_lower:
            t_target = text
            for phrase in ["complete task ", "finish task "]:
                if phrase in text_lower:
                    parts = text.split(phrase, 1)
                    t_target = parts[1].strip()
                    break
            return IntentAnalysis(intent=IntentEnum.GOOGLE_TASK_COMPLETE, target=t_target)

        # 16. Open folder
        if "open folder" in text_lower or "explore folder" in text_lower:
            parts = text_lower.split("folder", 1)
            target = parts[1].strip() if len(parts) > 1 else ""
            return IntentAnalysis(intent=IntentEnum.OPEN_FOLDER, target=target)

        # 17. Open folder by mapping (e.g. "open downloads", "open desktop")
        for folder_key in ["downloads", "documents", "desktop", "pictures", "music", "videos", "home"]:
            if folder_key in text_lower and any(p in text_lower for p in ["open", "explore", "show"]):
                return IntentAnalysis(intent=IntentEnum.OPEN_FOLDER, target=folder_key)

        # 17.5 Close app
        if any(verb in text_lower for verb in ["close", "exit", "quit", "terminate", "kill"]):
            if not any(p in text_lower for p in ["window", "this window", "active window", "foreground window"]):
                target = ""
                for verb in ["close", "exit", "quit", "terminate", "kill"]:
                    if verb in text_lower:
                        parts = text_lower.split(verb, 1)
                        target = parts[1].strip() if len(parts) > 1 else ""
                        break
                if target:
                    return IntentAnalysis(intent=IntentEnum.CLOSE_APP, target=target)

        # 18. Open app
        if any(p in text_lower for p in ["open", "launch", "start", "run"]):
            target = ""
            for verb in ["open", "launch", "start", "run"]:
                if verb in text_lower:
                    parts = text_lower.split(verb, 1)
                    target = parts[1].strip() if len(parts) > 1 else ""
                    break
            if target.endswith(" app"):
                target = target[:-4].strip()
            if target:
                return IntentAnalysis(intent=IntentEnum.OPEN_APP, target=target)

        # 19.5 Screen Vision
        if any(p in text_lower for p in ["on my screen", "what's on my screen", "read screen", "explain screen", "screenshot"]):
            return IntentAnalysis(intent=IntentEnum.SCREEN_VISION, target=text)

        # 19.6 Voice Macros
        if any(p in text_lower for p in ["work mode", "study mode", "gaming mode", "game mode", "night mode", "dark mode"]):
            return IntentAnalysis(intent=IntentEnum.RUN_MACRO, target=text_lower)

        # 19.7 Timer & Stopwatch
        if any(p in text_lower for p in ["timer", "stopwatch"]):
            if "stopwatch" in text_lower:
                act = "start"
                if any(p in text_lower for p in ["stop", "pause"]):
                    act = "stop"
                elif any(p in text_lower for p in ["status", "check"]):
                    act = "status"
                elif "reset" in text_lower:
                    act = "reset"
                return IntentAnalysis(intent=IntentEnum.TIMER_ALARM, target=act, params={"type": "stopwatch"})
            return IntentAnalysis(intent=IntentEnum.TIMER_ALARM, target=text)

        # 19.8 Clipboard Assistant
        if "clipboard" in text_lower or "copied text" in text_lower:
            act = "explain"
            if any(p in text_lower for p in ["fix", "correct", "proofread"]):
                act = "fix"
            elif any(p in text_lower for p in ["summarize", "summary"]):
                act = "summarize"
            elif any(p in text_lower for p in ["read", "get", "paste", "show"]):
                act = "read"
            return IntentAnalysis(intent=IntentEnum.CLIPBOARD_OP, target=act)

        # 19.9 File Search
        if any(p in text_lower for p in ["find file", "search file", "locate file", "find my"]):
            return IntentAnalysis(intent=IntentEnum.SEARCH_FILE, target=text)

        # 20. General queries/Web Search (fallback when nothing matches)
        return IntentAnalysis(intent=IntentEnum.WEB_SEARCH, target=text)
