"""
Refactored Structured Intent Classifier for JARVIS Voice Assistant.
"""

import os
import re
from enum import Enum
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from google import genai
from logger import get_logger
from exceptions import IntentClassificationException

logger = get_logger("Jarvis.IntentClassifier")

class IntentEnum(str, Enum):
    GREETING = "greeting"
    OPEN_APP = "open_app"
    CLOSE_APP = "close_app"
    SYSTEM_OP = "system_op"
    SET_VOLUME = "set_volume"
    SET_BRIGHTNESS = "set_brightness"
    GET_WEATHER = "get_weather"
    WEB_SEARCH = "web_search"
    TIME_DATE = "time_date"
    TELL_JOKE = "tell_joke"
    PLAY_SONG = "play_song"
    SET_REMINDER = "set_reminder"
    LIST_REMINDERS = "list_reminders"
    TODO_ADD = "todo_add"
    TODO_LIST = "todo_list"
    TODO_COMPLETE = "todo_complete"
    NOTE_DICTATE = "note_dictate"
    SCREEN_VISION = "screen_vision"
    MEMORY_RAG = "memory_rag"
    CLIPBOARD_OP = "clipboard_op"
    UNKNOWN = "unknown"

class IntentAnalysis(BaseModel):
    intent: IntentEnum = Field(description="The classified intent of the user spoken command.")
    target: str = Field(default="", description="The primary target of the action.")
    params: Dict[str, Any] = Field(default_factory=dict, description="Extracted parameters.")
    confidence: float = Field(default=1.0, description="Classification confidence score.")
    requires_clarification: bool = Field(default=False, description="Whether user clarification is needed.")
    clarification_prompt: str = Field(default="", description="Prompt to ask user for clarification.")

class IntentClassifier:
    """Classifies user spoken commands into structured IntentAnalysis schemas using Gemini 2.0 Flash with rule-based fallback."""

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            logger.warning("GEMINI_API_KEY not set. Operating in rule-based fallback mode.")
            self.client = None
        else:
            try:
                self.client = genai.Client(api_key=self.api_key)
                logger.info("Gemini GenAI client initialized for IntentClassifier.")
            except Exception as e:
                logger.error(f"Error initializing Gemini GenAI client: {e}")
                self.client = None

    def classify(self, text: str) -> IntentAnalysis:
        text_clean = text.strip()
        if not text_clean:
            return IntentAnalysis(intent=IntentEnum.UNKNOWN, target="")

        logger.info(f"Classifying command: '{text_clean}'")

        if not self.client:
            return self._fallback_rule_based_classifier(text_clean)

        try:
            prompt = (
                "You are the intent classifier module of a Windows Voice Assistant named Jarvis. "
                "Classify the following user transcript into one of the allowed intents and extract targets/params.\n"
                f"Transcript: '{text_clean}'"
            )
            response = self.client.models.generate_content(
                model='gemini-2.0-flash',
                contents=prompt,
                config={
                    'response_mime_type': 'application/json',
                    'response_schema': IntentAnalysis,
                }
            )
            analysis = IntentAnalysis.model_validate_json(response.text)
            logger.info(f"Gemini Intent Classification result: {analysis.intent.value} (Target: {analysis.target})")
            return analysis
        except Exception as e:
            logger.warning(f"Gemini API intent classification failed: {e}. Falling back to rule-based classification.")
            return self._fallback_rule_based_classifier(text_clean)

    def _fallback_rule_based_classifier(self, text: str) -> IntentAnalysis:
        text_lower = text.lower()

        # Greetings
        if re.search(r'\b(hello|hi|hey|good morning|good evening|good afternoon)\b', text_lower):
            return IntentAnalysis(intent=IntentEnum.GREETING, target=text)

        # Time & Date
        if re.search(r'\b(time|date|what day|clock|today\'s date)\b', text_lower):
            return IntentAnalysis(intent=IntentEnum.TIME_DATE, target="")

        # Weather
        if "weather" in text_lower or "forecast" in text_lower:
            return IntentAnalysis(intent=IntentEnum.GET_WEATHER, target="")

        # Volume
        if "volume" in text_lower or "mute" in text_lower or "unmute" in text_lower:
            return IntentAnalysis(intent=IntentEnum.SET_VOLUME, target=text_lower)

        # Brightness
        if "brightness" in text_lower:
            return IntentAnalysis(intent=IntentEnum.SET_BRIGHTNESS, target=text_lower)

        # Open App
        match_open = re.search(r'\b(open|launch|start)\s+(.+)', text_lower)
        if match_open:
            return IntentAnalysis(intent=IntentEnum.OPEN_APP, target=match_open.group(2).strip())

        # Close App
        match_close = re.search(r'\b(close|exit|terminate|kill)\s+(.+)', text_lower)
        if match_close:
            return IntentAnalysis(intent=IntentEnum.CLOSE_APP, target=match_close.group(2).strip())

        # Web Search
        if "search" in text_lower or "google" in text_lower or "find" in text_lower:
            query = re.sub(r'^(search for|search|google|find)\s+', '', text_lower).strip()
            return IntentAnalysis(intent=IntentEnum.WEB_SEARCH, target=query)

        # Play Song
        if "play" in text_lower:
            song = re.sub(r'^(play|play song)\s+', '', text_lower).strip()
            return IntentAnalysis(intent=IntentEnum.PLAY_SONG, target=song)

        # Tell Joke
        if "joke" in text_lower:
            return IntentAnalysis(intent=IntentEnum.TELL_JOKE, target="")

        return IntentAnalysis(intent=IntentEnum.WEB_SEARCH, target=text)
