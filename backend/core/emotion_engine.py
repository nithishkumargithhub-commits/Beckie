"""
Re-export of core.emotion_engine under backend.core.emotion_engine namespace.
"""

from core.emotion_engine import (
    DEFAULT_MODEL,
    DEFAULT_SMOOTHING_ALPHA,
    DEFAULT_WINDOW_SIZE,
    EmotionEngine,
    EmotionState,
    ProsodyExtractor,
    ProsodyFeatures,
    get_emotion_engine,
)

__all__ = [
    "DEFAULT_MODEL",
    "DEFAULT_SMOOTHING_ALPHA",
    "DEFAULT_WINDOW_SIZE",
    "EmotionEngine",
    "EmotionState",
    "ProsodyExtractor",
    "ProsodyFeatures",
    "get_emotion_engine",
]
