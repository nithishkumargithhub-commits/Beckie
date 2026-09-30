"""
JARVIS – Adaptive Dialogue Manager.

Consumes the active EmotionState and modulates:
  - tone_style: supportive | balanced | direct
  - challenge_level: gentle | standard | rigorous
  - step_size: small | normal | large

Challenge-Mode Safety Invariants:
  - NEVER agree with unsafe, destructive, or factually incorrect plans.
  - State uncertainty explicitly when confidence is limited.
  - Never fake execution.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from core.emotion_engine import EmotionState, get_emotion_engine

logger = logging.getLogger("Jarvis.Core.DialogueManager")


# ---------------------------------------------------------------------------
# Permitted Adaptive Categories
# ---------------------------------------------------------------------------

TONE_STYLES = {"supportive", "balanced", "direct"}
CHALLENGE_LEVELS = {"gentle", "standard", "rigorous"}
STEP_SIZES = {"small", "normal", "large"}


@dataclass
class DialogueAdaptation:
    """Represents the active behavioral adaptation of the assistant."""
    tone_style: str                # supportive | balanced | direct
    challenge_level: str           # gentle | standard | rigorous
    step_size: str                 # small | normal | large
    reason: str
    emotion_state: EmotionState
    system_prompt_addon: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tone_style": self.tone_style,
            "challenge_level": self.challenge_level,
            "step_size": self.step_size,
            "reason": self.reason,
            "emotion_state": self.emotion_state.to_dict(),
            "system_prompt_addon": self.system_prompt_addon,
        }


# ---------------------------------------------------------------------------
# Dialogue Manager
# ---------------------------------------------------------------------------

class DialogueManager:
    """
    Manages conversational adaptation based on inferred user emotion,
    ensuring safety invariants and challenge-mode guarantees are preserved.
    """

    def __init__(self, neutral_mode: bool = False) -> None:
        self.neutral_mode = neutral_mode
        self._current_adaptation: Optional[DialogueAdaptation] = None

    def adapt(self, emotion: Optional[EmotionState] = None) -> DialogueAdaptation:
        """
        Determines the optimal tone, challenge intensity, and pacing (step size)
        based on the user's emotion state.
        """
        state = emotion or EmotionState.neutral()
        if self.neutral_mode or state.is_neutral_mode:
            adaptation = DialogueAdaptation(
                tone_style="balanced",
                challenge_level="standard",
                step_size="normal",
                reason="Neutral mode active: standard balanced baseline.",
                emotion_state=state,
                system_prompt_addon=self._build_prompt_addon("balanced", "standard", "normal"),
            )
            self._current_adaptation = adaptation
            return adaptation

        v = state.valence
        a = state.arousal
        d = state.dominance
        labels = state.labels

        reasons = []

        # ------------------------------------------------------------------
        # 1. Tone Style Selection
        # ------------------------------------------------------------------
        # Supportive: user is stressed, frustrated, overwhelmed, or anxious
        if v < -0.25 or "frustrated" in labels or "overwhelmed" in labels or "anxious" in labels:
            tone_style = "supportive"
            reasons.append("negative valence/frustration detected")
        # Direct: user is decisive, urgent, rushed, assertive, or confident
        elif (d >= 0.70 or "urgent" in labels or "assertive" in labels) and v >= -0.2:
            tone_style = "direct"
            reasons.append("high dominance/urgency detected")
        else:
            tone_style = "balanced"
            reasons.append("balanced affective baseline")

        # ------------------------------------------------------------------
        # 2. Challenge Level Selection (Preserving Truthfulness & Safety)
        # ------------------------------------------------------------------
        # Gentle: user is emotionally strained; point out errors with softer phrasing
        if v < -0.30 or d < 0.35 or "frustrated" in labels or "overwhelmed" in labels:
            challenge_level = "gentle"
            reasons.append("gentle challenge to avoid escalating emotional friction")
        # Rigorous: user is confident, high-dominance, focused; detailed critique
        elif d >= 0.65 or "focused" in labels or "assertive" in labels:
            challenge_level = "rigorous"
            reasons.append("rigorous challenge for high-focus/confident state")
        else:
            challenge_level = "standard"
            reasons.append("standard challenge level")

        # ------------------------------------------------------------------
        # 3. Step Size Selection (Cognitive Load & Pacing)
        # ------------------------------------------------------------------
        # Small: user is overwhelmed, confused, or stressed
        if v < -0.30 or d < 0.35 or "confused" in labels or "overwhelmed" in labels:
            step_size = "small"
            reasons.append("small bite-sized steps to reduce cognitive overload")
        # Large: user is in flow, high-dominance, decisive
        elif d >= 0.70 and v >= 0.0:
            step_size = "large"
            reasons.append("large comprehensive step size for high dominance flow")
        else:
            step_size = "normal"
            reasons.append("normal step size")

        prompt_addon = self._build_prompt_addon(tone_style, challenge_level, step_size)
        adaptation = DialogueAdaptation(
            tone_style=tone_style,
            challenge_level=challenge_level,
            step_size=step_size,
            reason="; ".join(reasons),
            emotion_state=state,
            system_prompt_addon=prompt_addon,
        )
        self._current_adaptation = adaptation
        logger.info(
            "Dialogue adapted: tone=%s, challenge=%s, steps=%s (V=%.2f, A=%.2f, D=%.2f)",
            tone_style, challenge_level, step_size, v, a, d
        )
        return adaptation

    def _build_prompt_addon(self, tone_style: str, challenge_level: str, step_size: str) -> str:
        """Constructs behavioral instructions to append to the system prompt."""
        tone_instructions = {
            "supportive": (
                "- **Tone (Supportive)**: Adopt a calm, reassuring, and patient demeanor. "
                "Acknowledge challenges validatingly without being patronizing or overly wordy."
            ),
            "balanced": (
                "- **Tone (Balanced)**: Maintain a clear, objective, and professional demeanor. "
                "Be polite and helpful."
            ),
            "direct": (
                "- **Tone (Direct)**: Be highly concise, efficient, and action-oriented. "
                "Skip pleasantries and deliver key technical details or next actions immediately."
            ),
        }[tone_style]

        challenge_instructions = {
            "gentle": (
                "- **Challenge Mode (Gentle)**: When pointing out errors, frame them constructively "
                "and gently (e.g. 'One thing to consider is...' or 'Shall we double-check...?'). "
                "CRITICAL: Never agree with unsafe, factually incorrect, or destructive actions, "
                "even when gentle."
            ),
            "standard": (
                "- **Challenge Mode (Standard)**: Disagree politely and clearly if the user's premise "
                "is factually incorrect or risky. Ask clarifying questions on ambiguity."
            ),
            "rigorous": (
                "- **Challenge Mode (Rigorous)**: Actively challenge assumptions, inspect subtle edge cases, "
                "and demand rigorous validation. Provide in-depth technical analysis of trade-offs."
            ),
        }[challenge_level]

        step_instructions = {
            "small": (
                "- **Pacing (Small Steps)**: Present ONLY 1 or 2 clear, bite-sized immediate next steps. "
                "Do not overwhelm with extensive lists."
            ),
            "normal": (
                "- **Pacing (Normal)**: Present standard step-by-step guidance (3-4 points)."
            ),
            "large": (
                "- **Pacing (Large Steps)**: Deliver comprehensive solutions and high-level architectural "
                "blocks at once with minimal hand-holding."
            ),
        }[step_size]

        return (
            "\n### Adaptive Dialogue Directives\n"
            f"{tone_instructions}\n"
            f"{challenge_instructions}\n"
            f"{step_instructions}\n"
            "- **Safety & Honesty Invariant**: Explicitly state uncertainty whenever confidence is below 80%. "
            "NEVER validate dangerous or false plans.\n"
        )

    def get_current_adaptation(self) -> Optional[DialogueAdaptation]:
        return self._current_adaptation


# Module-level instance
_default_dialogue_manager: Optional[DialogueManager] = None


def get_dialogue_manager(neutral_mode: bool = False) -> DialogueManager:
    global _default_dialogue_manager
    if _default_dialogue_manager is None:
        _default_dialogue_manager = DialogueManager(neutral_mode=neutral_mode)
    return _default_dialogue_manager
