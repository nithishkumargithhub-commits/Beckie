"""
JARVIS Test Suite – Unit tests for core modules.
Coverage targets: permission_broker, ollama_adapter, challenge_prompt, audit_logger, db/schema.
"""

from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

# ── Ensure project root is on path ────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ===========================================================================
# db/schema tests
# ===========================================================================
class TestSchemaInit:
    """Tests for encrypted DB schema initialisation."""

    def test_init_db_creates_all_tables(self, tmp_path: Path) -> None:
        from db.schema import init_db, get_db

        db_path = tmp_path / "test.db"
        init_db(db_path=db_path)

        with get_db(db_path=db_path) as conn:
            tables = {
                row["name"]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }

        expected = {
            "reminders", "meetings", "preferences", "oauth_tokens",
            "audit_logs", "conversation_history", "schema_version",
        }
        assert expected.issubset(tables), f"Missing tables: {expected - tables}"

    def test_schema_version_recorded(self, tmp_path: Path) -> None:
        from db.schema import init_db, get_db, CURRENT_SCHEMA_VERSION

        db_path = tmp_path / "test.db"
        init_db(db_path=db_path)

        with get_db(db_path=db_path) as conn:
            row = conn.execute(
                "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
            ).fetchone()

        assert row is not None
        assert row["version"] == CURRENT_SCHEMA_VERSION

    def test_init_db_idempotent(self, tmp_path: Path) -> None:
        """Calling init_db twice must not raise."""
        from db.schema import init_db

        db_path = tmp_path / "test.db"
        init_db(db_path=db_path)
        init_db(db_path=db_path)  # should not raise

    def test_reminder_insert_and_query(self, tmp_path: Path) -> None:
        from db.schema import init_db, get_db

        db_path = tmp_path / "test.db"
        init_db(db_path=db_path)

        with get_db(db_path=db_path) as conn:
            conn.execute(
                "INSERT INTO reminders (title, due_at) VALUES (?, ?)",
                ("Test reminder", "2026-01-01T09:00:00Z"),
            )

        with get_db(db_path=db_path) as conn:
            row = conn.execute("SELECT title FROM reminders").fetchone()

        assert row is not None
        assert row["title"] == "Test reminder"

    def test_audit_log_insert(self, tmp_path: Path) -> None:
        from db.schema import init_db, get_db

        db_path = tmp_path / "test.db"
        init_db(db_path=db_path)

        with get_db(db_path=db_path) as conn:
            conn.execute(
                """INSERT INTO audit_logs
                   (session_id, action_type, action_name, status)
                   VALUES (?, ?, ?, ?)""",
                ("sess1", "permission_check", "read_file", "auto_approved"),
            )

        with get_db(db_path=db_path) as conn:
            row = conn.execute("SELECT action_name, status FROM audit_logs").fetchone()

        assert row["action_name"] == "read_file"
        assert row["status"] == "auto_approved"

    def test_foreign_keys_enforced(self, tmp_path: Path) -> None:
        """PRAGMA foreign_keys=ON should be active."""
        from db.schema import get_db, init_db

        db_path = tmp_path / "test.db"
        init_db(db_path=db_path)

        with get_db(db_path=db_path) as conn:
            result = conn.execute("PRAGMA foreign_keys").fetchone()
        # Result is a dict with column name 'foreign_keys' or key '0'
        assert list(result.values())[0] == 1


