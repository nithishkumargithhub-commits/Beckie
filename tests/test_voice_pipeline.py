"""
JARVIS – Voice Pipeline Test Suite (test_voice_pipeline.py).

Comprehensive tests covering:
  1. openWakeWord 'Hey Beckie' ONNX model loading and detection
  2. False positive rate measurement (< 1 / hour requirement)
  3. faster-whisper tiny.en STT on CPU int8 with on-demand loading/unloading
  4. Whisper WER verification (< 7% requirement on test audio)
  5. Piper TTS en_US-lessac-medium streaming with latency verification (< 500ms requirement)
  6. On-demand loading/unloading of Piper TTS
  7. Windows microphone permission prompt via pywin32 / mock
  8. Visible listening indicator (tray icon state transitions)
  9. Voice command router end-to-end (wake -> STT -> intent -> confirmation -> TTS)
"""

from __future__ import annotations

import os
import tempfile
import time
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from core.audit_logger import AuditLogger
from core.intent_classifier import IntentAnalysis, IntentClassifier, IntentEnum
from core.permission_broker import PermissionBroker, PermissionTier
from pipeline.action_executor import ActionExecutor
from pipeline.indicator import IndicatorState, TrayListeningIndicator, create_indicator_icon
from pipeline.mic_permission import MicrophonePermissionManager
from pipeline.stt import SpeechToText, calculate_wer
from pipeline.train_wakeword import DEFAULT_MODEL_PATH, measure_false_positive_rate
from pipeline.tts import TextToSpeech
from pipeline.voice_router import VoiceCommandRouter
from pipeline.wake_word import WakeWordListener

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ===========================================================================
# 1 & 2: openWakeWord Hey Beckie & False Positive Rate
# ===========================================================================

class TestHeyBeckieWakeWord:
    def test_hey_beckie_onnx_model_exists(self):
        assert DEFAULT_MODEL_PATH.exists(), f"Hey Beckie model missing at {DEFAULT_MODEL_PATH}"
        assert DEFAULT_MODEL_PATH.stat().st_size > 1000

    def test_openwakeword_loads_hey_beckie_model(self):
        from openwakeword.model import Model
        oww = Model(wakeword_models=[str(DEFAULT_MODEL_PATH)], inference_framework="onnx")
        assert "hey_beckie" in oww.models
        assert oww.model_inputs["hey_beckie"] == 16

    def test_listener_processes_silent_chunk_no_trigger(self):
        listener = WakeWordListener(on_wake_callback=MagicMock(), model_path=DEFAULT_MODEL_PATH)
        silent_chunk = np.zeros(1280, dtype=np.int16)
        triggered = listener.process_audio_chunk(silent_chunk)
        assert triggered is False
        listener.on_wake_callback.assert_not_called()

    def test_false_positive_rate_below_one_per_hour(self):
        """Verify requirement: wake-word false positive rate (< 1/hour)."""
        fpr = measure_false_positive_rate(str(DEFAULT_MODEL_PATH), duration_hours=0.01)
        assert fpr < 1.0, f"False positive rate {fpr} exceeds threshold of 1.0/hour"


# ===========================================================================
# 3 & 4: faster-whisper tiny.en STT & WER < 7%
# ===========================================================================

