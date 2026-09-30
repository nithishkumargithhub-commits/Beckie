"""Avatar Event Publisher.

Bridges local BECKIE / JARVIS speech, voice, privacy, and LLM lifecycle events
to the frontend 3D AvatarController via localhost WebSocket and broadcast callbacks.
Zero remote networks: all messages circulate strictly on localhost (127.0.0.1).
"""

import logging
from typing import Dict, Any, Callable, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger("Avatar.EventPublisher")


class AvatarEventPublisher:
    """Manages event callbacks and publishes avatar-related state changes."""

    def __init__(self):
        self._listeners: List[Callable[[Dict[str, Any]], None]] = []

    def register_listener(self, listener: Callable[[Dict[str, Any]], None]) -> None:
        if listener not in self._listeners:
            self._listeners.append(listener)

    def unregister_listener(self, listener: Callable[[Dict[str, Any]], None]) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    def publish_event(self, event_type: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Dispatch a typed event with ISO timestamp to all registered listeners."""
        payload = {
            "type": "avatar_event",
            "event": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data or {},
        }

        for listener in list(self._listeners):
            try:
                listener(payload)
            except Exception as e:
                logger.warning(f"[AvatarEventPublisher] Error notifying listener: {e}")

        return payload

    # Convenience triggers for core assistant states
    def on_voice_listening_started(self) -> Dict[str, Any]:
        return self.publish_event("voice.listening.started", {"state": "LISTENING"})

    def on_voice_listening_stopped(self) -> Dict[str, Any]:
        return self.publish_event("voice.listening.stopped", {"state": "IDLE"})

    def on_llm_generation_started(self, prompt_summary: Optional[str] = None) -> Dict[str, Any]:
        return self.publish_event("llm.generation.started", {"state": "THINKING", "prompt": prompt_summary})

    def on_llm_generation_completed(self) -> Dict[str, Any]:
        return self.publish_event("llm.generation.completed", {"state": "IDLE"})

    def on_tts_started(self, text_snippet: str = "", audio_viseme_envelope: Optional[List[float]] = None) -> Dict[str, Any]:
        return self.publish_event("tts.started", {
            "state": "SPEAKING",
            "text": text_snippet,
            "voice": "LOCAL PIPER",
            "envelope": audio_viseme_envelope or [],
        })

    def on_tts_completed(self) -> Dict[str, Any]:
        return self.publish_event("tts.completed", {"state": "IDLE"})

    def on_privacy_mic_paused(self, paused: bool) -> Dict[str, Any]:
        return self.publish_event("privacy.mic.paused", {"micPaused": paused, "state": "PAUSED" if paused else "IDLE"})

    def on_emergency_paused(self, paused: bool) -> Dict[str, Any]:
        return self.publish_event("assistant.emergency_paused", {"emergencyPaused": paused, "state": "PAUSED" if paused else "IDLE"})


_singleton_publisher: Optional[AvatarEventPublisher] = None


def get_avatar_event_publisher() -> AvatarEventPublisher:
    global _singleton_publisher
    if _singleton_publisher is None:
        _singleton_publisher = AvatarEventPublisher()
    return _singleton_publisher
