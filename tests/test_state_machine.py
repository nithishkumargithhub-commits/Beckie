"""
Unit tests for Core StateMachine transitions and callbacks.
"""

import pytest
from core.state_machine import StateMachine, StateEnum

def test_initial_state():
    sm = StateMachine(initial_state=StateEnum.IDLE)
    assert sm.current_state == StateEnum.IDLE

def test_valid_transitions():
    sm = StateMachine(initial_state=StateEnum.IDLE)
    assert sm.transition_to(StateEnum.LISTENING, reason="User spoke wake word") is True
    assert sm.current_state == StateEnum.LISTENING

    assert sm.transition_to(StateEnum.PROCESSING, reason="Speech captured") is True
    assert sm.current_state == StateEnum.PROCESSING

    assert sm.transition_to(StateEnum.EXECUTING, reason="Intent classified") is True
    assert sm.current_state == StateEnum.EXECUTING

    assert sm.transition_to(StateEnum.SPEAKING, reason="Action executed") is True
    assert sm.current_state == StateEnum.SPEAKING

    assert sm.transition_to(StateEnum.IDLE, reason="TTS finished") is True
    assert sm.current_state == StateEnum.IDLE

def test_invalid_transitions():
    sm = StateMachine(initial_state=StateEnum.IDLE)
    # Attempting IDLE -> EXECUTING directly should fail
    assert sm.transition_to(StateEnum.EXECUTING, reason="Direct jump") is False
    assert sm.current_state == StateEnum.IDLE

def test_transition_listener():
    sm = StateMachine(initial_state=StateEnum.IDLE)
    events = []

    def on_transition(old_s, new_s):
        events.append((old_s, new_s))

    sm.add_transition_listener(on_transition)
    sm.transition_to(StateEnum.LISTENING)

    assert len(events) == 1
    assert events[0] == (StateEnum.IDLE, StateEnum.LISTENING)
