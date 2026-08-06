import os
import sys

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BASE_DIR not in sys.path:
    sys.path.insert(0, _BASE_DIR)

import logging
import config


logger = logging.getLogger("VoiceAssistant.Transcriber")

try:
    import speech_recognition as sr
except ImportError:
    sr = None

try:
    from faster_whisper import WhisperModel
    HAS_FASTER_WHISPER = True
except Exception as e:
    logger.warning(f"Could not import faster_whisper: {e}. Falling back to SpeechRecognition.")
    HAS_FASTER_WHISPER = False

class Transcriber:
    def __init__(self):
        self.use_fallback = not HAS_FASTER_WHISPER
        if not self.use_fallback:
            logger.info(f"Initializing WhisperModel with size: {config.WHISPER_MODEL}")
            try:
                # Initialize faster-whisper model
                self.model = WhisperModel(
                    config.WHISPER_MODEL,
                    device=config.WHISPER_DEVICE,
                    compute_type=config.WHISPER_COMPUTE_TYPE
                )
                logger.info("WhisperModel initialized successfully.")
            except Exception as e:
                logger.error(f"Error initializing WhisperModel: {e}. Falling back to SpeechRecognition.")
                self.use_fallback = True
                
        if self.use_fallback:
            logger.info("Initializing SpeechRecognition library for fallback transcription.")
            self.recognizer = sr.Recognizer()

    def transcribe(self, audio_path: str) -> str:
        """
        Transcribes the audio file at the given path.
        Returns the transcription text.
        """
        logger.info(f"Transcribing audio file: {audio_path}")
        if not self.use_fallback:
            try:
                language = getattr(config, "WHISPER_LANGUAGE", "en")
                kwargs = {
                    "beam_size": 5,
                    "vad_filter": True
                }
                if language:
                    kwargs["language"] = language

                segments, info = self.model.transcribe(audio_path, **kwargs)
                # Concatenate all transcribed segments
                text_segments = [segment.text for segment in segments]
                full_text = " ".join(text_segments).strip()
                
                # Filter common Whisper background hallucinations
                hallucinations = [
                    "thank you", "thanks for watching", "subtitles by",
                    "amara.org", "subscribe", "see you next time", "bye"
                ]
                clean_check = full_text.lower().strip(" .!,")
                if clean_check in hallucinations or any(clean_check.startswith(h) for h in ["subtitles by", "translated by"]):
                    logger.info(f"Filtered Whisper hallucination: '{full_text}'")
                    return ""

                logger.info(f"Transcription completed. Language: {info.language} (prob: {info.language_probability:.2f})")
                logger.info(f"Result: {full_text}")
                return full_text
            except Exception as e:
                logger.error(f"Error transcribing audio file with WhisperModel: {e}. Trying SpeechRecognition fallback.")
                # Fall through to SpeechRecognition fallback if Whisper fails at runtime
                self.use_fallback = True
                if sr:
                    self.recognizer = sr.Recognizer()

        # Fallback transcription using SpeechRecognition and Google Web Speech API
        if sr and hasattr(self, "recognizer"):
            try:
                with sr.AudioFile(audio_path) as source:
                    audio_data = self.recognizer.record(source)
                full_text = self.recognizer.recognize_google(audio_data)
                logger.info("Transcription completed via SpeechRecognition fallback.")
                logger.info(f"Result: {full_text}")
                return full_text
            except Exception as e:
                logger.error(f"Error transcribing audio file with SpeechRecognition: {e}")
                return ""
        else:
            logger.error("SpeechRecognition (sr) module is not installed for fallback.")
            return ""