# ===========================================================================
# core/permission_broker tests
# ===========================================================================
class TestPermissionBroker:

    def _make_broker(
        self,
        approval: bool = True,
        destructive: bool = False,
    ):
        from core.permission_broker import PermissionBroker

        return PermissionBroker(
            session_id="test-session",
            approval_cb=lambda name, tier, desc: approval,
            destructive_cb=lambda name, phrase: destructive,
        )

    def test_safe_tier_auto_approved(self) -> None:
        broker = self._make_broker()
        result = broker.request("get_time")
        assert result.granted is True
        assert result.user_approved is False
        assert result.tier.value == "safe"

    def test_read_tier_auto_approved(self) -> None:
        broker = self._make_broker()
        result = broker.request("read_file")
        assert result.granted is True
        assert result.user_approved is False
        assert result.tier.value == "read"

    def test_write_tier_approved_by_user(self) -> None:
        broker = self._make_broker(approval=True)
        result = broker.request("write_file")
        assert result.granted is True
        assert result.user_approved is True
        assert result.tier.value == "write"

    def test_write_tier_denied_by_user(self) -> None:
        broker = self._make_broker(approval=False)
        result = broker.request("write_file")
        assert result.granted is False
        assert result.tier.value == "write"

    def test_write_permission_cached_in_session(self) -> None:
        """Second request for same WRITE action skips re-prompting."""
        call_count = 0

        def counting_cb(name, tier, desc):
            nonlocal call_count
            call_count += 1
            return True

        from core.permission_broker import PermissionBroker
        broker = PermissionBroker(session_id="s1", approval_cb=counting_cb)
        broker.request("write_file")
        broker.request("write_file")

        assert call_count == 1  # only prompted once

    def test_destructive_tier_confirmed(self) -> None:
        broker = self._make_broker(destructive=True)
        result = broker.request("delete_file")
        assert result.granted is True
        assert result.tier.value == "destructive"

    def test_destructive_tier_rejected(self) -> None:
        broker = self._make_broker(destructive=False)
        result = broker.request("delete_file")
        assert result.granted is False

    def test_destructive_not_cached(self) -> None:
        """Destructive actions must always prompt; no session caching."""
        call_count = 0

        def counting_destructive(name, phrase):
            nonlocal call_count
            call_count += 1
            return True

        from core.permission_broker import PermissionBroker
        broker = PermissionBroker(session_id="s2", destructive_cb=counting_destructive)
        broker.request("delete_file")
        broker.request("delete_file")

        assert call_count == 2  # prompted every time

    def test_revoke_session_permissions(self) -> None:
        broker = self._make_broker(approval=True)
        broker.request("write_file")
        assert broker.is_granted("write_file")

        broker.revoke_session_permissions()
        assert not broker.is_granted("write_file")

    def test_custom_tier_registration(self) -> None:
        from core.permission_broker import PermissionBroker, PermissionTier
        broker = PermissionBroker(session_id="s3")
        broker.register_action("my_custom_action", PermissionTier.SAFE)
        assert broker.get_tier("my_custom_action") == PermissionTier.SAFE

    def test_unknown_action_defaults_to_write(self) -> None:
        from core.permission_broker import PermissionBroker, PermissionTier
        broker = PermissionBroker(session_id="s4")
        assert broker.get_tier("unknown_exotic_action") == PermissionTier.WRITE

    def test_status_summary(self) -> None:
        broker = self._make_broker(approval=True)
        broker.request("write_file")
        summary = broker.status_summary()
        assert "session_id" in summary
        assert "write_file" in summary["granted_write_actions"]

    def test_audit_callback_invoked(self) -> None:
        audit_records = []

        def audit_cb(result, extra):
            audit_records.append(result)

        from core.permission_broker import PermissionBroker
        broker = PermissionBroker(
            session_id="s5",
            approval_cb=lambda *a: True,
            audit_callback=audit_cb,
        )
        broker.request("read_file")
        assert len(audit_records) == 1
        assert audit_records[0].action_name == "read_file"


