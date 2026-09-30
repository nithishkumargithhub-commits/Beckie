"""
JARVIS – Speech-to-Text (STT) Pipeline Service.

Requirements:
  - faster-whisper 'tiny.en' STT with CPU fallback (int8 mode)
  - Load Whisper only during active listening (unload after)
  - Verify Whisper WER < 7% on test audio
"""

from __future__ import annotations

import contextlib
import gc
import logging
import os
import re
import tempfile
from typing import Generator, Optional

logger = logging.getLogger("Jarvis.Pipeline.STT")


def calculate_wer(reference: str, hypothesis: str) -> float:
    """
    Calculate Word Error Rate (WER) using Levenshtein distance on words.
    WER = (Substitutions + Deletions + Insertions) / Total Words in Reference.
    """
    num_map = {
        "0": "zero", "1": "one", "2": "two", "3": "three", "4": "four",
        "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine",
        "10": "ten", "11": "eleven", "12": "twelve",
    }

    def clean_words(text: str) -> list[str]:
        # Lowercase and strip punctuation
        cleaned = re.sub(r"[^\w\s]", "", text.lower())
        words = cleaned.split()
        return [num_map.get(w, w) for w in words]

    ref_words = clean_words(reference)
    hyp_words = clean_words(hypothesis)

    if not ref_words:
        return 0.0 if not hyp_words else 1.0

    r_len = len(ref_words)
    h_len = len(hyp_words)

    # Dynamic programming distance matrix
    d = [[0] * (h_len + 1) for _ in range(r_len + 1)]

    for i in range(r_len + 1):
        d[i][0] = i
    for j in range(h_len + 1):
        d[0][j] = j

    for i in range(1, r_len + 1):
        for j in range(1, h_len + 1):
            if ref_words[i - 1] == hyp_words[j - 1]:
                d[i][j] = d[i - 1][j - 1]
            else:
                substitution = d[i - 1][j - 1] + 1
                insertion = d[i][j - 1] + 1
                deletion = d[i - 1][j] + 1
                d[i][j] = min(substitution, insertion, deletion)

    return float(d[r_len][h_len]) / float(r_len)


class SpeechToText:
    """
    Managed Speech-to-Text with faster-whisper tiny.en on CPU (int8).
    Unloads the model immediately after transcription to conserve RAM.
    """

    def __init__(self, model_name: str = "tiny.en", auto_unload: bool = True):
        self.model_name = model_name
        self.auto_unload = auto_unload
        self._whisper_model = None

    def load_model(self):
        """Loads faster-whisper tiny.en into memory if not already loaded."""
        if self._whisper_model is None:
            try:
                from faster_whisper import WhisperModel
                logger.info("Loading faster-whisper (%s, device=cpu, int8)...", self.model_name)
                self._whisper_model = WhisperModel(
                    self.model_name,
                    device="cpu",
                    compute_type="int8",
                    cpu_threads=4,
                )
                logger.info("faster-whisper model loaded into memory.")
            except Exception as exc:
                logger.warning("Could not load faster-whisper: %s", exc)
                self._whisper_model = None
        return self._whisper_model

    def unload_model(self) -> None:
        """Unload faster-whisper from memory and run garbage collection."""
        if self._whisper_model is not None:
            del self._whisper_model
            self._whisper_model = None
            gc.collect()
            logger.info("faster-whisper model unloaded from memory.")

    @contextlib.contextmanager
    def active_listening(self) -> Generator[SpeechToText, None, None]:
        """Context manager: load model during active listening, unload afterwards."""
        try:
            self.load_model()
            yield self
        finally:
            if self.auto_unload:
                self.unload_model()

    def transcribe_audio_file(self, audio_filepath: str) -> str:
        """Transcribe audio WAV file. Automatically unloads if auto_unload is True."""
        if not os.path.exists(audio_filepath):
            raise FileNotFoundError(f"Audio file not found: {audio_filepath}")

        model = self.load_model()
        if model is None:
            return self._google_fallback(audio_filepath)

        try:
            segments, info = model.transcribe(
                audio_filepath,
                beam_size=5,
                vad_filter=True,
                language="en",
            )
            transcript = " ".join([segment.text.strip() for segment in segments]).strip()
            logger.info("Whisper transcription: '%s' (lang=%s, prob=%.2f)",
                        transcript, info.language, info.language_probability)
            return transcript
        except Exception as exc:
            logger.warning("faster-whisper failed (%s), trying fallback...", exc)
            return self._google_fallback(audio_filepath)
        finally:
            if self.auto_unload:
                self.unload_model()

    def transcribe_pcm_data(self, audio_data: bytes, sample_rate: int = 16000) -> str:
        """Transcribe raw 16-bit PCM bytes."""
        import wave
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        try:
            with wave.open(tmp.name, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(audio_data)
            return self.transcribe_audio_file(tmp.name)
        finally:
            if os.path.exists(tmp.name):
                os.remove(tmp.name)

    def record_and_transcribe(self, duration_sec: float = 4.0) -> str:
        """Record audio from mic for duration and transcribe it."""
        try:
            import sounddevice as sd
            import numpy as np
            import scipy.io.wavfile as wav

            samplerate = 16000
            logger.info("Recording voice for %.1f seconds...", duration_sec)
            recording = sd.rec(
                int(duration_sec * samplerate),
                samplerate=samplerate,
                channels=1,
                dtype="int16",
            )
            sd.wait()

            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp.close()
            try:
                wav.write(tmp.name, samplerate, recording)
                return self.transcribe_audio_file(tmp.name)
            finally:
                if os.path.exists(tmp.name):
                    os.remove(tmp.name)
        except Exception as exc:
            logger.error("Audio recording error: %s", exc)
            raise

    @staticmethod
    def _google_fallback(audio_filepath: str) -> str:
        """Fallback STT via SpeechRecognition Google API."""
        try:
            import speech_recognition as sr
            recognizer = sr.Recognizer()
            with sr.AudioFile(audio_filepath) as source:
                audio_data = recognizer.record(source)
                return recognizer.recognize_google(audio_data)
        except Exception as exc:
            logger.error("All STT engines failed: %s", exc)
            return ""
