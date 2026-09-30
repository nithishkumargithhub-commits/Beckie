"""
JARVIS – Wake-Word and Hotkey Pipeline Service.

Requirements:
  - openWakeWord integration for "Hey Beckie" detection (ONNX model)
  - Windows hotkey (Ctrl+Alt+J) trigger support
  - Permission check before opening microphone
"""

from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import Callable, Optional

import numpy as np

logger = logging.getLogger("Jarvis.Pipeline.WakeWord")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BECKIE_MODEL = PROJECT_ROOT / "models" / "hey_beckie.onnx"


class WakeWordListener:
    """Manages 'Hey Beckie' wake word detection loop and hotkey registration."""

    def __init__(
        self,
        on_wake_callback: Callable[[], None],
        model_path: Optional[Path] = None,
        threshold: float = 0.5,
        permission_manager=None,
    ):
        self.on_wake_callback = on_wake_callback
        self.model_path = Path(model_path) if model_path else DEFAULT_BECKIE_MODEL
        self.threshold = threshold
        self.permission_manager = permission_manager
        self.is_running = False
        self.is_paused = False
        self._thread: Optional[threading.Thread] = None
        self._oww_model = None

    def pause(self) -> None:
        """Pause audio listening and wake word processing."""
        self.is_paused = True
        logger.info("WakeWordListener paused.")

    def resume(self) -> None:
        """Resume audio listening and wake word processing."""
        self.is_paused = False
        logger.info("WakeWordListener resumed.")

    def load_model(self):
        """Load openWakeWord model for 'Hey Beckie'."""
        if self._oww_model is None:
            from openwakeword.model import Model

            models_to_load = []
            if self.model_path.exists():
                models_to_load.append(str(self.model_path))
                logger.info("Loading custom wake word model: %s", self.model_path.name)
            else:
                models_to_load.append("hey_jarvis")
                logger.info("Custom model not found, falling back to built-in 'hey_jarvis'")

            self._oww_model = Model(wakeword_models=models_to_load, inference_framework="onnx")
            logger.info("openWakeWord model loaded: %s", list(self._oww_model.models.keys()))
        return self._oww_model

    def start(self) -> None:
        """Starts the wake word background listening loop."""
        if self.is_running:
            return

        if self.permission_manager is not None:
            if not self.permission_manager.request_permission():
                logger.warning("Microphone permission denied. WakeWordListener will not start.")
                return

        self.is_running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        logger.info("WakeWordListener background thread started.")
        self._register_hotkey()

    def stop(self) -> None:
        """Stops the wake word listening loop."""
        self.is_running = False
        logger.info("WakeWordListener stopped.")

    def process_audio_chunk(self, audio_data: np.ndarray) -> bool:
        """Process a single 1280-sample audio chunk and return True if wake word detected."""
        model = self.load_model()
        model.predict(audio_data)

        for model_name, scores in model.prediction_buffer.items():
            if scores and scores[-1] >= self.threshold:
                logger.info("Wake word detected on '%s'! Score: %.3f", model_name, scores[-1])
                model.reset()
                return True
        return False

    def _register_hotkey(self) -> None:
        """Registers global Windows hotkey Ctrl+Alt+J."""
        try:
            import keyboard
            keyboard.add_hotkey("ctrl+alt+j", self.on_wake_callback)
            logger.info("Registered global hotkey: Ctrl+Alt+J")
        except Exception as exc:
            logger.warning("Could not register hotkey via keyboard library: %s", exc)

    def _listen_loop(self) -> None:
        """Background thread loop running openWakeWord on microphone stream."""
        try:
            import sounddevice as sd
            model = self.load_model()

            def audio_callback(indata, frames, time_info, status):
                if not self.is_running or self.is_paused:
                    return
                audio_data = np.frombuffer(indata, dtype=np.int16)
                if self.process_audio_chunk(audio_data):
                    if not self.is_paused:
                        self.on_wake_callback()

            # 16kHz, 1280 blocksize = 80ms chunk
            with sd.RawInputStream(
                samplerate=16000,
                blocksize=1280,
                dtype="int16",
                channels=1,
                callback=audio_callback,
            ):
                while self.is_running:
                    time.sleep(0.1)

        except Exception as exc:
            logger.error("Error in openWakeWord listening loop: %s", exc)
