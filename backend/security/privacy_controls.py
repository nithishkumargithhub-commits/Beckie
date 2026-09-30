"""
Re-export of security.privacy_controls under backend.security.privacy_controls namespace.
"""

from security.privacy_controls import (
    EmotionPrivacyManager,
    EmotionPrivacySettings,
    get_privacy_manager,
)

__all__ = [
    "EmotionPrivacyManager",
    "EmotionPrivacySettings",
    "get_privacy_manager",
]
