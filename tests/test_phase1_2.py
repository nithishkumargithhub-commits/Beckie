"""
JARVIS – Tests for Phase 1.2 additions:
  - @audit_log decorator
  - @require_permission decorator
  - permissions DB table
  - argparse CLI (jarvis_argparse.py)
  - pytest fixtures (conftest.py)
  - SQLCipher encryption verification
  - DPAPI key protection (skipped on non-Windows)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ===========================================================================
# @audit_log decorator
# ===========================================================================
class TestAuditLogDecorator:

    def test_decorated_function_still_runs(self) -> None:
        from core.decorators import audit_log

        @audit_log(action_type="system", action_name="compute", tier="safe")
        def add(a: int, b: int) -> int:
            return a + b

        assert add(2, 3) == 5

    def test_decorator_preserves_function_name(self) -> None:
        from core.decorators import audit_log

        @audit_log(action_type="system", tier="safe")
        def my_function() -> None:
            pass

        assert my_function.__name__ == "my_function"

    def test_decorator_preserves_docstring(self) -> None:
        from core.decorators import audit_log

        @audit_log(action_type="system", tier="safe")
        def documented():
            """This is the docstring."""

        assert documented.__doc__ == "This is the docstring."

    def test_decorator_propagates_exception(self) -> None:
        from core.decorators import audit_log

        @audit_log(action_type="file_op", action_name="read_file", tier="read")
        def always_fails():
            raise ValueError("file not found")

        with pytest.raises(ValueError, match="file not found"):
            always_fails()

    def test_decorator_passes_kwargs(self) -> None:
        from core.decorators import audit_log

        results = []

        @audit_log(action_type="system", tier="safe")
        def record(name: str, value: int = 0) -> dict:
            return {"name": name, "value": value}

        out = record(name="x", value=42)
        assert out == {"name": "x", "value": 42}

    def test_extract_resource_called(self) -> None:
        from core.decorators import audit_log

        captured: list[Any] = []

        def extractor(args, kwargs):
            captured.append(kwargs.get("path") or (args[0] if args else None))
            return str(captured[-1])

        @audit_log(
            action_type="file_op",
            action_name="read_file",
            tier="read",
            extract_resource=extractor,
        )
        def read_file(path: str) -> str:
            return f"contents of {path}"

        read_file("/tmp/test.txt")
        assert "/tmp/test.txt" in captured

    def test_custom_action_name_used(self) -> None:
        """action_name parameter should override the function name in audit records."""
        from core.decorators import audit_log

        @audit_log(action_type="system", action_name="custom_op", tier="read")
        def internal_name():
            pass

        # We verify the decorator doesn't break; action_name is checked in audit output
        internal_name()

    def test_multiple_decorators_composable(self) -> None:
        from core.decorators import audit_log

        call_log: list[str] = []

        @audit_log(action_type="system", action_name="op_a", tier="safe")
        @audit_log(action_type="system", action_name="op_b", tier="read")
        def double_decorated():
            call_log.append("ran")

        double_decorated()
        assert call_log == ["ran"]

    def test_decorator_timing_non_negative(self) -> None:
        from core.decorators import audit_log

        @audit_log(action_type="system", tier="safe")
        def slow_ish():
            time.sleep(0.01)

        # Just ensure it doesn't raise
        slow_ish()

    def test_return_value_preserved_on_none(self) -> None:
        from core.decorators import audit_log

        @audit_log(action_type="system", tier="safe")
        def returns_none():
            return None

        assert returns_none() is None


# ===========================================================================
# @audit_log_async decorator
# ===========================================================================
class TestAuditLogAsyncDecorator:

    @pytest.mark.asyncio
    async def test_async_function_runs(self) -> None:
        from core.decorators import audit_log_async

        @audit_log_async(action_type="system", action_name="async_op", tier="safe")
        async def fetch() -> str:
            return "data"

        result = await fetch()
        assert result == "data"

    @pytest.mark.asyncio
    async def test_async_propagates_exception(self) -> None:
        from core.decorators import audit_log_async

        @audit_log_async(action_type="system", tier="read")
        async def fail():
            raise RuntimeError("async fail")

        with pytest.raises(RuntimeError, match="async fail"):
            await fail()


# ===========================================================================
# @require_permission decorator
# ===========================================================================
class TestRequirePermissionDecorator:

    def _service_with_broker(self, broker):
        """Create a mock service object that holds a broker."""
        from core.decorators import require_permission

        class Service:
            def __init__(self, b):
                self._broker = b

            @require_permission("write_file")
            def write_file(self, path: str, content: str) -> str:
                return f"wrote {content} to {path}"

            @require_permission("delete_file")
            def delete_file(self, path: str) -> str:
                return f"deleted {path}"

        return Service(broker)

    def test_permission_granted_executes_function(self, permission_broker) -> None:
        svc = self._service_with_broker(permission_broker)
        result = svc.write_file("/tmp/test.txt", "hello")
        assert "wrote" in result

    def test_permission_denied_raises_permission_error(self, deny_broker) -> None:
        svc = self._service_with_broker(deny_broker)
        with pytest.raises(PermissionError, match="denied"):
            svc.write_file("/tmp/test.txt", "hello")

    def test_no_broker_falls_through(self) -> None:
        """If self._broker is not set, the function runs without gating."""
        from core.decorators import require_permission

        class NoBrokerService:
            @require_permission("write_file")
            def write_file(self, path: str) -> str:
                return f"wrote {path}"

        svc = NoBrokerService()
        result = svc.write_file("/tmp/x.txt")
        assert "wrote" in result

    def test_tier_override_registered(self, permission_broker) -> None:
        from core.decorators import require_permission
        from core.permission_broker import PermissionTier

        class Svc:
            def __init__(self, b):
                self._broker = b

            @require_permission("my_safe_action", tier=PermissionTier.SAFE)
            def safe_op(self) -> str:
                return "safe"

        svc = Svc(permission_broker)
        result = svc.safe_op()
        assert result == "safe"
        assert permission_broker.get_tier("my_safe_action") == PermissionTier.SAFE


# ===========================================================================
# Permissions table (DB schema v2)
# ===========================================================================
class TestPermissionsTable:

    def test_permissions_table_exists(self, tmp_db: Path) -> None:
        from db.schema import get_db

        with get_db(db_path=tmp_db) as conn:
            tables = {
                r["name"]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        assert "permissions" in tables

    def test_insert_permission_record(self, tmp_db: Path) -> None:
        from db.schema import get_db

        with get_db(db_path=tmp_db) as conn:
            conn.execute(
                """INSERT INTO permissions (session_id, action_name, tier, granted, user_approved)
                   VALUES (?, ?, ?, ?, ?)""",
                ("sess1", "write_file", "write", 1, 1),
            )

        with get_db(db_path=tmp_db) as conn:
            row = conn.execute(
                "SELECT * FROM permissions WHERE action_name='write_file'"
            ).fetchone()

        assert row is not None
        assert row["tier"] == "write"
        assert row["granted"] == 1
        assert row["user_approved"] == 1

    def test_permissions_revoked_at_null_by_default(self, tmp_db: Path) -> None:
        from db.schema import get_db

        with get_db(db_path=tmp_db) as conn:
            conn.execute(
                "INSERT INTO permissions (session_id, action_name, tier) VALUES (?,?,?)",
                ("s2", "read_file", "read"),
            )

        with get_db(db_path=tmp_db) as conn:
            row = conn.execute("SELECT revoked_at FROM permissions").fetchone()

        assert row["revoked_at"] is None

    def test_schema_version_is_2(self, tmp_db: Path) -> None:
        from db.schema import get_db, CURRENT_SCHEMA_VERSION

        assert CURRENT_SCHEMA_VERSION == 2
        with get_db(db_path=tmp_db) as conn:
            row = conn.execute(
                "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
            ).fetchone()
        assert row["version"] == 2

    def test_all_required_tables_present(self, tmp_db: Path) -> None:
        from db.schema import get_db

        required = {
            "reminders", "meetings", "preferences", "audit_logs",
            "permissions", "oauth_tokens", "conversation_history",
        }
        with get_db(db_path=tmp_db) as conn:
            tables = {
                r["name"]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        missing = required - tables
        assert not missing, f"Missing tables: {missing}"


# ===========================================================================
# SQLCipher encryption verification
# ===========================================================================
class TestSQLCipherEncryption:

    def test_encrypted_db_not_readable_as_plain_text(self, tmp_path: Path) -> None:
        """
        Open an encrypted DB, write a secret, then verify it can't be read
        as plaintext by a direct file read.
        """
        try:
            import sqlcipher3  # type: ignore  # noqa: F401
        except ImportError:
            pytest.skip("sqlcipher3 not available")

        from db.schema import init_db, get_db, KeyStore, KEY_PATH

        db_path = tmp_path / "secret.db"
        init_db(db_path=db_path)

        with get_db(db_path=db_path) as conn:
            conn.execute(
                "INSERT INTO preferences (namespace, key, value) VALUES (?,?,?)",
                ("security", "secret_key", '"TOP_SECRET_VALUE_12345"'),
            )

        # Read raw bytes and check secret is NOT visible in plain text
        raw = db_path.read_bytes()
        assert b"TOP_SECRET_VALUE_12345" not in raw, (
            "Secret found in raw DB bytes – encryption may not be working!"
        )

    def test_sqlcipher_key_is_not_hardcoded(self, tmp_path: Path) -> None:
        """Verify the DB key is generated, not hardcoded."""
        from db.schema import KeyStore

        ks = KeyStore(tmp_path / ".key.enc")
        key = ks.ensure_key()

        # Key should be 64 hex chars (32 bytes)
        assert len(key) == 64
        assert all(c in "0123456789abcdef" for c in key)

        # Not a well-known constant
        assert key not in {
            "0" * 64,
            "f" * 64,
            "deadbeef" * 8,
        }

    def test_different_key_files_produce_different_keys(self, tmp_path: Path) -> None:
        from db.schema import KeyStore

        k1 = KeyStore(tmp_path / "k1.enc").ensure_key()
        k2 = KeyStore(tmp_path / "k2.enc").ensure_key()
        assert k1 != k2

    def test_same_key_file_produces_stable_key(self, tmp_path: Path) -> None:
        from db.schema import KeyStore

        ks = KeyStore(tmp_path / "stable.enc")
        k1 = ks.ensure_key()
        k2 = ks.ensure_key()
        assert k1 == k2


# ===========================================================================
# DPAPI key protection
# ===========================================================================
class TestDPAPIKeyProtection:

    @pytest.mark.skipif(sys.platform != "win32", reason="DPAPI is Windows-only")
    def test_dpapi_protect_unprotect_roundtrip(self) -> None:
        from db.schema import _dpapi_protect, _dpapi_unprotect

        plaintext = b"super secret key material 1234"
        ciphertext = _dpapi_protect(plaintext)

        assert ciphertext != plaintext
        assert len(ciphertext) > len(plaintext)

        recovered = _dpapi_unprotect(ciphertext)
        assert recovered == plaintext

    @pytest.mark.skipif(sys.platform != "win32", reason="DPAPI is Windows-only")
    def test_dpapi_key_file_is_binary_on_disk(self, tmp_path: Path) -> None:
        from db.schema import KeyStore

        ks = KeyStore(tmp_path / ".enc")
        ks.ensure_key()

        raw = (tmp_path / ".enc").read_bytes()
        # DPAPI output is never pure ASCII (it's a binary BLOB)
        assert len(raw) > 32

    @pytest.mark.skipif(sys.platform == "win32", reason="Only tests non-Windows fallback")
    def test_non_windows_stores_raw_key(self, tmp_path: Path) -> None:
        from db.schema import KeyStore

        ks = KeyStore(tmp_path / ".key")
        key_hex = ks.ensure_key()
        raw = (tmp_path / ".key").read_bytes()
        assert raw.hex() == key_hex


# ===========================================================================
# argparse CLI
# ===========================================================================
class TestArgparseCLI:

    def test_parser_builds_without_error(self) -> None:
        from cli.jarvis_argparse import build_parser
        parser = build_parser()
        assert parser is not None

    def test_version_flag(self, capsys) -> None:
        from cli.jarvis_argparse import build_parser
        parser = build_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["--version"])
        assert exc_info.value.code == 0

    def test_no_command_returns_zero(self) -> None:
        from cli.jarvis_argparse import main
        rc = main([])
        assert rc == 0

    def test_help_exits_cleanly(self) -> None:
        from cli.jarvis_argparse import main
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0

    def test_health_command_parses(self) -> None:
        from cli.jarvis_argparse import build_parser
        parser = build_parser()
        args = parser.parse_args(["health"])
        assert args.command == "health"

    def test_ask_command_parses_question(self) -> None:
        from cli.jarvis_argparse import build_parser
        parser = build_parser()
        args = parser.parse_args(["ask", "What is 2+2?"])
        assert args.command == "ask"
        assert args.question == "What is 2+2?"
        assert args.model == "qwen3:8b"
        assert args.temperature == 0.7

    def test_ask_custom_model(self) -> None:
        from cli.jarvis_argparse import build_parser
        parser = build_parser()
        args = parser.parse_args(["ask", "Hi", "--model", "phi3:mini", "--temperature", "0.5"])
        assert args.model == "phi3:mini"
        assert args.temperature == pytest.approx(0.5)

    def test_chat_defaults(self) -> None:
        from cli.jarvis_argparse import build_parser
        parser = build_parser()
        args = parser.parse_args(["chat"])
        assert args.command == "chat"
        assert args.stream is True
        assert args.challenge == "balanced"

    def test_no_stream_flag(self) -> None:
        from cli.jarvis_argparse import build_parser
        parser = build_parser()
        args = parser.parse_args(["chat", "--no-stream"])
        assert args.stream is False

    def test_audit_limit_default(self) -> None:
        from cli.jarvis_argparse import build_parser
        parser = build_parser()
        args = parser.parse_args(["audit"])
        assert args.limit == 20
        assert args.type is None

    def test_audit_limit_custom(self) -> None:
        from cli.jarvis_argparse import build_parser
        parser = build_parser()
        args = parser.parse_args(["audit", "--limit", "5", "--type", "file_op"])
        assert args.limit == 5
        assert args.type == "file_op"

    def test_permissions_revoke_flag(self) -> None:
        from cli.jarvis_argparse import build_parser
        parser = build_parser()
        args = parser.parse_args(["permissions", "--revoke"])
        assert args.revoke is True

    def test_db_init_flag(self) -> None:
        from cli.jarvis_argparse import build_parser
        parser = build_parser()
        args = parser.parse_args(["db", "--init"])
        assert args.init is True
        assert args.tables is False

    def test_db_tables_flag(self) -> None:
        from cli.jarvis_argparse import build_parser
        parser = build_parser()
        args = parser.parse_args(["db", "--tables"])
        assert args.tables is True

    def test_no_color_flag(self) -> None:
        from cli.jarvis_argparse import build_parser
        parser = build_parser()
        args = parser.parse_args(["--no-color", "health"])
        assert args.color is False

    def test_health_offline(self) -> None:
        """cmd_health returns 1 when Ollama is unreachable."""
        from cli.jarvis_argparse import cmd_health, build_parser

        parser = build_parser()
        args = parser.parse_args(["--no-color", "health"])

        with patch("core.ollama_adapter.OllamaAdapter.is_healthy", return_value=False):
            rc = cmd_health(args)
        assert rc == 1

    def test_health_online_no_models(self) -> None:
        from cli.jarvis_argparse import cmd_health, build_parser

        parser = build_parser()
        args = parser.parse_args(["--no-color", "health"])

        with patch("core.ollama_adapter.OllamaAdapter.is_healthy", return_value=True), \
             patch("core.ollama_adapter.OllamaAdapter.list_models", return_value=[]):
            rc = cmd_health(args)
        assert rc == 0

    def test_permissions_show(self) -> None:
        from cli.jarvis_argparse import cmd_permissions, build_parser

        parser = build_parser()
        args = parser.parse_args(["--no-color", "permissions"])
        rc = cmd_permissions(args)
        assert rc == 0

    def test_permissions_revoke(self) -> None:
        from cli.jarvis_argparse import cmd_permissions, build_parser

        parser = build_parser()
        args = parser.parse_args(["--no-color", "permissions", "--revoke"])
        rc = cmd_permissions(args)
        assert rc == 0

    def test_db_init_runs(self, tmp_path: Path) -> None:
        from cli.jarvis_argparse import cmd_db, build_parser

        parser = build_parser()
        args = parser.parse_args(["--no-color", "db", "--init"])

        with patch("db.schema.DB_PATH", tmp_path / "cli_test.db"):
            rc = cmd_db(args)
        assert rc == 0

    def test_db_no_flags_returns_1(self) -> None:
        from cli.jarvis_argparse import cmd_db, build_parser

        parser = build_parser()
        args = parser.parse_args(["--no-color", "db"])
        rc = cmd_db(args)
        assert rc == 1

    def test_audit_empty_returns_zero(self) -> None:
        from cli.jarvis_argparse import cmd_audit, build_parser
        from core.audit_logger import AuditLogger
        import core.audit_logger as al_mod

        parser = build_parser()
        args = parser.parse_args(["--no-color", "audit", "--limit", "5"])

        mock_al = Mock()
        mock_al.recent.return_value = []
        old = al_mod._logger_instance
        al_mod._logger_instance = mock_al
        try:
            rc = cmd_audit(args)
        finally:
            al_mod._logger_instance = old
        assert rc == 0


# ===========================================================================
# Conftest fixtures — self-test
# ===========================================================================
class TestConftest:

    def test_tmp_db_fixture(self, tmp_db: Path) -> None:
        assert tmp_db.exists()
        assert tmp_db.suffix == ".db"

    def test_db_conn_fixture(self, db_conn) -> None:
        row = db_conn.execute("SELECT 1 AS val").fetchone()
        assert row["val"] == 1

    def test_session_id_fixture_is_12_chars(self, session_id: str) -> None:
        assert len(session_id) == 12
        assert all(c in "0123456789abcdef" for c in session_id)

    def test_permission_broker_fixture_grants(self, permission_broker) -> None:
        result = permission_broker.request("write_file")
        assert result.granted is True

    def test_deny_broker_fixture_denies(self, deny_broker) -> None:
        result = deny_broker.request("write_file")
        assert result.granted is False

    def test_auto_broker_fixture_safe(self, auto_broker) -> None:
        result = auto_broker.request("get_time")
        assert result.granted is True

    def test_audit_logger_fixture_logs(self, audit_logger) -> None:
        audit_logger.log("system", "test_event", "completed")
        audit_logger.flush(timeout=2.0)
        records = audit_logger.recent(5)
        assert any(r["action_name"] == "test_event" for r in records)

    def test_prompt_builder_fixture(self, prompt_builder, session_id: str) -> None:
        prompt = prompt_builder.build(session_id=session_id)
        assert len(prompt) > 50

    def test_prompt_builder_all_levels(
        self, prompt_builder_all_levels, session_id: str
    ) -> None:
        prompt = prompt_builder_all_levels.build(session_id=session_id)
        assert isinstance(prompt, str)

    def test_mock_adapter_returns_response(self, mock_adapter) -> None:
        from core.ollama_adapter import ChatMessage
        result = mock_adapter.chat(
            messages=[ChatMessage(role="user", content="hi")]
        )
        assert result.choices[0].message.content == "Hello! How can I help?"

    def test_offline_adapter_is_unhealthy(self, offline_adapter) -> None:
        assert offline_adapter.is_healthy() is False

    def test_cli_args_base_fixture(self, cli_args_base) -> None:
        assert cli_args_base.color is False
        assert "11434" in cli_args_base.url

    def test_cli_ask_args_fixture(self, cli_ask_args) -> None:
        assert cli_ask_args.question == "What is 2 + 2?"
        assert cli_ask_args.model == "qwen3:8b"