# ===========================================================================
# core/ollama_adapter tests
# ===========================================================================
class TestOllamaAdapter:

    def test_chat_message_to_dict(self) -> None:
        from core.ollama_adapter import ChatMessage
        msg = ChatMessage(role="user", content="hello")
        d = msg.to_dict()
        assert d["role"] == "user"
        assert d["content"] == "hello"
        assert "name" not in d  # name is None → omitted

    def test_chat_message_with_name(self) -> None:
        from core.ollama_adapter import ChatMessage
        msg = ChatMessage(role="tool", content="result", name="weather")
        d = msg.to_dict()
        assert d["name"] == "weather"

    def test_completion_usage_total(self) -> None:
        from core.ollama_adapter import CompletionUsage
        u = CompletionUsage(prompt_tokens=10, completion_tokens=20)
        assert u.total_tokens == 30

    def test_chat_completion_to_dict(self) -> None:
        from core.ollama_adapter import ChatCompletion, ChatMessage, CompletionChoice
        cc = ChatCompletion(
            id="test-id",
            model="qwen3:8b",
            choices=[
                CompletionChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content="Hi!"),
                )
            ],
        )
        d = cc.to_dict()
        assert d["id"] == "test-id"
        assert d["choices"][0]["message"]["content"] == "Hi!"

    def test_model_info_to_dict(self) -> None:
        from core.ollama_adapter import ModelInfo
        m = ModelInfo(id="qwen3:8b")
        d = m.to_dict()
        assert d["id"] == "qwen3:8b"
        assert d["object"] == "model"

    @patch("httpx.Client.get")
    def test_is_healthy_true(self, mock_get) -> None:
        from core.ollama_adapter import OllamaAdapter
        mock_get.return_value = Mock(status_code=200)
        adapter = OllamaAdapter()
        assert adapter.is_healthy() is True

    @patch("httpx.Client.get", side_effect=Exception("Connection refused"))
    def test_is_healthy_false_on_exception(self, mock_get) -> None:
        from core.ollama_adapter import OllamaAdapter
        adapter = OllamaAdapter()
        assert adapter.is_healthy() is False

    @patch("httpx.Client.get")
    def test_list_models(self, mock_get) -> None:
        from core.ollama_adapter import OllamaAdapter
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "models": [{"name": "qwen3:8b"}, {"name": "phi3:mini"}]
        }
        mock_resp.raise_for_status = Mock()
        mock_get.return_value = mock_resp
        adapter = OllamaAdapter()
        models = adapter.list_models()
        assert len(models) == 2
        assert models[0].id == "qwen3:8b"

    @patch("httpx.Client.post")
    def test_blocking_chat(self, mock_post) -> None:
        from core.ollama_adapter import ChatMessage, OllamaAdapter
        mock_resp = Mock()
        mock_resp.raise_for_status = Mock()
        mock_resp.json.return_value = {
            "message": {"role": "assistant", "content": "Hello there!"},
            "done": True,
            "prompt_eval_count": 5,
            "eval_count": 3,
        }
        mock_post.return_value = mock_resp
        adapter = OllamaAdapter()
        result = adapter.chat(
            messages=[ChatMessage(role="user", content="Hi")],
            model="qwen3:8b",
        )
        assert result.choices[0].message.content == "Hello there!"
        assert result.usage.total_tokens == 8

    @patch("httpx.Client.post")
    def test_generate(self, mock_post) -> None:
        from core.ollama_adapter import OllamaAdapter
        mock_resp = Mock()
        mock_resp.raise_for_status = Mock()
        mock_resp.json.return_value = {"response": "  test output  "}
        mock_post.return_value = mock_resp
        adapter = OllamaAdapter()
        result = adapter.generate("Test prompt")
        assert result == "test output"

    def test_get_adapter_singleton(self) -> None:
        from core.ollama_adapter import get_adapter
        import core.ollama_adapter as oa
        oa._adapter = None  # reset
        a1 = get_adapter()
        a2 = get_adapter()
        assert a1 is a2


# ===========================================================================
# core/challenge_prompt tests
# ===========================================================================
class TestChallengePrompt:

    def test_build_returns_string(self) -> None:
        from core.challenge_prompt import ChallengePromptBuilder
        builder = ChallengePromptBuilder()
        prompt = builder.build(session_id="test-sess")
        assert isinstance(prompt, str)
        assert len(prompt) > 100

    def test_build_contains_session_id(self) -> None:
        from core.challenge_prompt import ChallengePromptBuilder
        builder = ChallengePromptBuilder()
        prompt = builder.build(session_id="my-session-123")
        assert "my-session-123" in prompt

    def test_build_contains_persona_name(self) -> None:
        from core.challenge_prompt import ChallengePromptBuilder, PersonaConfig
        builder = ChallengePromptBuilder(PersonaConfig(name="ALFRED"))
        prompt = builder.build(session_id="s1")
        assert "ALFRED" in prompt

    def test_balanced_challenge_level(self) -> None:
        from core.challenge_prompt import ChallengePromptBuilder, PersonaConfig
        builder = ChallengePromptBuilder(PersonaConfig(challenge_level="balanced"))
        prompt = builder.build(session_id="s1")
        assert "Factual accuracy" in prompt or "calibrated" in prompt.lower()

    def test_assertive_challenge_level(self) -> None:
        from core.challenge_prompt import ChallengePromptBuilder, PersonaConfig
        builder = ChallengePromptBuilder(PersonaConfig(challenge_level="assertive"))
        prompt = builder.build(session_id="s1")
        assert "disagree" in prompt.lower() or "Actively challenge" in prompt

    def test_granted_actions_injected(self) -> None:
        from core.challenge_prompt import ChallengePromptBuilder
        builder = ChallengePromptBuilder()
        prompt = builder.build(
            session_id="s1",
            granted_actions=["write_file", "send_email"],
        )
        assert "write_file" in prompt
        assert "send_email" in prompt

    def test_extra_context_injected(self) -> None:
        from core.challenge_prompt import ChallengePromptBuilder
        builder = ChallengePromptBuilder()
        prompt = builder.build(session_id="s1", extra_context="You have 3 meetings today.")
        assert "3 meetings today" in prompt

    def test_build_messages_format(self) -> None:
        from core.challenge_prompt import ChallengePromptBuilder
        builder = ChallengePromptBuilder()
        msgs = builder.build_messages(session_id="s1")
        assert len(msgs) == 1
        assert msgs[0]["role"] == "system"
        assert len(msgs[0]["content"]) > 50

    def test_get_prompt_builder_singleton(self) -> None:
        from core.challenge_prompt import get_prompt_builder
        import core.challenge_prompt as cp
        cp._builder = None
        b1 = get_prompt_builder()
        b2 = get_prompt_builder()
        assert b1 is b2


