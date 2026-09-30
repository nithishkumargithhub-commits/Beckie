"""
Re-export of core.dialogue_manager under backend.core.dialogue_manager namespace.
"""

from core.dialogue_manager import (
    CHALLENGE_LEVELS,
    STEP_SIZES,
    TONE_STYLES,
    DialogueAdaptation,
    DialogueManager,
    get_dialogue_manager,
)

__all__ = [
    "CHALLENGE_LEVELS",
    "STEP_SIZES",
    "TONE_STYLES",
    "DialogueAdaptation",
    "DialogueManager",
    "get_dialogue_manager",
]
