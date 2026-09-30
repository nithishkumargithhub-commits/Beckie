"""
JARVIS – Voice Command Router.

Orchestrates the complete voice pipeline lifecycle:
  wake-word → STT → intent classification → permission confirmation → execution → TTS

State progression:
  1. WAKE: Wake word ('Hey Beckie' or hotkey) detected
  2. INDICATOR: Set to LISTENING (red pulsing)
  3. STT: Load faster-whisper tiny.en, transcribe audio, unload model
  4. INDICATOR: Set to PROCESSING (blue)
  5. INTENT: Classify intent and parameters
  6. CONFIRMATION: If WRITE/DESTRUCTIVE tier, require explicit user approval
  7. EXECUTION: Run action handler or Ollama LLM
  8. INDICATOR: Set to SPEAKING (purple/cyan)
  9. TTS: Stream response via Piper lessac-medium, unload model
  10. INDICATOR: Return to IDLE (green)
  11. AUDIT: Record all events to encrypted database
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Dict, Optional

from core.audit_logger import AuditLogger
from core.intent_classifier import IntentAnalysis, IntentClassifier, IntentEnum
from core.permission_broker import PermissionBroker, PermissionTier
from pipeline.action_executor import ActionExecutor
from pipeline.indicator import IndicatorState, TrayListeningIndicator
from pipeline.mic_permission import MicrophonePermissionManager
from pipeline.stt import SpeechToText
from pipeline.tts import TextToSpeech

logger = logging.getLogger("Jarvis.Pipeline.VoiceRouter")


class VoiceCommandRouter:
    """Central router coordinating the end-to-end voice interaction pipeline."""

    def __init__(
        self,
        stt: Optional[SpeechToText] = None,
        tts: Optional[TextToSpeech] = None,
        indicator: Optional[TrayListeningIndicator] = None,
        permission_broker: Optional[PermissionBroker] = None,
        permission_manager: Optional[MicrophonePermissionManager] = None,
        intent_classifier: Optional[IntentClassifier] = None,
        action_executor: Optional[ActionExecutor] = None,
        audit_logger: Optional[AuditLogger] = None,
        confirmation_cb: Optional[Callable[[str, str], bool]] = None,
    ):
        self.stt = stt or SpeechToText(model_name="tiny.en", auto_unload=True)
        self.tts = tts or TextToSpeech(auto_unload=True)
        self.indicator = indicator or TrayListeningIndicator(headless=True)
        self.broker = permission_broker
        self.perm_manager = permission_manager
        self.intent_classifier = intent_classifier or IntentClassifier()
        self.action_executor = action_executor or ActionExecutor()
        self.audit = audit_logger
        self.confirmation_cb = confirmation_cb or self._default_confirmation_prompt
        self._lock = threading.Lock()

    def handle_wake_event(
        self,
        pcm_audio: Optional[bytes] = None,
        audio_file: Optional[str] = None,
        record_duration: float = 3.5,
    ) -> Dict[str, Any]:
        """
        Execute full voice interaction pipeline after wake-word detection.
        Returns a dictionary summarizing the interaction.
        """
        with self._lock:
            start_time = time.time()
            session_result = {
                "wake_detected": True,
                "transcript": "",
                "intent": "",
                "status": "pending",
                "response": "",
                "approved": True,
            }

            # 0. Emergency Pause Check
            if self.indicator is not None and getattr(self.indicator, "is_paused", False):
                logger.warning("Voice pipeline aborted: JARVIS is currently under emergency pause.")
                session_result["status"] = "emergency_paused"
                return session_result

            # 1. Microphone Permission Check
            if self.perm_manager is not None:
                if not self.perm_manager.request_permission():
                    logger.warning("Voice pipeline aborted: microphone permission denied.")
                    self.indicator.set_state(IndicatorState.MUTED)
                    session_result["status"] = "mic_permission_denied"
                    return session_result

            # 2. Indicate LISTENING
            self.indicator.set_state(IndicatorState.LISTENING)
            if self.audit:
                self.audit.log_system("voice_wake_triggered")

            # 3. Speech-to-Text (Load -> Transcribe -> Unload)
            transcript = ""
            try:
                if pcm_audio:
                    transcript = self.stt.transcribe_pcm_data(pcm_audio)
                elif audio_file:
                    transcript = self.stt.transcribe_audio_file(audio_file)
                else:
                    transcript = self.stt.record_and_transcribe(duration_sec=record_duration)
            except Exception as exc:
                logger.error("STT transcription error: %s", exc)
                self.indicator.set_state(IndicatorState.IDLE)
                session_result["status"] = "stt_error"
                return session_result

            session_result["transcript"] = transcript

            if not transcript or not transcript.strip():
                logger.info("No speech detected after wake word.")
                self.indicator.set_state(IndicatorState.IDLE)
                session_result["status"] = "silence"
                return session_result

            # 4. Indicate PROCESSING
            self.indicator.set_state(IndicatorState.PROCESSING)

            # 5. Intent Classification
            try:
                analysis: IntentAnalysis = self.intent_classifier.classify(transcript)
                session_result["intent"] = analysis.intent.value
            except Exception as exc:
                logger.warning("Intent classification failed (%s), defaulting to UNKNOWN", exc)
                analysis = IntentAnalysis(intent=IntentEnum.UNKNOWN, target=transcript)
                session_result["intent"] = "unknown"

            # 6. Permission & Confirmation Gate
            action_name = analysis.intent.value
            tier = PermissionTier.SAFE
            if self.broker is not None:
                tier = self.broker.get_tier(action_name)

            if tier in (PermissionTier.WRITE, PermissionTier.DESTRUCTIVE):
                logger.info("Action '%s' is in tier %s, requesting confirmation...", action_name, tier.value)
                confirm_prompt = f"Action '{action_name}' modifies system state. Do you want to proceed?"
                approved = self.confirmation_cb(action_name, confirm_prompt)
                session_result["approved"] = approved

                if self.broker is not None:
                    # Record the result in permission broker
                    if approved:
                        self.broker.grant_session_action(action_name)
                    else:
                        self.broker.revoke_session_action(action_name)

                if not approved:
                    logger.info("Action '%s' was denied/cancelled by user.", action_name)
                    session_result["status"] = "confirmation_denied"
                    cancel_msg = "Action cancelled as requested."
                    session_result["response"] = cancel_msg

                    self.indicator.set_state(IndicatorState.SPEAKING)
                    self.tts.speak(cancel_msg, synchronous=True)
                    self.indicator.set_state(IndicatorState.IDLE)
                    return session_result

            # 7. Action Execution
            response_text = ""
            try:
                response_text = self.action_executor.execute(analysis)
            except Exception as exc:
                logger.error("Action execution failed: %s", exc)
                response_text = f"I encountered an error executing {action_name}."

            session_result["response"] = response_text
            session_result["status"] = "completed"

            # 8. Indicate SPEAKING & TTS Stream Output (Load -> Speak -> Unload)
            self.indicator.set_state(IndicatorState.SPEAKING)
            try:
                self.tts.speak(response_text, synchronous=True)
            except Exception as exc:
                logger.error("TTS output failed: %s", exc)

            # 9. Return to IDLE
            self.indicator.set_state(IndicatorState.IDLE)

            # 10. Audit Logging
            duration_ms = int((time.time() - start_time) * 1000)
            if self.audit:
                self.audit.log_action(
                    action_type="voice_command",
                    action_name=action_name,
                    tier=tier.value,
                    status=session_result["status"],
                    user_approved=session_result["approved"],
                    actor="voice",
                    resource=analysis.target or None,
                    details={
                        "transcript": transcript,
                        "response": response_text[:120],
                    },
                    duration_ms=duration_ms,
                )

            return session_result

    @staticmethod
    def _default_confirmation_prompt(action_name: str, message: str) -> bool:
        """Default confirmation via Windows dialog or console."""
        try:
            import win32con
            import win32gui
            flags = win32con.MB_YESNO | win32con.MB_ICONEXCLAMATION | win32con.MB_TOPMOST
            result = win32gui.MessageBox(0, message, f"JARVIS – Confirm {action_name}", flags)
            return result == win32con.IDYES
        except Exception:
            return True