# ===========================================================================
# core/audit_logger tests
# ===========================================================================
class TestAuditLogger:

    def test_log_enqueues_without_blocking(self, tmp_path: Path) -> None:
        from db.schema import init_db
        from core.audit_logger import AuditLogger

        db_path = tmp_path / "audit.db"
        init_db(db_path=db_path)

        al = AuditLogger(db_path=db_path, session_id="test-sess")
        # Log 10 records rapidly
        for i in range(10):
            al.log(
                action_type="permission_check",
                action_name=f"action_{i}",
                status="auto_approved",
            )
        al.flush(timeout=3.0)
        al.stop()

        records = al.recent(limit=20)
        assert len(records) >= 10

    def test_log_permission_granted(self, tmp_path: Path) -> None:
        from db.schema import init_db
        from core.audit_logger import AuditLogger

        db_path = tmp_path / "audit.db"
        init_db(db_path=db_path)

        al = AuditLogger(db_path=db_path, session_id="s1")
        al.log_permission("write_file", "write", granted=True, user_approved=True)
        al.flush(timeout=3.0)
        al.stop()

        records = al.recent(limit=5)
        assert any(r["action_name"] == "write_file" for r in records)

    def test_log_permission_denied_status(self, tmp_path: Path) -> None:
        from db.schema import init_db
        from core.audit_logger import AuditLogger

        db_path = tmp_path / "audit.db"
        init_db(db_path=db_path)

        al = AuditLogger(db_path=db_path, session_id="s2")
        al.log_permission("delete_file", "destructive", granted=False)
        al.flush(timeout=3.0)
        al.stop()

        records = al.recent(limit=5)
        match = next((r for r in records if r["action_name"] == "delete_file"), None)
        assert match is not None
        assert match["status"] == "denied"

    def test_sanitise_resource_strips_token(self) -> None:
        from core.audit_logger import AuditLogger
        result = AuditLogger._sanitise_resource("https://example.com?token=abc123&foo=bar")
        assert "abc123" not in result
        assert "***" in result

    def test_sanitise_resource_none(self) -> None:
        from core.audit_logger import AuditLogger
        assert AuditLogger._sanitise_resource(None) is None

    def test_session_summary(self, tmp_path: Path) -> None:
        from db.schema import init_db
        from core.audit_logger import AuditLogger

        db_path = tmp_path / "audit.db"
        init_db(db_path=db_path)

        al = AuditLogger(db_path=db_path, session_id="sum-sess")
        al.log("llm_query", "chat_completion", "completed", duration_ms=150)
        al.flush(timeout=3.0)
        al.stop()

        summary = al.session_summary("sum-sess")
        assert summary["session_id"] == "sum-sess"
        assert "breakdown" in summary


