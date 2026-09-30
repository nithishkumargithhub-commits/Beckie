"""
JARVIS – Local Emotion Engine.

Provides local-first emotion inference from conversation text using Qwen3 8B
with a structured classification head, optional CPU-only voice prosody extraction
from faster-whisper outputs, multi-modal fusion, and temporal smoothing over turns.

Privacy Guarantee: All inference is local-first, zero GPU VRAM additions,
and completely revocable.
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from core.ollama_adapter import ChatMessage, get_adapter

logger = logging.getLogger("Jarvis.Core.EmotionEngine")

DEFAULT_MODEL = "qwen3:8b"
DEFAULT_WINDOW_SIZE = 5
DEFAULT_SMOOTHING_ALPHA = 0.65
DEFAULT_LLM_TIMEOUT = 0.25


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class ProsodyFeatures:
    """Voice prosody cues extracted from faster-whisper segments or audio."""
    speaking_rate: float        # words per second (normal: 2.5 - 4.2)
    pause_ratio: float          # ratio of silence/pause time to duration [0.0, 1.0]
    utterance_energy: float     # normalized audio RMS energy [0.0, 1.0]
    duration_sec: float         # total utterance duration in seconds

    def to_dict(self) -> Dict[str, float]:
        return {
            "speaking_rate": round(self.speaking_rate, 2),
            "pause_ratio": round(self.pause_ratio, 3),
            "utterance_energy": round(self.utterance_energy, 3),
            "duration_sec": round(self.duration_sec, 2),
        }


@dataclass
class EmotionState:
    """Compact VAD (Valence, Arousal, Dominance) emotion representation."""
    valence: float                      # [-1.0, 1.0]: negative to positive
    arousal: float                      # [0.0, 1.0]: calm to intense/agitated
    dominance: float                    # [0.0, 1.0]: overwhelmed to in-control/assertive
    labels: List[str]                   # e.g. ["frustrated", "stressed"], ["focused"]
    confidence: float                   # [0.0, 1.0]
    timestamp: float = field(default_factory=time.time)
    is_neutral_mode: bool = False
    prosody_cues: Optional[Dict[str, float]] = None

    def __post_init__(self) -> None:
        # Clamp bounds strictly
        self.valence = max(-1.0, min(1.0, float(self.valence)))
        self.arousal = max(0.0, min(1.0, float(self.arousal)))
        self.dominance = max(0.0, min(1.0, float(self.dominance)))
        self.confidence = max(0.0, min(1.0, float(self.confidence)))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valence": round(self.valence, 3),
            "arousal": round(self.arousal, 3),
            "dominance": round(self.dominance, 3),
            "labels": list(self.labels),
            "confidence": round(self.confidence, 3),
            "timestamp": self.timestamp,
            "is_neutral_mode": self.is_neutral_mode,
            "prosody_cues": self.prosody_cues,
        }

    @classmethod
    def neutral(cls) -> EmotionState:
        """Returns neutral emotional baseline."""
        return cls(
            valence=0.0,
            arousal=0.0,
            dominance=0.5,
            labels=["neutral"],
            confidence=1.0,
            is_neutral_mode=True,
            prosody_cues=None,
        )


# ---------------------------------------------------------------------------
# Rule-Based Heuristic Fallback (Ensures latency <= 600ms and offline stability)
# ---------------------------------------------------------------------------

_POSITIVE_WORDS = {
    "great", "awesome", "good", "excellent", "love", "thanks", "thank",
    "perfect", "amazing", "happy", "glad", "cool", "wonderful", "nice"
}
_NEGATIVE_WORDS = {
    "bad", "terrible", "awful", "hate", "broken", "fail", "failed",
    "failing", "error", "bug", "wrong", "annoying", "stupid", "stuck",
    "frustrated", "angry", "slow", "horrible", "useless"
}
_HIGH_AROUSAL_WORDS = {
    "hurry", "urgent", "fast", "asap", "immediately", "now", "crash",
    "emergency", "panic", "cannot", "critical", "fix", "fatal"
}
_LOW_DOMINANCE_WORDS = {
    "confused", "help", "lost", "idk", "understand", "overwhelmed",
    "stuck", "tired", "exhausted", "hopeless", "dunno", "unsure"
}
_HIGH_DOMINANCE_WORDS = {
    "execute", "run", "do", "must", "override", "force", "sure",
    "deploy", "start", "proceed", "commit", "apply", "build"
}


def _heuristic_classify_text(text: str) -> EmotionState:
    """Fast, deterministic fallback classifier computing VAD from text tokens."""
    words = re.findall(r"\b[a-z']+\b", text.lower())
    if not words:
        return EmotionState.neutral()

    pos_count = sum(1 for w in words if w in _POSITIVE_WORDS)
    neg_count = sum(1 for w in words if w in _NEGATIVE_WORDS)
    high_arousal_count = sum(1 for w in words if w in _HIGH_AROUSAL_WORDS)
    low_dom_count = sum(1 for w in words if w in _LOW_DOMINANCE_WORDS)
    high_dom_count = sum(1 for w in words if w in _HIGH_DOMINANCE_WORDS)

    # Exclamation & all-caps checks
    exclamations = text.count("!")
    is_caps = len(text) > 4 and text.isupper()

    # Valence: [-1.0, 1.0]
    total_sentiment = pos_count + neg_count
    if total_sentiment > 0:
        val = (pos_count - neg_count) / float(total_sentiment)
    else:
        val = 0.0

    # Arousal: [0.0, 1.0]
    arousal_score = (high_arousal_count * 0.3) + (min(exclamations, 3) * 0.15) + (0.3 if is_caps else 0.0) + (0.2 if neg_count > 0 else 0.0)
    arousal = min(1.0, max(0.05, arousal_score))

    # Dominance: [0.0, 1.0]
    dom_delta = (high_dom_count * 0.2) - (low_dom_count * 0.25)
    dominance = min(1.0, max(0.1, 0.5 + dom_delta))

    # Determine labels
    labels = []
    if neg_count > pos_count:
        if arousal > 0.4:
            labels.append("frustrated")
        else:
            labels.append("dissatisfied")
    elif pos_count > neg_count:
        labels.append("pleased")

    if low_dom_count > 0:
        labels.append("confused" if val >= -0.2 else "overwhelmed")
    if high_dom_count > 0 and dominance >= 0.7:
        labels.append("assertive")
    if high_arousal_count > 0:
        labels.append("urgent")

    if not labels:
        labels.append("neutral" if abs(val) < 0.2 else ("positive" if val > 0 else "negative"))

    return EmotionState(
        valence=val,
        arousal=arousal,
        dominance=dominance,
        labels=labels,
        confidence=0.85,
    )


# ---------------------------------------------------------------------------
# Prosody Feature Extractor (CPU-only, lightweight)
# ---------------------------------------------------------------------------

class ProsodyExtractor:
    """Extracts speaking rate, pause ratios, and utterance energy without GPU models."""

    @staticmethod
    def extract_from_segments(
        segments: Sequence[Any],
        audio_array: Optional[Any] = None,
    ) -> Optional[ProsodyFeatures]:
        """
        Extracts prosody cues from faster-whisper segment objects or dicts.
        """
        if not segments:
            return None

        total_words = 0
        total_pause_time = 0.0
        prev_end: Optional[float] = None
        start_time: Optional[float] = None
        end_time: Optional[float] = None

        for seg in segments:
            seg_start = getattr(seg, "start", None) if hasattr(seg, "start") else seg.get("start", 0.0)
            seg_end = getattr(seg, "end", None) if hasattr(seg, "end") else seg.get("end", 0.0)
            seg_text = getattr(seg, "text", "") if hasattr(seg, "text") else seg.get("text", "")

            if start_time is None:
                start_time = seg_start
            end_time = seg_end

            words = len(seg_text.strip().split())
            total_words += words

            if prev_end is not None and seg_start > prev_end:
                gap = seg_start - prev_end
                if gap > 0.15:  # meaningful pause threshold: >150ms
                    total_pause_time += gap

            prev_end = seg_end

        if start_time is None or end_time is None or end_time <= start_time:
            return None

        total_duration = max(0.2, end_time - start_time)
        speaking_rate = total_words / total_duration
        pause_ratio = min(1.0, total_pause_time / total_duration)

        # Compute energy if raw audio array is provided
        energy = 0.5  # default moderate energy
        if audio_array is not None:
            try:
                import numpy as np
                arr = np.asarray(audio_array, dtype=np.float32)
                if arr.size > 0:
                    rms = float(np.sqrt(np.mean(np.square(arr))))
                    # Normalize RMS roughly to 0.0 - 1.0 range
                    energy = min(1.0, max(0.0, rms * 10.0))
            except Exception as exc:
                logger.debug("Error computing audio energy: %s", exc)

        return ProsodyFeatures(
            speaking_rate=speaking_rate,
            pause_ratio=pause_ratio,
            utterance_energy=energy,
            duration_sec=total_duration,
        )


# ---------------------------------------------------------------------------
# Emotion Engine
# ---------------------------------------------------------------------------

class EmotionEngine:
    """
    Main emotion inference engine.
    Produces compact VAD emotion states from text and optional prosody cues.
    Maintains turn-to-turn temporal smoothing and privacy controls.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        window_size: int = DEFAULT_WINDOW_SIZE,
        smoothing_alpha: float = DEFAULT_SMOOTHING_ALPHA,
        neutral_mode: bool = False,
    ) -> None:
        self.model_name = model_name
        self.window_size = window_size
        self.smoothing_alpha = smoothing_alpha
        self.neutral_mode = neutral_mode

        self._history: List[EmotionState] = []
        self._smoothed_state: Optional[EmotionState] = None

    # ------------------------------------------------------------------
    # Text Emotion Inference
    # ------------------------------------------------------------------

    def infer_text_emotion(self, text: str, timeout: float = DEFAULT_LLM_TIMEOUT) -> EmotionState:
        """
        Infers emotion from input text using Qwen3 8B structured output with
        fast heuristic fallback to guarantee <= 600 ms turn latency.
        """
        if self.neutral_mode or not text.strip():
            return EmotionState.neutral()

        start_t = time.perf_counter()
        # Attempt Qwen3 8B classification
        try:
            adapter = get_adapter()
            system_prompt = (
                "You are an emotion classification head. Analyze the emotional tone of the user's message.\n"
                "Respond with ONLY a raw JSON object with keys:\n"
                "- valence: float from -1.0 (very negative) to 1.0 (very positive)\n"
                "- arousal: float from 0.0 (calm) to 1.0 (intense/agitated)\n"
                "- dominance: float from 0.0 (submissive/overwhelmed) to 1.0 (assertive/in control)\n"
                "- labels: list of strings (e.g. [\"frustrated\"], [\"confident\"], [\"neutral\"])\n"
                "- confidence: float from 0.0 to 1.0\n"
                "No markdown formatting, no explanations."
            )
            # Cap effective timeout to strictly satisfy <= 600ms latency requirement
            elapsed = time.perf_counter() - start_t
            effective_timeout = max(0.05, min(timeout, 0.35 - elapsed))
            resp = adapter.create_chat_completion(
                messages=[
                    ChatMessage(role="system", content=system_prompt),
                    ChatMessage(role="user", content=text),
                ],
                model=self.model_name,
                timeout=effective_timeout,
                max_tokens=64,
            )
            raw_text = resp.choices[0].message.content.strip()
            # Extract JSON block if wrapped
            json_match = re.search(r"\{.*?\}", raw_text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
                return EmotionState(
                    valence=max(-1.0, min(1.0, float(data.get("valence", 0.0)))),
                    arousal=max(0.0, min(1.0, float(data.get("arousal", 0.0)))),
                    dominance=max(0.0, min(1.0, float(data.get("dominance", 0.5)))),
                    labels=[str(lbl) for lbl in data.get("labels", ["neutral"])],
                    confidence=max(0.0, min(1.0, float(data.get("confidence", 0.8)))),
                )
        except Exception as exc:
            # Latency limit or offline Ollama: gracefully fallback to fast heuristic
            logger.debug("Falling back to local heuristic emotion classifier (%s)", exc)

        return _heuristic_classify_text(text)

    # ------------------------------------------------------------------
    # Multi-Modal Fusion
    # ------------------------------------------------------------------

    def fuse_emotion(
        self,
        text_emotion: EmotionState,
        prosody: Optional[ProsodyFeatures],
    ) -> EmotionState:
        """
        Fuses text emotion with voice prosody cues into a unified EmotionState.
        """
        if self.neutral_mode or text_emotion.is_neutral_mode:
            return EmotionState.neutral()

        if prosody is None:
            return text_emotion

        fused_valence = text_emotion.valence
        fused_arousal = text_emotion.arousal
        fused_dominance = text_emotion.dominance
        labels = list(text_emotion.labels)

        # 1. Arousal modulation from speaking rate and energy
        # Fast speech (>4.0 wps) or elevated energy (>0.65) raises arousal
        if prosody.speaking_rate > 4.2 or prosody.utterance_energy > 0.65:
            arousal_boost = 0.25 * (min(prosody.speaking_rate / 4.0, 1.5) - 1.0) + (prosody.utterance_energy * 0.15)
            fused_arousal = min(1.0, fused_arousal + max(0.1, arousal_boost))
            if "urgent" not in labels and fused_arousal > 0.5:
                labels.append("urgent")
        # Slow speech (<2.0 wps) and low energy (<0.3) lowers arousal
        elif prosody.speaking_rate < 2.2 and prosody.utterance_energy < 0.3:
            fused_arousal = max(0.05, fused_arousal - 0.2)
            if fused_valence < -0.1 and "fatigued" not in labels:
                labels.append("fatigued")

        # 2. Dominance modulation from pause ratio
        # Excessive hesitant pausing (>40% pause ratio) indicates uncertainty/overwhelm
        if prosody.pause_ratio > 0.4:
            fused_dominance = max(0.1, fused_dominance - 0.2)
            if "hesitant" not in labels and "neutral" in labels:
                labels.remove("neutral")
                labels.append("hesitant")
        # Steady, fluent delivery with high energy increases dominance
        elif prosody.pause_ratio < 0.15 and prosody.utterance_energy > 0.5:
            fused_dominance = min(1.0, fused_dominance + 0.15)
            if "assertive" not in labels and fused_dominance > 0.65:
                labels.append("assertive")

        return EmotionState(
            valence=fused_valence,
            arousal=fused_arousal,
            dominance=fused_dominance,
            labels=labels,
            confidence=min(1.0, text_emotion.confidence + 0.05),
            prosody_cues=prosody.to_dict(),
        )

    # ------------------------------------------------------------------
    # Temporal Smoothing & Turn Processing
    # ------------------------------------------------------------------

    def process_turn(
        self,
        text: str,
        prosody_segments: Optional[Sequence[Any]] = None,
        audio_array: Optional[Any] = None,
    ) -> EmotionState:
        """
        Complete pipeline for a conversation turn:
        Infers text emotion, extracts prosody, fuses signals, applies temporal smoothing.
        """
        if self.neutral_mode:
            state = EmotionState.neutral()
            self._history.append(state)
            self._smoothed_state = state
            return state

        # 1. Infer text emotion
        text_state = self.infer_text_emotion(text)

        # 2. Extract prosody if segments provided
        prosody = None
        if prosody_segments:
            prosody = ProsodyExtractor.extract_from_segments(prosody_segments, audio_array=audio_array)

        # 3. Fuse signals
        instant_state = self.fuse_emotion(text_state, prosody)

        # 4. Temporal smoothing (Exponential Moving Average over turn history)
        if self._smoothed_state is None:
            smoothed = instant_state
        else:
            alpha = self.smoothing_alpha
            s_val = alpha * instant_state.valence + (1 - alpha) * self._smoothed_state.valence
            s_arousal = alpha * instant_state.arousal + (1 - alpha) * self._smoothed_state.arousal
            s_dom = alpha * instant_state.dominance + (1 - alpha) * self._smoothed_state.dominance

            # Inherit current instant labels if confidence is high, or merge
            merged_labels = instant_state.labels if instant_state.confidence >= 0.7 else list(set(instant_state.labels + self._smoothed_state.labels))

            smoothed = EmotionState(
                valence=s_val,
                arousal=s_arousal,
                dominance=s_dom,
                labels=merged_labels,
                confidence=instant_state.confidence,
                prosody_cues=instant_state.prosody_cues,
            )

        self._history.append(instant_state)
        if len(self._history) > self.window_size:
            self._history = self._history[-self.window_size:]

        self._smoothed_state = smoothed
        return smoothed

    def get_current_state(self) -> EmotionState:
        """Returns the current smoothed emotion state or neutral baseline."""
        if self.neutral_mode or self._smoothed_state is None:
            return EmotionState.neutral()
        return self._smoothed_state

    def clear_history(self) -> None:
        """Clears in-memory emotion tracking history."""
        self._history.clear()
        self._smoothed_state = None
        logger.info("Emotion engine history cleared.")


# Module-level instance
_default_engine: Optional[EmotionEngine] = None


def get_emotion_engine(neutral_mode: bool = False) -> EmotionEngine:
    global _default_engine
    if _default_engine is None:
        _default_engine = EmotionEngine(neutral_mode=neutral_mode)
    return _default_engine
