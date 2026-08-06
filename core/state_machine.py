"""
Core State Machine for JARVIS Voice Assistant.
Manages explicit state transitions and execution events.
"""

from enum import Enum
from typing import Callable, Dict, Optional, List
from logger import get_logger

logger = get_logger("Jarvis.StateMachine")

class StateEnum(Enum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    PROCESSING = "PROCESSING"
    EXECUTING = "EXECUTING"
    SPEAKING = "SPEAKING"
    CLARIFY = "CLARIFY"
    ERROR = "ERROR"

class StateMachine:
    """Explicit state machine managing assistant state transitions."""
    
    # Valid transitions from each state
    VALID_TRANSITIONS: Dict[StateEnum, List[StateEnum]] = {
        StateEnum.IDLE: [StateEnum.LISTENING, StateEnum.ERROR],
        StateEnum.LISTENING: [StateEnum.PROCESSING, StateEnum.IDLE, StateEnum.ERROR],
        StateEnum.PROCESSING: [StateEnum.EXECUTING, StateEnum.CLARIFY, StateEnum.ERROR, StateEnum.IDLE],
        StateEnum.EXECUTING: [StateEnum.SPEAKING, StateEnum.ERROR, StateEnum.IDLE],
        StateEnum.SPEAKING: [StateEnum.IDLE, StateEnum.LISTENING, StateEnum.ERROR],
        StateEnum.CLARIFY: [StateEnum.PROCESSING, StateEnum.IDLE, StateEnum.ERROR],
        StateEnum.ERROR: [StateEnum.PROCESSING, StateEnum.IDLE]
    }

    def __init__(self, initial_state: StateEnum = StateEnum.IDLE):
        self._current_state = initial_state
        self._on_transition_callbacks: List[Callable[[StateEnum, StateEnum], None]] = []
        logger.info(f"StateMachine initialized in state: {self._current_state.value}")

    @property
    def current_state(self) -> StateEnum:
        return self._current_state

    def add_transition_listener(self, callback: Callable[[StateEnum, StateEnum], None]):
        """Register a callback for state transition events."""
        self._on_transition_callbacks.append(callback)

    def transition_to(self, target_state: StateEnum, reason: Optional[str] = None) -> bool:
        """Transitions the machine to a new state if valid."""
        if target_state == self._current_state:
            return True

        allowed = self.VALID_TRANSITIONS.get(self._current_state, [])
        if target_state not in allowed:
            logger.error(
                f"Invalid state transition attempted: {self._current_state.value} -> {target_state.value}. "
                f"Reason: {reason or 'N/A'}"
            )
            return False

        old_state = self._current_state
        self._current_state = target_state
        logger.info(f"State Transition: {old_state.value} -> {target_state.value} ({reason or 'No reason provided'})")

        for callback in self._on_transition_callbacks:
            try:
                callback(old_state, target_state)
            except Exception as e:
                logger.error(f"Error in transition listener callback: {e}")

        return True