# ===========================================================================
# Security tests
# ===========================================================================
class TestSecurity:

    def test_no_hardcoded_secrets_in_schema(self) -> None:
        """Verify db/schema.py contains no hardcoded passwords or API keys."""
        schema_path = PROJECT_ROOT / "db" / "schema.py"
        content = schema_path.read_text(encoding="utf-8").lower()
        forbidden = ["password=", "api_key=", "secret=", "token=", "passphrase="]
        for f in forbidden:
            assert f not in content, f"Possible hardcoded secret: '{f}' in schema.py"

    def test_key_store_generates_unique_keys(self, tmp_path: Path) -> None:
        """Two different key stores should produce different keys."""
        from db.schema import KeyStore

        ks1 = KeyStore(tmp_path / "k1.enc")
        ks2 = KeyStore(tmp_path / "k2.enc")

        # On non-Windows, falls back to raw bytes
        k1 = ks1.ensure_key()
        k2 = ks2.ensure_key()
        assert k1 != k2

    def test_key_store_stable_across_calls(self, tmp_path: Path) -> None:
        from db.schema import KeyStore

        ks = KeyStore(tmp_path / "k.enc")
        k1 = ks.ensure_key()
        k2 = ks.ensure_key()
        assert k1 == k2  # Same key file → same passphrase

    def test_destructive_tier_requires_confirmation_every_time(self) -> None:
        """DESTRUCTIVE permissions must NEVER be cached."""
        from core.permission_broker import PermissionBroker

        calls = []

        def track_confirm(name, phrase):
            calls.append(name)
            return True

        broker = PermissionBroker(session_id="sec-test", destructive_cb=track_confirm)
        broker.request("delete_file")
        broker.request("delete_file")
        broker.request("execute_shell")

        assert len(calls) == 3  # no caching

    def test_audit_resource_capped_at_512_chars(self) -> None:
        from core.audit_logger import AuditLogger
        long_resource = "https://example.com/" + "x" * 600
        result = AuditLogger._sanitise_resource(long_resource)
        assert len(result) <= 512

    def test_permission_broker_thread_safety(self) -> None:
        """Concurrent requests should not corrupt the granted set."""
        import threading
        from core.permission_broker import PermissionBroker

        broker = PermissionBroker(
            session_id="thread-test",
            approval_cb=lambda *a: True,
        )
        results = []
        errors = []

        def do_request():
            try:
                r = broker.request("write_file")
                results.append(r.granted)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=do_request) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert all(results)  # all granted


# ===========================================================================
# Integration: permission broker + audit logger
# ===========================================================================
class TestIntegration:

    def test_permission_result_written_to_audit(self, tmp_path: Path) -> None:
        """Check that broker results flow to the audit logger correctly."""
        from db.schema import init_db
        from core.audit_logger import AuditLogger
        from core.permission_broker import PermissionBroker

        db_path = tmp_path / "int.db"
        init_db(db_path=db_path)

        al = AuditLogger(db_path=db_path, session_id="int-sess")

        def audit_cb(perm_result, extra):
            al.log_permission(
                action_name=perm_result.action_name,
                tier=perm_result.tier.value,
                granted=perm_result.granted,
                user_approved=perm_result.user_approved,
                resource=extra.get("resource"),
            )

        broker = PermissionBroker(
            session_id="int-sess",
            approval_cb=lambda *a: True,
            audit_callback=audit_cb,
        )

        broker.request("write_file", resource="/home/user/docs/report.pdf")
        broker.request("read_file", resource="/home/user/notes.txt")

        al.flush(timeout=3.0)
        al.stop()

        records = al.recent(limit=10)
        names = {r["action_name"] for r in records}
        assert "write_file" in names
        assert "read_file" in names


# ===========================================================================
# Additional coverage boosters – edge cases and error paths
# ===========================================================================

