"""
Action Executor Pipeline Service for JARVIS Voice Assistant.
Routes classified IntentAnalysis objects to specific action functions via a dispatch table.
"""

from typing import Dict, Any, Callable
from core.intent_classifier import IntentAnalysis, IntentEnum
from logger import get_logger
from exceptions import ActionExecutionException

logger = get_logger("Jarvis.Pipeline.ActionExecutor")

class ActionExecutor:
    """Dispatches intent analysis results to stateless action handlers."""

    def __init__(self):
        self._dispatch_table: Dict[IntentEnum, Callable[[IntentAnalysis], str]] = {
            IntentEnum.GREETING: self._handle_greeting,
            IntentEnum.TIME_DATE: self._handle_time_date,
            IntentEnum.GET_WEATHER: self._handle_weather,
            IntentEnum.SET_VOLUME: self._handle_volume,
            IntentEnum.SET_BRIGHTNESS: self._handle_brightness,
            IntentEnum.OPEN_APP: self._handle_open_app,
            IntentEnum.CLOSE_APP: self._handle_close_app,
            IntentEnum.WEB_SEARCH: self._handle_web_search,
            IntentEnum.PLAY_SONG: self._handle_play_song,
            IntentEnum.TELL_JOKE: self._handle_tell_joke,
            IntentEnum.SYSTEM_OP: self._handle_system_op,
        }

    def execute(self, analysis: IntentAnalysis) -> str:
        """Executes the action corresponding to the classified intent and returns a verbal response."""
        handler = self._dispatch_table.get(analysis.intent)
        if not handler:
            logger.warning(f"No specific handler registered for intent '{analysis.intent.value}'. Defaulting to web search.")
            return self._handle_web_search(analysis)

        try:
            logger.info(f"Executing action handler for intent '{analysis.intent.value}'")
            return handler(analysis)
        except Exception as e:
            logger.error(f"Error executing action for intent '{analysis.intent.value}': {e}")
            raise ActionExecutionException(f"Failed to execute {analysis.intent.value}: {e}")

    # Action Handlers

    def _handle_greeting(self, analysis: IntentAnalysis) -> str:
        from datetime import datetime
        hour = datetime.now().hour
        if hour < 12:
            greeting = "Good morning"
        elif hour < 18:
            greeting = "Good afternoon"
        else:
            greeting = "Good evening"
        return f"{greeting}! How can I assist you today?"

    def _handle_time_date(self, analysis: IntentAnalysis) -> str:
        from datetime import datetime
        now = datetime.now()
        time_str = now.strftime("%I:%M %p")
        date_str = now.strftime("%A, %B %d, %Y")
        return f"It is currently {time_str} on {date_str}."

    def _handle_weather(self, analysis: IntentAnalysis) -> str:
        try:
            from actions.weather import get_weather_forecast
            return get_weather_forecast(analysis.target or "Coimbatore")
        except Exception as e:
            logger.warning(f"Weather service unavailable: {e}")
            return "I am currently unable to fetch the weather forecast. Please check your internet connection."

    def _handle_volume(self, analysis: IntentAnalysis) -> str:
        try:
            from actions.volume import volume_controller
            target = (analysis.target or "").lower()
            if "mute" in target and "unmute" not in target:
                _, msg = volume_controller.mute(force_unconfirmed=True)
                return msg
            elif "unmute" in target:
                _, msg = volume_controller.unmute(force_unconfirmed=True)
                return msg
            elif "full" in target or "max" in target:
                _, msg = volume_controller.set_volume(100, force_unconfirmed=True)
                return msg
            else:
                _, msg = volume_controller.set_volume(50, force_unconfirmed=True)
                return msg
        except Exception as e:
            return "Adjusted volume settings."

    def _handle_brightness(self, analysis: IntentAnalysis) -> str:
        try:
            from actions.brightness import brightness_controller
            _, msg = brightness_controller.set_brightness(70, force_unconfirmed=True)
            return msg
        except Exception as e:
            return "Could not adjust screen brightness."

    def _handle_open_app(self, analysis: IntentAnalysis) -> str:
        app_name = analysis.target or "notepad"
        try:
            from actions.file_ops import file_ops
            _, msg = file_ops.launch_approved_app(app_name, force_unconfirmed=True)
            return msg
        except Exception as e:
            return f"Could not launch {app_name}."

    def _handle_close_app(self, analysis: IntentAnalysis) -> str:
        app_name = analysis.target or "application"
        try:
            from actions.app_launcher import close_app
            return close_app(app_name)
        except Exception as e:
            return f"Could not close {app_name}."

    def _handle_web_search(self, analysis: IntentAnalysis) -> str:
        query = analysis.target or "Python"
        try:
            import webbrowser
            import urllib.parse
            url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
            webbrowser.open(url)
            return f"Searching Google for {query}."
        except Exception as e:
            return f"I couldn't complete the web search."

    def _handle_play_song(self, analysis: IntentAnalysis) -> str:
        song = analysis.target or "music"
        try:
            import webbrowser
            import urllib.parse
            url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(song)}"
            webbrowser.open(url)
            return f"Playing {song} on YouTube."
        except Exception as e:
            return f"Could not search YouTube for {song}."

    def _handle_tell_joke(self, analysis: IntentAnalysis) -> str:
        try:
            from actions.jokes import get_random_joke
            return get_random_joke()
        except Exception:
            return "Why don't scientists trust atoms? Because they make up everything!"

    def _handle_system_op(self, analysis: IntentAnalysis) -> str:
        op = analysis.target.lower()
        if "lock" in op:
            import os
            os.system("rundll32.exe user32.dll,LockWorkStation")
            return "Workstation locked."
        return "System operation requested."
