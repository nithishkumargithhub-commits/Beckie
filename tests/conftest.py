"""
JARVIS – pytest fixtures (conftest.py).

Available fixtures:
  tmp_db          – fresh in-memory-equivalent SQLite DB (temp file)
  db_path         – Path to the temp DB file
  audit_logger    – AuditLogger bound to tmp_db
  permission_broker – PermissionBroker with stub approval callbacks
  auto_broker     – PermissionBroker that auto-approves everything
  deny_broker     – PermissionBroker that always denies WRITE/DESTRUCTIVE
  prompt_builder  – ChallengePromptBuilder with balanced challenge level
  mock_adapter    – OllamaAdapter with httpx mocked out
  session_id      – Consistent test session UUID
  logging_cfg     – Configures logging for tests

All fixtures that open DB connections clean up after themselves.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Generator
from unittest.mock import Mock, patch

import pytest

# ── Project root ──────────────────────────────────────────────────────────────
import sys
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def logging_cfg() -> None:
    """Configure logging for the entire test session."""
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    # Silence noisy third-party loggers
    for name in ("httpx", "httpcore", "urllib3"):
        logging.getLogger(name).setLevel(logging.WARNING)


# ---------------------------------------------------------------------------
# Session ID
# ---------------------------------------------------------------------------

@pytest.fixture
def session_id() -> str:
    """Return a fresh UUID hex string for each test."""
    return uuid.uuid4().hex[:12]


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Unique temp DB path per test."""
    return tmp_path / "jarvis_test.db"


@pytest.fixture
def tmp_db(db_path: Path) -> Generator[Path, None, None]:
    """
    Initialised, isolated SQLite database for each test.
    Yields the Path; the file is automatically removed when tmp_path is cleaned.
    """
    from db.schema import init_db
    init_db(db_path=db_path)
    yield db_path
    # tmp_path cleanup handled by pytest


@pytest.fixture
def db_conn(tmp_db: Path):
    """
    Open a context-managed DB connection to tmp_db.
    Yields the connection; commits + closes after test.
    """
    from db.schema import get_db
    with get_db(db_path=tmp_db) as conn:
        yield conn


# ---------------------------------------------------------------------------
# Permission broker fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def permission_broker(session_id: str):
    """
    PermissionBroker with non-interactive stubs:
      - WRITE  → always approved
      - DESTRUCTIVE → always confirmed
    """
    from core.permission_broker import PermissionBroker

    return PermissionBroker(
        session_id=session_id,
        approval_cb=lambda action, tier, desc: True,
        destructive_cb=lambda action, phrase: True,
    )


@pytest.fixture
def auto_broker(session_id: str):
    """PermissionBroker that auto-approves every tier silently."""
    from core.permission_broker import PermissionBroker, PermissionTier

    broker = PermissionBroker(
        session_id=session_id,
        approval_cb=lambda *_: True,
        destructive_cb=lambda *_: True,
    )
    return broker


@pytest.fixture
def deny_broker(session_id: str):
    """PermissionBroker that denies all WRITE and DESTRUCTIVE requests."""
    from core.permission_broker import PermissionBroker

    return PermissionBroker(
        session_id=session_id,
        approval_cb=lambda *_: False,
        destructive_cb=lambda *_: False,
    )


# ---------------------------------------------------------------------------
# AuditLogger fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def audit_logger(tmp_db: Path, session_id: str):
    """
    AuditLogger backed by tmp_db.
    Stops the background writer after each test.
    """
    from core.audit_logger import AuditLogger

    al = AuditLogger(db_path=tmp_db, session_id=session_id)
    yield al
    al.flush(timeout=3.0)
    al.stop()


# ---------------------------------------------------------------------------
# Challenge prompt builder
# ---------------------------------------------------------------------------

@pytest.fixture
def prompt_builder():
    """ChallengePromptBuilder with default balanced persona."""
    from core.challenge_prompt import ChallengePromptBuilder, PersonaConfig

    return ChallengePromptBuilder(PersonaConfig(challenge_level="balanced"))


