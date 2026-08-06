"""
Wake-Word and Hotkey Pipeline Service for JARVIS Voice Assistant.
Listens for openWakeWord model triggers or Ctrl+Alt+J global hotkeys.
"""

import time
import threading
from typing import Callable, Optional
from logger import get_logger

logger = get_logger("Jarvis.Pipeline.WakeWord")

class WakeWordListener:
    """Manages wake word detection loop and hotkey registration."""

    def __init__(self, on_wake_callback: Callable[[], None]):
        self.on_wake_callback = on_wake_callback
        self.is_running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """Starts the wake word background listening loop."""
        if self.is_running:
            return
        self.is_running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        logger.info("WakeWordListener background thread started.")
        self._register_hotkey()

    def stop(self):
        """Stops the wake word listening loop."""
        self.is_running = False
        logger.info("WakeWordListener stopped.")

    def _register_hotkey(self):
        """Registers global Windows hotkey Ctrl+Alt+J using pynput or keyboard if available."""
        try:
            import keyboard
            keyboard.add_hotkey('ctrl+alt+j', self.on_wake_callback)
            logger.info("Registered global hotkey: Ctrl+Alt+J")
        except Exception as e:
            logger.warning(f"Could not register global hotkey via keyboard library: {e}")

    def _listen_loop(self):
        """Background thread loop running openWakeWord on microphone stream."""
        try:
            from openwakeword.model import Model
            import sounddevice as sd
            import numpy as np

            logger.info("Loading openWakeWord models...")
            oww_model = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
            logger.info("openWakeWord model loaded successfully.")

            def audio_callback(indata, frames, time_info, status):
                if not self.is_running:
                    return
                # Convert int16 bytes to int16 numpy array
                audio_data = np.frombuffer(indata, dtype=np.int16)
                oww_model.predict(audio_data)
                for model_name, scores in oww_model.prediction_buffer.items():
                    if scores[-1] > 0.5:
                        logger.info(f"Wake word detected! Score: {scores[-1]}")
                        oww_model.reset()
                        self.on_wake_callback()

            with sd.RawInputStream(samplerate=16000, blocksize=1280, dtype='int16', channels=1, callback=audio_callback):
                while self.is_running:
                    time.sleep(0.1)

        except Exception as e:
            logger.error(f"Error in openWakeWord listening loop: {e}")
