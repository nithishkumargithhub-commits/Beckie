"""
Unit tests for ActionExecutor intent routing and responses.
"""

import pytest
from core.intent_classifier import IntentAnalysis, IntentEnum
from pipeline.action_executor import ActionExecutor

@pytest.fixture
def executor():
    return ActionExecutor()

def test_greeting_action(executor):
    analysis = IntentAnalysis(intent=IntentEnum.GREETING, target="hello")
    response = executor.execute(analysis)
    assert isinstance(response, str)
    assert len(response) > 0

def test_time_date_action(executor):
    analysis = IntentAnalysis(intent=IntentEnum.TIME_DATE, target="")
    response = executor.execute(analysis)
    assert "currently" in response or "20" in response or ":" in response

def test_joke_action(executor):
    analysis = IntentAnalysis(intent=IntentEnum.TELL_JOKE, target="")
    response = executor.execute(analysis)
    assert isinstance(response, str)
    assert len(response) > 0
