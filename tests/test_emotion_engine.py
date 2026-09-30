"""
Tests for Local Emotion Understanding Engine.

Covers:
1. Text-only emotion classification (valence, arousal, dominance, labels, confidence).
2. Latency verification (<= 600 ms).
3. Prosody feature extraction from faster-whisper transcripts (rate, pause, energy).
4. Multi-modal fusion (text + prosody).
5. Temporal smoothing over turns.
6. Neutral mode baseline behavior.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from core.emotion_engine import (
    EmotionEngine,
    EmotionState,
    ProsodyExtractor,
    ProsodyFeatures,
    get_emotion_engine,
)


class TestEmotionEngine:
    @pytest.fixture
    def engine(self) -> EmotionEngine:
        return EmotionEngine(model_name="qwen3:8b", window_size=5, smoothing_alpha=0.65)

    def test_text_emotion_bounds_and_structure(self, engine: EmotionEngine) -> None:
        """Verifies VAD values are strictly clamped and structured."""
        # Test positive message
        res_pos = engine.infer_text_emotion("Thank you so much, this is awesome and works great!")
        assert -1.0 <= res_pos.valence <= 1.0
        assert 0.0 <= res_pos.arousal <= 1.0
        assert 0.0 <= res_pos.dominance <= 1.0
        assert 0.0 <= res_pos.confidence <= 1.0
        assert res_pos.valence > 0.0
        assert isinstance(res_pos.labels, list)
        assert len(res_pos.labels) > 0

        # Test frustrated / negative message
        res_neg = engine.infer_text_emotion("This is failing again, terrible bug and it is so annoying!")
        assert res_neg.valence < 0.0
        assert res_neg.arousal > 0.2
        assert "frustrated" in res_neg.labels or "dissatisfied" in res_neg.labels

    def test_latency_under_600ms(self, engine: EmotionEngine) -> None:
        """Acceptance Criteria: Emotion inference adds <= 600 ms latency per turn."""
        start_t = time.perf_counter()
        res = engine.infer_text_emotion("Quick status check on my current task.")
        duration_ms = (time.perf_counter() - start_t) * 1000.0
        assert duration_ms <= 600.0, f"Latency was {duration_ms:.1f}ms, expected <= 600ms"
        assert res is not None

    def test_prosody_feature_extraction(self) -> None:
        """Tests CPU-only prosody cue extraction from faster-whisper style segments."""
        # Mock segments: 2 segments with a 0.5s pause in between
        seg1 = {"start": 0.0, "end": 2.0, "text": "Hello Jarvis can you hear me"}
        seg2 = {"start": 2.5, "end": 4.0, "text": "I need assistance right now"}
        segments = [seg1, seg2]

        audio_dummy = [0.05, -0.05, 0.1, -0.1]
        prosody = ProsodyExtractor.extract_from_segments(segments, audio_array=audio_dummy)
        assert prosody is not None
        assert prosody.duration_sec == 4.0
        # 11 words / 4.0s = 2.75 wps
        assert 2.0 <= prosody.speaking_rate <= 3.5
        # 0.5s pause / 4.0s = 0.125 pause ratio
        assert 0.10 <= prosody.pause_ratio <= 0.25
        assert 0.0 <= prosody.utterance_energy <= 1.0

    def test_multimodal_fusion(self, engine: EmotionEngine) -> None:
        """Tests fusing text emotion with voice prosody cues."""
        text_state = EmotionState(
            valence=-0.4,
            arousal=0.3,
            dominance=0.5,
            labels=["dissatisfied"],
            confidence=0.8,
        )
        # Fast, loud speech indicates elevated arousal and urgency
        urgent_prosody = ProsodyFeatures(
            speaking_rate=5.5,      # rushed speech
            pause_ratio=0.05,
            utterance_energy=0.85,  # loud
            duration_sec=2.0,
        )

        fused = engine.fuse_emotion(text_state, urgent_prosody)
        assert fused.arousal > text_state.arousal
        assert "urgent" in fused.labels
        assert fused.prosody_cues is not None
        assert fused.prosody_cues["speaking_rate"] == 5.5

    def test_temporal_smoothing_over_turns(self, engine: EmotionEngine) -> None:
        """Tests EMA smoothing over consecutive turns."""
        # Turn 1: calm neutral
        t1 = engine.process_turn("Hello, good morning.")
        assert t1.valence >= 0.0

        # Turn 2: abrupt negative spike
        t2 = engine.process_turn("Wait, this is broken and failing!")
        # Instant valence is strongly negative, smoothed valence is moderated
        assert t2.valence < t1.valence
        assert len(engine._history) == 2

        # Turn 3: continued frustration
        t3 = engine.process_turn("Still broken, why is this so slow?!")
        assert t3.valence < t2.valence

    def test_neutral_mode_baseline(self) -> None:
        """Tests that neutral mode strictly returns neutral baseline."""
        engine = EmotionEngine(neutral_mode=True)
        res = engine.process_turn("I am extremely furious and angry right now!!!")
        assert res.is_neutral_mode is True
        assert res.valence == 0.0
        assert res.arousal == 0.0
        assert res.dominance == 0.5
        assert res.labels == ["neutral"]

    def test_clear_history(self, engine: EmotionEngine) -> None:
        engine.process_turn("Turn one")
        engine.process_turn("Turn two")
        assert len(engine._history) == 2
        engine.clear_history()
        assert len(engine._history) == 0
        assert engine.get_current_state().is_neutral_mode is True
