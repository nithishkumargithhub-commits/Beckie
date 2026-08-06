"""
Custom domain-specific exceptions for JARVIS Voice Assistant.
"""

class JarvisException(Exception):
    """Base exception for all JARVIS errors."""
    pass

class STTException(JarvisException):
    """Raised when Speech-to-Text fails."""
    pass

class TTSException(JarvisException):
    """Raised when Text-to-Speech fails."""
    pass

class IntentClassificationException(JarvisException):
    """Raised when NLU intent classification fails."""
    pass

class ActionExecutionException(JarvisException):
    """Raised when an action handler fails to execute."""
    pass

class ConfigurationException(JarvisException):
    """Raised when configuration or environment variables are missing."""
    pass