class TestOllamaAdapterEdgeCases:

    @patch("httpx.Client.post")
    def test_blocking_chat_not_done_sets_length_finish(self, mock_post) -> None:
        from core.ollama_adapter import ChatMessage, OllamaAdapter
        mock_resp = Mock()
        mock_resp.raise_for_status = Mock()
        mock_resp.json.return_value = {
            "message": {"role": "assistant", "content": "partial"},
            "done": False,
            "prompt_eval_count": 0,
            "eval_count": 0,
        }
        mock_post.return_value = mock_resp
        adapter = OllamaAdapter()
        result = adapter.chat([ChatMessage(role="user", content="Hi")])
        assert result.choices[0].finish_reason == "length"

    @patch("httpx.Client.post", side_effect=Exception("conn refused"))
    def test_generate_raises_on_error(self, mock_post) -> None:
        from core.ollama_adapter import OllamaAdapter
        adapter = OllamaAdapter()
        with pytest.raises(Exception, match="conn refused"):
            adapter.generate("test")

    @patch("httpx.Client.get")
    def test_list_models_empty_on_error(self, mock_get) -> None:
        from core.ollama_adapter import OllamaAdapter
        mock_resp = Mock()
        mock_resp.raise_for_status.side_effect = Exception("net error")
        mock_get.return_value = mock_resp
        adapter = OllamaAdapter()
        assert adapter.list_models() == []

    def test_completion_usage_dict(self) -> None:
        from core.ollama_adapter import CompletionUsage
        u = CompletionUsage(prompt_tokens=7, completion_tokens=13)
        d = u.to_dict()
        assert d["total_tokens"] == 20

    @patch("httpx.Client.post")
    def test_blocking_chat_http_error(self, mock_post) -> None:
        import httpx
        from core.ollama_adapter import ChatMessage, OllamaAdapter
        mock_resp = Mock()
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500", request=Mock(), response=Mock(text="err", status_code=500)
        )
        mock_post.return_value = mock_resp
        adapter = OllamaAdapter()
        with pytest.raises(httpx.HTTPStatusError):
            adapter.chat([ChatMessage(role="user", content="hi")])


class TestAuditLoggerEdgeCases:

    def test_log_file_op_write(self, tmp_path: Path) -> None:
        from db.schema import init_db
        from core.audit_logger import AuditLogger
        db_path = tmp_path / "a.db"
        init_db(db_path=db_path)
        al = AuditLogger(db_path=db_path, session_id="fop")
        al.log_file_op("write_file", "/docs/r.pdf", "approved", user_approved=True)
        al.flush(timeout=3.0)
        al.stop()
        assert any(r["action_name"] == "write_file" for r in al.recent(5))

    def test_log_system_event(self, tmp_path: Path) -> None:
        from db.schema import init_db
        from core.audit_logger import AuditLogger
        db_path = tmp_path / "b.db"
        init_db(db_path=db_path)
        al = AuditLogger(db_path=db_path, session_id="sys")
        al.log_system("startup", details={"v": "1.0"})
        al.flush(timeout=3.0)
        al.stop()
        assert any(r["action_name"] == "startup" for r in al.recent(5))

    def test_log_oauth(self, tmp_path: Path) -> None:
        from db.schema import init_db
        from core.audit_logger import AuditLogger
        db_path = tmp_path / "c.db"
        init_db(db_path=db_path)
        al = AuditLogger(db_path=db_path, session_id="oauth")
        al.log_oauth("google", "refresh", "completed", account="u@e.com")
        al.flush(timeout=3.0)
        al.stop()
        assert any("google" in r["action_name"] for r in al.recent(5))

    def test_log_llm_query_error_status(self, tmp_path: Path) -> None:
        from db.schema import init_db
        from core.audit_logger import AuditLogger
        db_path = tmp_path / "d.db"
        init_db(db_path=db_path)
        al = AuditLogger(db_path=db_path, session_id="llm")
        al.log_llm_query(0, 0, "qwen3:8b", 500, status="error")
        al.flush(timeout=3.0)
        al.stop()
        assert any(r["status"] == "error" for r in al.recent(5))

    def test_get_audit_logger_singleton(self) -> None:
        from core.audit_logger import get_audit_logger
        import core.audit_logger as al_mod
        al_mod._logger_instance = None
        a1 = get_audit_logger()
        a2 = get_audit_logger()
        assert a1 is a2
        a1.stop()
        al_mod._logger_instance = None


class TestSchemaKeyStore:

    def test_key_store_creates_file(self, tmp_path: Path) -> None:
        from db.schema import KeyStore
        ks = KeyStore(tmp_path / "sub" / "key.enc")
        key = ks.ensure_key()
        assert len(key) == 64
        assert (tmp_path / "sub" / "key.enc").exists()

    def test_challenge_prompt_minimal_level(self) -> None:
        from core.challenge_prompt import ChallengePromptBuilder, PersonaConfig
        builder = ChallengePromptBuilder(PersonaConfig(challenge_level="minimal"))
        prompt = builder.build(session_id="s-minimal")
        assert "not sure" in prompt.lower() or "I'm not" in prompt

    def test_challenge_prompt_no_granted_actions(self) -> None:
        from core.challenge_prompt import ChallengePromptBuilder
        builder = ChallengePromptBuilder()
        prompt = builder.build(session_id="s-empty", granted_actions=[])
        assert "No WRITE actions" in prompt
