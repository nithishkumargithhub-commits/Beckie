"""
JARVIS – Tests for FastAPI Ollama router and application (test_api.py).

Tests:
  - GET  /                           – root metadata
  - GET  /v1/health                  – healthy and degraded status
  - GET  /v1/models                  – OpenAI /v1/models format
  - POST /v1/chat/completions        – non-streaming chat completions
  - POST /v1/chat/completions        – streaming SSE chat completions
  - POST /v1/chat/completions        – permission denied returns 403
  - GET  /v1/audit                   – recent audit records
  - GET  /v1/audit/session           – session summary stats
  - GET  /v1/permissions/status      – session permission summary
  - POST /v1/permissions/revoke      – revoking write grants
  - Error cases: missing dependencies return 503
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app import create_app
from core.audit_logger import AuditLogger
from core.ollama_adapter import (
    ChatCompletion,
    ChatMessage,
    CompletionChoice,
    CompletionUsage,
    ModelInfo,
)
from core.permission_broker import PermissionBroker, PermissionResult, PermissionTier


@pytest.fixture
def mock_ollama_adapter():
    adapter = MagicMock()
    adapter.is_healthy_async = AsyncMock(return_value=True)
    adapter.list_models = MagicMock(return_value=[
        ModelInfo(id="qwen3:8b"),
        ModelInfo(id="gemma2:2b"),
    ])

    dummy_response = ChatCompletion(
        id="chatcmpl-test123456",
        created=1727180000,
        model="qwen3:8b",
        choices=[CompletionChoice(
            index=0,
            message=ChatMessage(role="assistant", content="I am JARVIS, ready to assist."),
            finish_reason="stop",
        )],
        usage=CompletionUsage(prompt_tokens=15, completion_tokens=8),
    )
    adapter.chat_async = AsyncMock(return_value=dummy_response)
    adapter.close = MagicMock()
    return adapter


@pytest.fixture
def test_client(tmp_db, session_id, mock_ollama_adapter):
    """Create a TestClient with app state initialized with isolated test components."""
    app = create_app()

    audit = AuditLogger(session_id=session_id, db_path=tmp_db)
    broker = PermissionBroker(session_id=session_id)

    app.state.ollama_adapter = mock_ollama_adapter
    app.state.audit_logger = audit
    app.state.permission_broker = broker

    client = TestClient(app)
    try:
        yield client
    finally:
        audit.flush(timeout=1.0)
        audit.stop()


class TestAPIRootAndHealth:
    def test_root_endpoint(self, test_client):
        resp = test_client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["service"] == "JARVIS"
        assert data["version"] == "1.0.0"
        assert "session_id" in data

    def test_health_healthy(self, test_client):
        resp = test_client.get("/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["ollama"] is True
        assert data["models_available"] == 2
        assert len(data["models"]) == 2

    def test_health_degraded(self, test_client, mock_ollama_adapter):
        mock_ollama_adapter.is_healthy_async = AsyncMock(return_value=False)
        resp = test_client.get("/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["ollama"] is False
        assert data["models_available"] == 0


class TestAPIModels:
    def test_list_models_openai_format(self, test_client):
        resp = test_client.get("/v1/models")
        assert resp.status_code == 200
        data = resp.json()
        assert data["object"] == "list"
        assert len(data["data"]) == 2
        assert data["data"][0]["id"] == "qwen3:8b"
        assert data["data"][1]["id"] == "gemma2:2b"


class TestAPIChatCompletions:
    def test_chat_completion_non_streaming(self, test_client):
        payload = {
            "model": "qwen3:8b",
            "messages": [
                {"role": "user", "content": "What is 2 + 2?"}
            ],
            "temperature": 0.5,
            "max_tokens": 100,
            "stream": False,
        }
        resp = test_client.post("/v1/chat/completions", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "chatcmpl-test123456"
        assert data["choices"][0]["message"]["content"] == "I am JARVIS, ready to assist."
        assert data["usage"]["total_tokens"] == 23

    def test_chat_completion_streaming(self, test_client, mock_ollama_adapter):
        async def mock_stream_gen(*args, **kwargs):
            yield "Hello"
            yield " from"
            yield " JARVIS"

        mock_ollama_adapter.chat_async = AsyncMock(side_effect=mock_stream_gen)

        payload = {
            "model": "qwen3:8b",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": True,
        }
        resp = test_client.post("/v1/chat/completions", json=payload)
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

        body = resp.text
        assert "data: " in body
        assert "JARVIS" in body
        assert "data: [DONE]" in body

    def test_chat_completion_permission_denied(self, test_client):
        # Swap broker with one that denies chat_completion
        deny_broker = MagicMock()
        deny_broker.request.return_value = PermissionResult(
            tier=PermissionTier.READ,
            action_name="chat_completion",
            session_id="test-session",
            granted=False,
            user_approved=False,
            reason="Blocked by policy",
        )
        test_client.app.state.permission_broker = deny_broker

        payload = {
            "messages": [{"role": "user", "content": "Hello"}]
        }
        resp = test_client.post("/v1/chat/completions", json=payload)
        assert resp.status_code == 403
        assert "denied by PermissionBroker" in resp.json()["detail"]


class TestAPIAuditAndPermissions:
    def test_audit_tail(self, test_client):
        resp = test_client.get("/v1/audit?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert "records" in data
        assert isinstance(data["records"], list)

    def test_audit_session_summary(self, test_client):
        resp = test_client.get("/v1/audit/session")
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data
        assert "breakdown" in data

    def test_permissions_status(self, test_client):
        resp = test_client.get("/v1/permissions/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data
        assert "granted_write_actions" in data

    def test_permissions_revoke(self, test_client):
        resp = test_client.post("/v1/permissions/revoke", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "revoked"
        assert "session_id" in data


class TestAPIMissingDependencies:
    def test_missing_adapter_returns_503(self, test_client):
        test_client.app.state.ollama_adapter = None
        resp = test_client.get("/v1/health")
        assert resp.status_code == 503

    def test_missing_audit_logger_returns_503(self, test_client):
        test_client.app.state.audit_logger = None
        resp = test_client.get("/v1/audit")
        assert resp.status_code == 503

    def test_missing_broker_returns_503(self, test_client):
        test_client.app.state.permission_broker = None
        resp = test_client.get("/v1/permissions/status")
        assert resp.status_code == 503
