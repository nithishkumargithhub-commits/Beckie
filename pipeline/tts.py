"""
Text-to-Speech (TTS) Pipeline Service for JARVIS Voice Assistant.
Uses Microsoft Edge Neural TTS with offline pyttsx3 fallback and threaded queue with barge-in support.
"""

import os
import queue
import threading
import tempfile
import asyncio
from typing import Optional
from logger import get_logger
from exceptions import TTSException

logger = get_logger("Jarvis.Pipeline.TTS")

class TextToSpeech:
    """Manages audio generation and speech output queue."""

    def __init__(self, voice: str = "en-US-GuyNeural"):
        self.voice = voice
        self._speech_queue = queue.Queue()
        self._is_speaking = False
        self._stop_event = threading.Event()
        self._worker_thread = threading.Thread(target=self._process_queue, daemon=True)
        self._worker_thread.start()

    def speak(self, text: str, interrupt_current: bool = False):
        """Enqueues text to be spoken. If interrupt_current is True, clears existing queue."""
        if not text or not text.strip():
            return

        if interrupt_current:
            self.stop()

        self._speech_queue.put(text.strip())
        logger.info(f"Queued TTS message: '{text.strip()}'")

    def stop(self):
        """Interrupts and stops any currently playing or queued audio (barge-in)."""
        self._stop_event.set()
        with self._speech_queue.mutex:
            self._speech_queue.queue.clear()
        self._is_speaking = False
        logger.info("TTS output stopped / interrupted.")

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    def _process_queue(self):
        while True:
            try:
                text = self._speech_queue.get()
                if text is None:
                    break
                self._stop_event.clear()
                self._is_speaking = True
                self._speak_text(text)
                self._is_speaking = False
                self._speech_queue.task_done()
            except Exception as e:
                logger.error(f"Error in TTS worker process: {e}")
                self._is_speaking = False

    def _speak_text(self, text: str):
        # Primary Attempt: Edge TTS
        try:
            import edge_tts
            import pygame

            logger.info(f"Generating Edge TTS for: '{text[:30]}...'")
            tmp_mp3 = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False).name
            
            async def _generate():
                communicate = edge_tts.Communicate(text, self.voice)
                await communicate.save(tmp_mp3)

            asyncio.run(_generate())

            if self._stop_event.is_set():
                if os.path.exists(tmp_mp3):
                    os.remove(tmp_mp3)
                return

            # Play audio using pygame
            pygame.mixer.init()
            pygame.mixer.music.load(tmp_mp3)
            pygame.mixer.music.play()

            while pygame.mixer.music.get_busy():
                if self._stop_event.is_set():
                    pygame.mixer.music.stop()
                    break
                pygame.time.Clock().tick(10)

            pygame.mixer.quit()

            if os.path.exists(tmp_mp3):
                os.remove(tmp_mp3)

            return

        except Exception as e:
            logger.warning(f"Edge TTS generation/playback failed: {e}. Falling back to Piper TTS / pyttsx3...")

        # Secondary Attempt: Piper Neural TTS (Fast Offline)
        try:
            from piper.voice import PiperVoice
            import wave
            import pygame
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            model_path = os.path.join(base_dir, "en_US-lessac-medium.onnx")
            if os.path.exists(model_path):
                if not hasattr(self, "_piper_voice") or self._piper_voice is None:
                    self._piper_voice = PiperVoice.load(model_path)

                tmp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
                with wave.open(tmp_wav, "wb") as wav_file:
                    self._piper_voice.synthesize_wav(text, wav_file)

                if self._stop_event.is_set():
                    if os.path.exists(tmp_wav):
                        os.remove(tmp_wav)
                    return

                pygame.mixer.init()
                pygame.mixer.music.load(tmp_wav)
                pygame.mixer.music.play()

                while pygame.mixer.music.get_busy():
                    if self._stop_event.is_set():
                        pygame.mixer.music.stop()
                        break
                    pygame.time.Clock().tick(10)

                pygame.mixer.quit()
                if os.path.exists(tmp_wav):
                    os.remove(tmp_wav)
                return
        except Exception as piper_err:
            logger.warning(f"Piper TTS fallback failed: {piper_err}. Falling back to pyttsx3...")

        # Fallback Attempt: pyttsx3 (SAPI5 offline)
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()
        except Exception as e:
            logger.error(f"Offline pyttsx3 fallback failed: {e}")
