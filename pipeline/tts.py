"""
JARVIS – Text-to-Speech (TTS) Pipeline Service with Piper Streaming.

Requirements:
  - Piper TTS 'en_US-lessac-medium' with streaming audio output
  - Load Piper only during active speaking (unload after)
  - Piper voice latency < 500ms
  - Fallback to Edge TTS and pyttsx3
"""

from __future__ import annotations

import contextlib
import gc
import logging
import os
import queue
import tempfile
import threading
import time
from pathlib import Path
from typing import Generator, Iterator, Optional

import numpy as np

logger = logging.getLogger("Jarvis.Pipeline.TTS")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PIPER_MODEL = PROJECT_ROOT / "en_US-lessac-medium.onnx"


class TextToSpeech:
    """
    Managed Text-to-Speech with Piper Neural TTS en_US-lessac-medium.
    Streams audio chunks to speakers with <500ms first-chunk latency.
    Unloads the model immediately after speaking completes.
    """

    def __init__(
        self,
        piper_model_path: Path = DEFAULT_PIPER_MODEL,
        auto_unload: bool = True,
    ):
        self.piper_model_path = Path(piper_model_path)
        self.auto_unload = auto_unload
        self._piper_voice = None
        self._speech_queue = queue.Queue()
        self._is_speaking = False
        self._stop_event = threading.Event()
        self._last_latency_ms: float = 0.0

        self._worker_thread = threading.Thread(target=self._process_queue, daemon=True)
        self._worker_thread.start()

    def load_voice(self):
        """Load Piper voice on demand."""
        if self._piper_voice is None:
            if not self.piper_model_path.exists():
                logger.warning("Piper model file not found at %s", self.piper_model_path)
                return None
            try:
                from piper.voice import PiperVoice
                logger.info("Loading Piper voice model (%s)...", self.piper_model_path.name)
                self._piper_voice = PiperVoice.load(str(self.piper_model_path))
                logger.info("Piper voice model loaded successfully.")
            except Exception as exc:
                logger.error("Failed to load Piper voice: %s", exc)
                self._piper_voice = None
        return self._piper_voice

    def unload_voice(self) -> None:
        """Unload Piper voice model and run garbage collection."""
        if self._piper_voice is not None:
            del self._piper_voice
            self._piper_voice = None
            gc.collect()
            logger.info("Piper voice model unloaded from memory.")

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    @property
    def last_latency_ms(self) -> float:
        return self._last_latency_ms

    def speak(self, text: str, interrupt_current: bool = False, synchronous: bool = False):
        """Enqueue speech or speak synchronously."""
        if not text or not text.strip():
            return

        if interrupt_current:
            self.stop()

        if synchronous:
            self._speak_stream(text.strip())
        else:
            self._speech_queue.put(text.strip())

    def stop(self):
        """Barge-in: stops audio playback and clears queue."""
        self._stop_event.set()
        with self._speech_queue.mutex:
            self._speech_queue.queue.clear()
        self._is_speaking = False
        logger.info("TTS playback interrupted.")

    def stream_audio_chunks(self, text: str) -> Iterator[np.ndarray]:
        """Synthesize and yield audio chunks with low latency."""
        voice = self.load_voice()
        if voice is None:
            return

        t0 = time.perf_counter()
        first_chunk = True

        try:
            chunks = voice.synthesize(text)
            for chunk in chunks:
                if self._stop_event.is_set():
                    break
                if first_chunk:
                    self._last_latency_ms = (time.perf_counter() - t0) * 1000.0
                    logger.info("Piper first-chunk latency: %.2fms (Requirement: < 500ms)", self._last_latency_ms)
                    first_chunk = False
                yield chunk.audio_float_array
        finally:
            if self.auto_unload:
                self.unload_voice()

    def _process_queue(self):
        while True:
            try:
                text = self._speech_queue.get()
                if text is None:
                    break
                self._stop_event.clear()
                self._is_speaking = True
                self._speak_stream(text)
                self._is_speaking = False
                self._speech_queue.task_done()
            except Exception as exc:
                logger.error("Error in TTS queue worker: %s", exc)
                self._is_speaking = False

    def _speak_stream(self, text: str):
        voice = self.load_voice()
        if voice is not None:
            try:
                import sounddevice as sd

                t0 = time.perf_counter()
                first = True
                sample_rate = voice.config.sample_rate

                with sd.OutputStream(samplerate=sample_rate, channels=1, dtype="float32") as stream:
                    for chunk in voice.synthesize(text):
                        if self._stop_event.is_set():
                            break
                        if first:
                            self._last_latency_ms = (time.perf_counter() - t0) * 1000.0
                            logger.info("Piper TTS audio stream started in %.2fms", self._last_latency_ms)
                            first = False
                        stream.write(chunk.audio_float_array)

                return
            except Exception as exc:
                logger.warning("Piper streaming playback failed (%s), falling back...", exc)
            finally:
                if self.auto_unload:
                    self.unload_voice()

        # Fallback to offline pyttsx3
        self._fallback_pyttsx3(text)

    def _fallback_pyttsx3(self, text: str):
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()
        except Exception as exc:
            logger.error("pyttsx3 fallback failed: %s", exc)