@pytest.fixture(params=["minimal", "balanced", "assertive"])
def prompt_builder_all_levels(request):
    """Parametrised prompt builder covering all 3 challenge levels."""
    from core.challenge_prompt import ChallengePromptBuilder, PersonaConfig

    return ChallengePromptBuilder(PersonaConfig(challenge_level=request.param))


# ---------------------------------------------------------------------------
# Ollama adapter fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_ollama_response() -> dict:
    """A realistic Ollama /api/chat response dict."""
    return {
        "message": {"role": "assistant", "content": "Hello! How can I help?"},
        "done": True,
        "prompt_eval_count": 12,
        "eval_count": 8,
    }


@pytest.fixture
def mock_adapter(mock_ollama_response: dict):
    """
    OllamaAdapter with httpx.Client.post mocked to return mock_ollama_response.
    Use this for any test that doesn't need a live Ollama server.
    """
    from core.ollama_adapter import OllamaAdapter

    mock_resp = Mock()
    mock_resp.raise_for_status = Mock()
    mock_resp.json.return_value = mock_ollama_response
    mock_resp.status_code = 200

    mock_get = Mock()
    mock_get.return_value = Mock(status_code=200)

    with patch("httpx.Client.post", return_value=mock_resp), \
         patch("httpx.Client.get", return_value=mock_get.return_value):
        adapter = OllamaAdapter(base_url="http://127.0.0.1:11434")
        yield adapter


@pytest.fixture
def offline_adapter():
    """OllamaAdapter where every HTTP call raises ConnectionError (simulates offline)."""
    from core.ollama_adapter import OllamaAdapter

    with patch("httpx.Client.get", side_effect=ConnectionError("offline")), \
         patch("httpx.Client.post", side_effect=ConnectionError("offline")):
        adapter = OllamaAdapter()
        yield adapter


# ---------------------------------------------------------------------------
# Decorator fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def audit_records(tmp_db: Path, session_id: str) -> list:
    """
    Collects audit records emitted during a test via the AuditLogger singleton.
    Returns the list (populated in-place by the audit logger during the test).
    """
    import core.audit_logger as al_mod
    from core.audit_logger import AuditLogger

    records: list = []

    class CapturingLogger(AuditLogger):
        def log(self, *args, **kwargs):  # type: ignore[override]
            records.append({"args": args, "kwargs": kwargs})
            super().log(*args, **kwargs)

    old_instance = al_mod._logger_instance
    al_mod._logger_instance = CapturingLogger(db_path=tmp_db, session_id=session_id)
    yield records
    al_mod._logger_instance.flush(timeout=2.0)
    al_mod._logger_instance.stop()
    al_mod._logger_instance = old_instance


# ---------------------------------------------------------------------------
# CLI argument helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def cli_args_base():
    """Base argparse.Namespace with default CLI flags."""
    import argparse
    ns = argparse.Namespace()
    ns.color = False          # no ANSI in tests
    ns.url = "http://127.0.0.1:11434"
    ns.log_level = "WARNING"
    ns.command = None
    return ns


@pytest.fixture
def cli_health_args(cli_args_base):
    cli_args_base.command = "health"
    return cli_args_base


@pytest.fixture
def cli_ask_args(cli_args_base):
    cli_args_base.command = "ask"
    cli_args_base.question = "What is 2 + 2?"
    cli_args_base.model = "qwen3:8b"
    cli_args_base.temperature = 0.7
    cli_args_base.challenge = "balanced"
    return cli_args_base


@pytest.fixture
def cli_audit_args(cli_args_base):
    cli_args_base.command = "audit"
    cli_args_base.limit = 10
    cli_args_base.type = None
    return cli_args_base


@pytest.fixture
def cli_permissions_args(cli_args_base):
    cli_args_base.command = "permissions"
    cli_args_base.revoke = False
    return cli_args_base


@pytest.fixture
def cli_db_args(cli_args_base):
    cli_args_base.command = "db"
    cli_args_base.init = False
    cli_args_base.tables = False
    return cli_args_base
