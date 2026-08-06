"""
Unit tests for IntentClassifier rule-based fallback and schema validation.
"""

import pytest
from core.intent_classifier import IntentClassifier, IntentEnum

@pytest.fixture
def classifier():
    return IntentClassifier()

def test_greeting_intent(classifier):
    analysis = classifier.classify("hello there")
    assert analysis.intent == IntentEnum.GREETING

def test_time_date_intent(classifier):
    analysis = classifier.classify("what time is it")
    assert analysis.intent == IntentEnum.TIME_DATE

def test_weather_intent(classifier):
    analysis = classifier.classify("what is the weather today")
    assert analysis.intent == IntentEnum.GET_WEATHER

def test_open_app_intent(classifier):
    analysis = classifier.classify("open chrome")
    assert analysis.intent == IntentEnum.OPEN_APP
    assert "chrome" in analysis.target.lower()

def test_close_app_intent(classifier):
    analysis = classifier.classify("close notepad")
    assert analysis.intent == IntentEnum.CLOSE_APP
    assert "notepad" in analysis.target.lower()

def test_web_search_intent(classifier):
    analysis = classifier.classify("search for python tutorials")
    assert analysis.intent == IntentEnum.WEB_SEARCH
    assert "python tutorials" in analysis.target.lower()
