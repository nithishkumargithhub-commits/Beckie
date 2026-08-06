"""
Speech-to-Text (STT) Pipeline Service for JARVIS Voice Assistant.
Combines faster-whisper local model with Google Speech Recognition fallback.
"""

import os
import tempfile
from typing import Optional
from logger import get_logger
from exceptions import STTException

logger = get_logger("Jarvis.Pipeline.STT")

class SpeechToText:
    """Handles speech recording and transcription using Whisper with Google STT fallback."""

    def __init__(self):
        self._whisper_model = None

    def _get_whisper_model(self):
        if self._whisper_model is None:
            try:
                from faster_whisper import WhisperModel
                logger.info("Initializing faster-whisper model (base.en)...")
                self._whisper_model = WhisperModel("base.en", device="cpu", compute_type="int8")
                logger.info("faster-whisper model initialized successfully.")
            except Exception as e:
                logger.warning(f"Could not load faster-whisper: {e}. Will rely on Google Speech fallback.")
                self._whisper_model = False
        return self._whisper_model

    def transcribe_audio_file(self, audio_filepath: str) -> str:
        """Transcribes an audio WAV file using Whisper, falling back to Google STT."""
        if not os.path.exists(audio_filepath):
            raise STTException(f"Audio file not found: {audio_filepath}")

        # Attempt 1: faster-whisper
        model = self._get_whisper_model()
        if model:
            try:
                segments, info = model.transcribe(audio_filepath, beam_size=5, vad_filter=True)
                transcript = " ".join([segment.text.strip() for segment in segments]).strip()
                if transcript:
                    logger.info(f"Whisper transcription complete: '{transcript}'")
                    return transcript
            except Exception as e:
                logger.warning(f"faster-whisper transcription failed: {e}. Trying Google Speech fallback...")

        # Attempt 2: Google Speech Recognition Fallback
        try:
            import speech_recognition as sr
            recognizer = sr.Recognizer()
            with sr.AudioFile(audio_filepath) as source:
                audio_data = recognizer.record(source)
                transcript = recognizer.recognize_google(audio_data)
                logger.info(f"Google STT transcription complete: '{transcript}'")
                return transcript
        except Exception as e:
            logger.error(f"Google STT fallback failed: {e}")
            raise STTException(f"All STT methods failed: {e}")

    def record_and_transcribe(self, duration_sec: float = 5.0) -> str:
        """Records audio from microphone for specified duration and transcribes it."""
        try:
            import sounddevice as sd
            import scipy.io.wavfile as wav

            samplerate = 16000
            logger.info(f"Recording audio for {duration_sec} seconds...")
            recording = sd.rec(int(duration_sec * samplerate), samplerate=samplerate, channels=1, dtype='int16')
            sd.wait()
            logger.info("Recording complete. Saving to temporary WAV file...")

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                tmp_filepath = tmp_file.name
                wav.write(tmp_filepath, samplerate, recording)

            try:
                return self.transcribe_audio_file(tmp_filepath)
            finally:
                if os.path.exists(tmp_filepath):
                    os.remove(tmp_filepath)

        except Exception as e:
            logger.error(f"Error during audio recording/transcription: {e}")
            raise STTException(str(e))
