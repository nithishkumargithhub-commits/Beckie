"""
JARVIS Voice Assistant — Core Modular Entry Point & Orchestrator.
Integrates StateMachine, WakeWord, STT, NLU Intent Classification, ActionExecutor, and TTS.
"""

import sys
import time
import threading
import config
from logger import get_logger

from exceptions import JarvisException
from core.state_machine import StateMachine, StateEnum
from core.intent_classifier import IntentClassifier
from pipeline.wake_word import WakeWordListener
from pipeline.stt import SpeechToText
from pipeline.tts import TextToSpeech
from pipeline.action_executor import ActionExecutor

logger = get_logger("Jarvis.Main")

class JarvisOrchestrator:
    """Central orchestrator wiring pipeline components with the explicit state machine."""

    def __init__(self):
        self.state_machine = StateMachine(initial_state=StateEnum.IDLE)
        self.intent_classifier = IntentClassifier()
        self.stt = SpeechToText()
        self.tts = TextToSpeech()
        self.action_executor = ActionExecutor()
        self.wake_listener = WakeWordListener(on_wake_callback=self._on_wake_word_triggered)

    def start(self):
        """Starts Jarvis voice assistant background pipeline."""
        logger.info("Starting JARVIS Voice Assistant...")
        self.tts.speak("Hey, it's Beckie! How may I assist you?")
        self.wake_listener.start()
        
        # Keep main thread alive
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            logger.info("Stopping JARVIS...")
            self.stop()

    def stop(self):
        """Gracefully shuts down services."""
        self.wake_listener.stop()
        self.tts.stop()
        self.state_machine.transition_to(StateEnum.IDLE, reason="Shutdown requested")
        logger.info("JARVIS stopped.")

    def _on_wake_word_triggered(self):
        """Callback executed when wake word ('hey_beckie') or Ctrl+Alt+J hotkey triggers."""
        if self.state_machine.current_state != StateEnum.IDLE:
            logger.warning(f"Wake trigger ignored — assistant currently in state: {self.state_machine.current_state.value}")
            return

        threading.Thread(target=self._process_voice_interaction, daemon=True).start()

    def _process_voice_interaction(self):
        """Executes full interaction pipeline (LISTENING -> PROCESSING -> EXECUTING -> SPEAKING -> IDLE)."""
        try:
            # 1. State: LISTENING
            if not self.state_machine.transition_to(StateEnum.LISTENING, reason="Wake word / hotkey triggered"):
                return

            self.tts.speak("Listening...", interrupt_current=True)
            transcript = self.stt.record_and_transcribe(duration_sec=4.0)

            if not transcript:
                logger.info("No speech detected.")
                self.tts.speak("I didn't catch that.")
                self.state_machine.transition_to(StateEnum.IDLE, reason="No speech input")
                return

            # 2. State: PROCESSING
            if not self.state_machine.transition_to(StateEnum.PROCESSING, reason="Transcript captured"):
                return

            logger.info(f"Captured User Speech: '{transcript}'")
            analysis = self.intent_classifier.classify(transcript)

            if analysis.requires_clarification:
                self.state_machine.transition_to(StateEnum.CLARIFY, reason="Intent classification requires clarification")
                self.tts.speak(analysis.clarification_prompt or "Could you please clarify your request?")
                self.state_machine.transition_to(StateEnum.IDLE, reason="Clarification prompt delivered")
                return

            # 3. State: EXECUTING
            if not self.state_machine.transition_to(StateEnum.EXECUTING, reason="Intent classified"):
                return

            response_text = self.action_executor.execute(analysis)

            # 4. State: SPEAKING
            if not self.state_machine.transition_to(StateEnum.SPEAKING, reason="Action complete"):
                return

            logger.info(f"Assistant Response: '{response_text}'")
            self.tts.speak(response_text)

            # Return to IDLE
            self.state_machine.transition_to(StateEnum.IDLE, reason="Interaction loop completed")

        except Exception as e:
            logger.error(f"Error during voice interaction loop: {e}", exc_info=True)
            self.state_machine.transition_to(StateEnum.ERROR, reason=str(e))
            self.tts.speak("An error occurred while processing your request.")
            self.state_machine.transition_to(StateEnum.IDLE, reason="Reset after error")


_default_classifier = None
_default_executor = None

def _process_command_inner(command_text: str, stream=None, speak=None):
    """
    Core functional processor for textual or web/API commands.
    Classifies intent and dispatches to ActionExecutor.
    """
    global _default_classifier, _default_executor
    if _default_classifier is None:
        _default_classifier = IntentClassifier()
    if _default_executor is None:
        _default_executor = ActionExecutor()

    logger.info(f"Processing command inner: '{command_text}'")
    analysis = _default_classifier.classify(command_text)
    response_text = _default_executor.execute(analysis)

    if speak and callable(speak):
        speak(response_text)

    return True, analysis.intent.value


def main():
    orchestrator = JarvisOrchestrator()
    orchestrator.start()


if __name__ == "__main__":
    main()

