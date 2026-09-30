"""
Tests for Adaptive Dialogue Manager.

Covers:
1. Behavioral adaptation mapping (tone_style, challenge_level, step_size).
2. Supportive tone and gentle challenge for frustrated / overwhelmed users.
3. Direct tone and rigorous challenge for confident / high-dominance users.
4. Balanced baseline for neutral mode.
5. Invariant preservation: Never agree with unsafe/incorrect plans; calibrated uncertainty.
"""

from __future__ import annotations

import pytest

from core.dialogue_manager import (
    CHALLENGE_LEVELS,
    STEP_SIZES,
    TONE_STYLES,
    DialogueAdaptation,
    DialogueManager,
    get_dialogue_manager,
)
from core.emotion_engine import EmotionState


class TestDialogueManager:
    @pytest.fixture
    def manager(self) -> DialogueManager:
        return DialogueManager()

    def test_frustrated_adaptation(self, manager: DialogueManager) -> None:
        """Frustrated / stressed user gets supportive tone, gentle challenge, and small steps."""
        frustrated_state = EmotionState(
            valence=-0.65,
            arousal=0.75,
            dominance=0.25,
            labels=["frustrated", "overwhelmed"],
            confidence=0.9,
        )
        adaptation = manager.adapt(frustrated_state)
        assert adaptation.tone_style == "supportive"
        assert adaptation.challenge_level == "gentle"
        assert adaptation.step_size == "small"
        assert "negative valence/frustration detected" in adaptation.reason
        assert "Supportive" in adaptation.system_prompt_addon

    def test_confident_assertive_adaptation(self, manager: DialogueManager) -> None:
        """Confident, high-dominance user gets direct tone, rigorous challenge, and large steps."""
        assertive_state = EmotionState(
            valence=0.45,
            arousal=0.55,
            dominance=0.85,
            labels=["assertive", "focused"],
            confidence=0.95,
        )
        adaptation = manager.adapt(assertive_state)
        assert adaptation.tone_style == "direct"
        assert adaptation.challenge_level == "rigorous"
        assert adaptation.step_size == "large"
        assert "high dominance" in adaptation.reason
        assert "Direct" in adaptation.system_prompt_addon

    def test_neutral_mode_adaptation(self) -> None:
        """Neutral mode strictly returns balanced baseline."""
        manager = DialogueManager(neutral_mode=True)
        intense_state = EmotionState(
            valence=-0.8,
            arousal=0.9,
            dominance=0.1,
            labels=["panic"],
            confidence=0.9,
        )
        adaptation = manager.adapt(intense_state)
        assert adaptation.tone_style == "balanced"
        assert adaptation.challenge_level == "standard"
        assert adaptation.step_size == "normal"
        assert "Neutral mode" in adaptation.reason

    def test_safety_invariants_preserved_in_all_modes(self, manager: DialogueManager) -> None:
        """Verifies that challenge-mode safety guarantees are never omitted."""
        test_states = [
            EmotionState(valence=-0.9, arousal=0.9, dominance=0.1, labels=["furious"], confidence=1.0),
            EmotionState(valence=0.9, arousal=0.8, dominance=0.9, labels=["ecstatic"], confidence=1.0),
            EmotionState.neutral(),
        ]
        for st in test_states:
            adaptation = manager.adapt(st)
            prompt = adaptation.system_prompt_addon
            # Invariant: Never agree with unsafe/incorrect plans
            assert "Never agree with unsafe" in prompt or "NEVER validate dangerous" in prompt
            # Invariant: State uncertainty explicitly
            assert "Explicitly state uncertainty" in prompt or "state uncertainty" in prompt.lower()