class TestWhisperSTT:
    def test_calculate_wer_exact_match(self):
        ref = "the quick brown fox"
        hyp = "the quick brown fox"
        assert calculate_wer(ref, hyp) == 0.0

    def test_calculate_wer_with_substitution(self):
        ref = "the quick brown fox"
        hyp = "the fast brown fox"
        assert calculate_wer(ref, hyp) == 0.25

    def test_whisper_on_demand_loading_and_unloading(self):
        """Requirement: Load Whisper only during active listening (unload after)."""
        stt = SpeechToText(model_name="tiny.en", auto_unload=True)
        assert stt._whisper_model is None

        # Load
        model = stt.load_model()
        assert model is not None
        assert stt._whisper_model is not None

        # Unload
        stt.unload_model()
        assert stt._whisper_model is None

    def test_whisper_wer_under_seven_percent(self):
        """Requirement: Verify Whisper WER < 7% on test audio."""
        stt = SpeechToText(model_name="tiny.en", auto_unload=True)
        tts = TextToSpeech(auto_unload=True)

        test_phrase = "Good morning JARVIS. Please check my schedule and set a meeting at two o'clock."
        chunks = list(tts.stream_audio_chunks(test_phrase))
        assert len(chunks) > 0

        # Combine float32 chunks into 16-bit PCM WAV at 22050 Hz
        full_audio = np.concatenate(chunks)
        full_audio_int16 = (full_audio * 32767).astype(np.int16)

        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        try:
            with wave.open(tmp.name, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(22050)
                wf.writeframes(full_audio_int16.tobytes())

            hypothesis = stt.transcribe_audio_file(tmp.name)
            wer = calculate_wer(test_phrase, hypothesis)
            print(f"Ref: '{test_phrase}'")
            print(f"Hyp: '{hypothesis}'")
            print(f"WER: {wer * 100:.2f}%")
            assert wer < 0.07, f"Whisper WER {wer*100:.2f}% exceeded 7% threshold"
        finally:
            if os.path.exists(tmp.name):
                os.remove(tmp.name)


# ===========================================================================
# 5 & 6: Piper TTS Streaming & Latency < 500ms
# ===========================================================================

class TestPiperTTS:
    def test_piper_on_demand_loading_and_unloading(self):
        """Requirement: Load Piper only during active speaking (unload after)."""
        tts = TextToSpeech(auto_unload=True)
        assert tts._piper_voice is None

        voice = tts.load_voice()
        assert voice is not None
        assert tts._piper_voice is not None

        tts.unload_voice()
        assert tts._piper_voice is None

    def test_piper_streaming_latency_under_500ms(self):
        """Requirement: Piper voice latency < 500ms."""
        tts = TextToSpeech(auto_unload=False)
        tts.load_voice()  # Warm up

        text = "Hello, systems are operational and ready."
        chunks = []
        for chunk in tts.stream_audio_chunks(text):
            chunks.append(chunk)

        assert len(chunks) > 0
        latency_ms = tts.last_latency_ms
        tts.unload_voice()

        print(f"Measured Piper latency: {latency_ms:.2f}ms")
        assert latency_ms < 500.0, f"Piper latency {latency_ms}ms exceeded 500ms limit"

    def test_barge_in_stops_playback(self):
        tts = TextToSpeech(auto_unload=True)
        tts.speak("Long test sentence to check interruption.")
        assert tts._stop_event.is_set() is False
        tts.stop()
        assert tts._stop_event.is_set() is True


# ===========================================================================
# 7: Microphone Permission Prompt (Windows Dialog via pywin32)
# ===========================================================================

class TestMicrophonePermission:
    def test_permission_dialog_granted(self, session_id, tmp_db):
        broker = PermissionBroker(session_id=session_id)
        audit = AuditLogger(session_id=session_id, db_path=tmp_db)

        # Dialog returns True (User clicks Yes)
        mock_dialog = MagicMock(return_value=True)
        mgr = MicrophonePermissionManager(
            permission_broker=broker,
            audit_logger=audit,
            dialog_fn=mock_dialog,
        )

        assert mgr.has_permission() is False
        granted = mgr.request_permission()
        assert granted is True
        assert mgr.has_permission() is True
        mock_dialog.assert_called_once()

        # Subsequent call uses cache without re-prompting
        assert mgr.request_permission() is True
        assert mock_dialog.call_count == 1

        audit.flush()
        audit.stop()

    def test_permission_dialog_denied(self, session_id, tmp_db):
        broker = PermissionBroker(session_id=session_id)
        audit = AuditLogger(session_id=session_id, db_path=tmp_db)

        mock_dialog = MagicMock(return_value=False)
        mgr = MicrophonePermissionManager(
            permission_broker=broker,
            audit_logger=audit,
            dialog_fn=mock_dialog,
        )

        granted = mgr.request_permission()
        assert granted is False
        assert mgr.has_permission() is False

        audit.flush()
        audit.stop()

    def test_permission_revocation(self, session_id):
        broker = PermissionBroker(session_id=session_id)
        mgr = MicrophonePermissionManager(
            permission_broker=broker,
            dialog_fn=lambda title, msg: True,
        )
        mgr.request_permission()
        assert mgr.has_permission() is True

        mgr.revoke_permission()
        assert mgr.has_permission() is False


# ===========================================================================
# 8: Visible Listening Indicator (Tray Icon State Transitions)
# ===========================================================================

class TestListeningIndicator:
    def test_icon_generation_for_all_states(self):
        for state in IndicatorState:
            img = create_indicator_icon(state, size=64)
            assert img.size == (64, 64)
            assert img.mode == "RGBA"

    def test_state_transitions(self):
        state_history = []
        indicator = TrayListeningIndicator(
            headless=True,
            on_state_change=lambda s: state_history.append(s),
        )

        assert indicator.state == IndicatorState.IDLE

        indicator.set_state(IndicatorState.LISTENING)
        assert indicator.state == IndicatorState.LISTENING

        indicator.set_state(IndicatorState.PROCESSING)
        assert indicator.state == IndicatorState.PROCESSING

        indicator.set_state(IndicatorState.SPEAKING)
        assert indicator.state == IndicatorState.SPEAKING

        indicator.set_state(IndicatorState.IDLE)
        assert indicator.state == IndicatorState.IDLE

        assert state_history == [
            IndicatorState.LISTENING,
            IndicatorState.PROCESSING,
            IndicatorState.SPEAKING,
            IndicatorState.IDLE,
        ]


# ===========================================================================
# 9: Voice Command Router (wake -> STT -> intent -> confirmation -> TTS)
# ===========================================================================

class TestVoiceCommandRouter:
    @pytest.fixture
    def router_components(self, session_id, tmp_db):
        broker = PermissionBroker(session_id=session_id)
        audit = AuditLogger(session_id=session_id, db_path=tmp_db)
        perm_mgr = MicrophonePermissionManager(
            permission_broker=broker,
            audit_logger=audit,
            dialog_fn=lambda title, msg: True,
        )
        indicator = TrayListeningIndicator(headless=True)
        stt = SpeechToText(auto_unload=True)
        tts = TextToSpeech(auto_unload=True)
        classifier = IntentClassifier()
        executor = ActionExecutor()

        router = VoiceCommandRouter(
            stt=stt,
            tts=tts,
            indicator=indicator,
            permission_broker=broker,
            permission_manager=perm_mgr,
            intent_classifier=classifier,
            action_executor=executor,
            audit_logger=audit,
            confirmation_cb=lambda action, prompt: True,
        )

        yield router, audit
        audit.flush()
        audit.stop()

    def test_router_safe_action_lifecycle(self, router_components):
        router, audit = router_components

        # Mock STT to return greeting
        router.stt.transcribe_pcm_data = MagicMock(return_value="hello jarvis good morning")
        # Mock TTS speak to avoid hardware audio output during test
        router.tts.speak = MagicMock()

        dummy_audio = b"\x00" * 3200
        result = router.handle_wake_event(pcm_audio=dummy_audio)

        assert result["wake_detected"] is True
        assert result["transcript"] == "hello jarvis good morning"
        assert result["intent"] == "greeting"
        assert result["status"] == "completed"
        assert "morning" in result["response"].lower() or "assist" in result["response"].lower()
        assert router.indicator.state == IndicatorState.IDLE
        router.tts.speak.assert_called_once()

    def test_router_write_action_with_confirmation_approved(self, router_components):
        router, audit = router_components

        router.stt.transcribe_pcm_data = MagicMock(return_value="set volume to 50 percent")
        router.tts.speak = MagicMock()
        router.confirmation_cb = MagicMock(return_value=True)

        result = router.handle_wake_event(pcm_audio=b"\x00" * 3200)

        assert result["intent"] == "set_volume"
        assert result["approved"] is True
        assert result["status"] == "completed"
        router.confirmation_cb.assert_called_once()

    def test_router_write_action_with_confirmation_denied(self, router_components):
        router, audit = router_components

        router.stt.transcribe_pcm_data = MagicMock(return_value="set brightness to 80")
        router.tts.speak = MagicMock()
        # User rejects confirmation dialog
        router.confirmation_cb = MagicMock(return_value=False)

        result = router.handle_wake_event(pcm_audio=b"\x00" * 3200)

        assert result["intent"] == "set_brightness"
        assert result["approved"] is False
        assert result["status"] == "confirmation_denied"
        assert "cancelled" in result["response"].lower()
        assert router.indicator.state == IndicatorState.IDLE

    def test_router_handles_silence(self, router_components):
        router, audit = router_components
        router.stt.transcribe_pcm_data = MagicMock(return_value="")

        result = router.handle_wake_event(pcm_audio=b"\x00" * 3200)
        assert result["status"] == "silence"
        assert router.indicator.state == IndicatorState.IDLE

    def test_router_mic_permission_denied_aborts(self, router_components):
        router, audit = router_components
        # Revoke mic permission
        router.perm_manager._cached_granted = False
        router.perm_manager._dialog_fn = MagicMock(return_value=False)

        result = router.handle_wake_event(pcm_audio=b"\x00" * 3200)
        assert result["status"] == "mic_permission_denied"
        assert router.indicator.state == IndicatorState.MUTED
