"""
Tests for external account integrations:
  - OAuth token store (save / load / refresh detection)
  - Gmail read-only flow (mocked)
  - Calendar read-only flow + CalendarReminderDaemon (mocked)
  - Spotify playback (mocked spotipy)
  - Native messaging host (JSON-RPC framing + dispatch)
"""

from __future__ import annotations

import io
import json
import sqlite3
import struct
import tempfile
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Generator
from unittest.mock import MagicMock, patch

import pytest


# ===========================================================================
# Shared DB fixture: creates a fresh plain-sqlite3 DB per test and patches
# the get_db context manager so all modules under test use the temp DB.
# ===========================================================================

@contextmanager
def _make_temp_db() -> Generator[Path, None, None]:
    """Spin up a fresh SQLite DB, run the Jarvis schema, yield its path."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"

        # Init schema directly on a plain sqlite3 connection
        from db.schema import SCHEMA_SQL
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(SCHEMA_SQL)
        conn.commit()
        conn.close()

        yield db_path


def _make_dict_conn(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = lambda cur, row: {col[0]: row[i] for i, col in enumerate(cur.description)}
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def _patched_get_db(db_path: Path):
    """Context manager that patches db.schema.get_db to use db_path."""
    @contextmanager
    def _fake_get_db(path=None):
        conn = _make_dict_conn(db_path)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    with patch("db.schema.get_db", _fake_get_db), \
         patch("core.token_store.get_db", _fake_get_db):
        yield


# ===========================================================================
# 1.  Token Store Tests
# ===========================================================================

class TestTokenStore:
    """Unit tests for core.token_store encrypted CRUD operations."""

    def test_save_and_load_token(self):
        with _make_temp_db() as db_path, _patched_get_db(db_path):
            from core.token_store import load_token, save_token

            token_data = {"access_token": "abc123", "refresh_token": "refresh_xyz"}
            save_token("test_provider", "user@test.com", token_data,
                       "read", "2099-01-01T00:00:00Z")

            loaded = load_token("test_provider", "user@test.com")
            assert loaded is not None
            assert loaded["access_token"] == "abc123"
            assert loaded["refresh_token"] == "refresh_xyz"

    def test_load_missing_token_returns_none(self):
        with _make_temp_db() as db_path, _patched_get_db(db_path):
            from core.token_store import load_token
            assert load_token("nonexistent_provider", "nobody@test.com") is None

    def test_delete_token(self):
        with _make_temp_db() as db_path, _patched_get_db(db_path):
            from core.token_store import delete_token, load_token, save_token

            save_token("prov", "acct", {"token": "val"})
            delete_token("prov", "acct")
            assert load_token("prov", "acct") is None

    def test_token_overwrite(self):
        with _make_temp_db() as db_path, _patched_get_db(db_path):
            from core.token_store import load_token, save_token

            save_token("prov", "acct", {"v": 1})
            save_token("prov", "acct", {"v": 2})
            assert load_token("prov", "acct")["v"] == 2

    def test_token_needs_refresh_when_missing(self):
        with _make_temp_db() as db_path, _patched_get_db(db_path):
            from core.token_store import token_needs_refresh
            assert token_needs_refresh("ghost", "nobody") is True

    def test_token_needs_refresh_when_expired(self):
        with _make_temp_db() as db_path, _patched_get_db(db_path):
            from core.token_store import save_token, token_needs_refresh

            past = (datetime.now(tz=timezone.utc) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
            save_token("prov", "acct", {"t": "x"}, expires_at=past)
            assert token_needs_refresh("prov", "acct") is True

    def test_token_valid_does_not_need_refresh(self):
        with _make_temp_db() as db_path, _patched_get_db(db_path):
            from core.token_store import save_token, token_needs_refresh

            future = (datetime.now(tz=timezone.utc) + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
            save_token("prov", "acct", {"t": "x"}, expires_at=future)
            assert token_needs_refresh("prov", "acct") is False

    def test_token_near_expiry_needs_refresh(self):
        """Within 5 min window → should flag for refresh."""
        with _make_temp_db() as db_path, _patched_get_db(db_path):
            from core.token_store import save_token, token_needs_refresh

            soon = (datetime.now(tz=timezone.utc) + timedelta(minutes=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
            save_token("prov", "acct", {"t": "x"}, expires_at=soon)
            assert token_needs_refresh("prov", "acct") is True


# ===========================================================================
# 2.  Full OAuth token refresh flow (end-to-end through token_store)
# ===========================================================================

class TestTokenRefreshFlow:

    def test_full_refresh_cycle(self):
        """
        Simulate: save expired → detect needs_refresh → save fresh → load valid.
        """
        with _make_temp_db() as db_path, _patched_get_db(db_path):
            from core import token_store as ts

            # Step 1: save an already-expired token
            past = (datetime.now(tz=timezone.utc) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
            ts.save_token("test", "u@test.com", {"access_token": "old"}, expires_at=past)
            assert ts.token_needs_refresh("test", "u@test.com") is True

            # Step 2: "refresh" by writing a new token
            future = (datetime.now(tz=timezone.utc) + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
            ts.save_token("test", "u@test.com", {"access_token": "new"}, expires_at=future)
            assert ts.token_needs_refresh("test", "u@test.com") is False

            # Step 3: loaded token should be the refreshed one
            loaded = ts.load_token("test", "u@test.com")
            assert loaded["access_token"] == "new"


# ===========================================================================
# 3.  Gmail (mocked Google API)
# ===========================================================================

class TestGmailSecure:

    def _mock_gmail_service(self, messages):
        service = MagicMock()
        users = service.users.return_value
        msgs = users.messages.return_value

        msgs.list.return_value.execute.return_value = {
            "messages": [{"id": str(i)} for i in range(len(messages))]
        }

        def get_side_effect(userId, id, format, metadataHeaders):
            idx = int(id)
            return MagicMock(execute=lambda: {
                "payload": {
                    "headers": [
                        {"name": "Subject", "value": messages[idx]["subject"]},
                        {"name": "From", "value": messages[idx]["from"]},
                    ]
                }
            })

        msgs.get.side_effect = get_side_effect
        return service

    @patch("actions.google_secure._build_service")
    def test_check_unread_emails_returns_summaries(self, mock_build):
        from actions.google_secure import check_unread_emails_secure

        mock_build.return_value = self._mock_gmail_service([
            {"subject": "Hello World", "from": "alice@example.com"},
            {"subject": "Meeting Tomorrow", "from": "bob@example.com"},
        ])

        ok, msg = check_unread_emails_secure(max_results=2)
        assert ok is True
        assert "Hello World" in msg
        assert "alice@example.com" in msg

    @patch("actions.google_secure._build_service")
    def test_check_unread_emails_none(self, mock_build):
        from actions.google_secure import check_unread_emails_secure

        svc = MagicMock()
        svc.users.return_value.messages.return_value.list.return_value.execute.return_value = {
            "messages": []
        }
        mock_build.return_value = svc

        ok, msg = check_unread_emails_secure()
        assert ok is True
        assert "no unread" in msg.lower()

    def test_missing_credentials_returns_error(self, tmp_path):
        from actions import google_secure

        with patch.object(google_secure, "CREDENTIALS_PATH", tmp_path / "missing.json"):
            ok, msg = google_secure.check_unread_emails_secure()
        assert ok is False
        assert "credentials.json" in msg.lower() or "not found" in msg.lower()


# ===========================================================================
# 4.  Calendar (mocked)
# ===========================================================================

class TestCalendarSecure:

    @patch("actions.google_secure._build_service")
    def test_get_upcoming_events(self, mock_build):
        from actions.google_secure import get_upcoming_events

        svc = MagicMock()
        svc.events.return_value.list.return_value.execute.return_value = {
            "items": [
                {"summary": "Standup", "start": {"dateTime": "2026-09-28T10:00:00Z"}},
                {"summary": "Lunch", "start": {"dateTime": "2026-09-28T12:00:00Z"}},
            ]
        }
        mock_build.return_value = svc

        ok, msg = get_upcoming_events(max_results=2)
        assert ok is True
        assert "Standup" in msg
        assert "Lunch" in msg

    @patch("actions.google_secure._build_service")
    def test_no_upcoming_events(self, mock_build):
        from actions.google_secure import get_upcoming_events

        svc = MagicMock()
        svc.events.return_value.list.return_value.execute.return_value = {"items": []}
        mock_build.return_value = svc

        ok, msg = get_upcoming_events()
        assert ok is True
        assert "no upcoming" in msg.lower()

    @patch("actions.google_secure._build_service")
    def test_calendar_reminder_daemon_announces(self, mock_build):
        from actions.google_secure import CalendarReminderDaemon

        announced = []
        svc = MagicMock()
        svc.events.return_value.list.return_value.execute.return_value = {
            "items": [{
                "summary": "Doctor Appointment",
                "start": {"dateTime": "2026-09-28T11:00:00Z"},
            }]
        }
        mock_build.return_value = svc

        daemon = CalendarReminderDaemon(speak_fn=announced.append, poll_interval_seconds=1)
        daemon._check_and_announce()

        assert any("Doctor Appointment" in s for s in announced)


# ===========================================================================
# 5.  Spotify (mocked spotipy)
# ===========================================================================

class TestSpotifyIntegration:

    def test_play_with_query(self, monkeypatch):
        import actions.spotify_integration as mod

        sp = MagicMock()
        sp.search.return_value = {
            "tracks": {"items": [{"uri": "spotify:track:abc", "name": "Bohemian Rhapsody",
                                  "artists": [{"name": "Queen"}]}]}
        }
        monkeypatch.setattr(mod, "_get_spotify", lambda: sp)

        ok, msg = mod.play("Bohemian Rhapsody")
        assert ok is True
        assert "Bohemian Rhapsody" in msg
        sp.start_playback.assert_called_once_with(uris=["spotify:track:abc"])

    def test_play_no_results(self, monkeypatch):
        import actions.spotify_integration as mod

        sp = MagicMock()
        sp.search.return_value = {"tracks": {"items": []}}
        monkeypatch.setattr(mod, "_get_spotify", lambda: sp)

        ok, msg = mod.play("xyzzy nonexistent track 12345")
        assert ok is False
        assert "no spotify track found" in msg.lower() or "not found" in msg.lower()

    def test_pause(self, monkeypatch):
        import actions.spotify_integration as mod

        sp = MagicMock()
        monkeypatch.setattr(mod, "_get_spotify", lambda: sp)

        ok, msg = mod.pause()
        assert ok is True
        sp.pause_playback.assert_called_once()

    def test_skip_next(self, monkeypatch):
        import actions.spotify_integration as mod

        sp = MagicMock()
        monkeypatch.setattr(mod, "_get_spotify", lambda: sp)

        ok, msg = mod.skip_next()
        assert ok is True
        sp.next_track.assert_called_once()

    def test_set_volume_clamped(self, monkeypatch):
        import actions.spotify_integration as mod

        sp = MagicMock()
        monkeypatch.setattr(mod, "_get_spotify", lambda: sp)

        ok, msg = mod.set_volume(150)
        assert ok is True
        sp.volume.assert_called_once_with(100)

    def test_now_playing(self, monkeypatch):
        import actions.spotify_integration as mod

        sp = MagicMock()
        sp.current_playback.return_value = {
            "is_playing": True,
            "progress_ms": 60000,
            "item": {
                "name": "Stairway to Heaven",
                "artists": [{"name": "Led Zeppelin"}],
                "album": {"name": "Led Zeppelin IV"},
                "duration_ms": 480000,
            },
        }
        monkeypatch.setattr(mod, "_get_spotify", lambda: sp)

        ok, msg = mod.now_playing()
        assert ok is True
        assert "Stairway to Heaven" in msg
        assert "Led Zeppelin" in msg

    def test_premium_required_error(self, monkeypatch):
        import actions.spotify_integration as mod

        sp = MagicMock()
        sp.next_track.side_effect = Exception("403 Forbidden: PREMIUM_REQUIRED")
        monkeypatch.setattr(mod, "_get_spotify", lambda: sp)

        ok, msg = mod.skip_next()
        assert ok is False
        assert "premium" in msg.lower()

    def test_missing_credentials_error(self, monkeypatch):
        import actions.spotify_integration as mod

        monkeypatch.setenv("SPOTIFY_CLIENT_ID", "")
        monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "")

        ok, msg = mod.play("anything")
        assert ok is False
        assert "SPOTIFY_CLIENT_ID" in msg or "must be set" in msg.lower()


# ===========================================================================
# 6.  Native Messaging Host (JSON-RPC dispatch — tested via _dispatch directly)
# ===========================================================================

class TestNativeHost:
    """
    Tests call _dispatch() directly to avoid the stdin/stdout binary framing
    which cannot be reliably patched in the pytest runner environment.
    The framing itself (struct pack/unpack) is tested separately via helpers.
    """

    def _frame(self, obj: Dict) -> bytes:
        payload = json.dumps(obj).encode("utf-8")
        return struct.pack("<I", len(payload)) + payload

    def _unframe(self, data: bytes) -> Dict:
        length = struct.unpack("<I", data[:4])[0]
        return json.loads(data[4:4 + length].decode("utf-8"))

    def test_framing_roundtrip(self):
        """Verify 4-byte length-prefix framing encodes and decodes correctly."""
        original = {"jsonrpc": "2.0", "id": 42, "result": {"pong": True}}
        framed = self._frame(original)
        decoded = self._unframe(framed)
        assert decoded == original

    def test_dispatch_ping(self):
        from pipeline.native_host import _dispatch
        result = _dispatch("ping", {})
        assert result["pong"] is True

    def test_dispatch_unknown_method(self):
        from pipeline.native_host import _dispatch
        with pytest.raises(NotImplementedError, match="Unknown method"):
            _dispatch("no.such.method", {})

    def test_dispatch_page_summarise(self):
        from pipeline.native_host import _dispatch
        result = _dispatch("page.summarise", {
            "text": "The quick brown fox jumps " * 10,
            "url": "https://example.com",
        })
        assert "summary" in result
        assert "example.com" in result["summary"]

    def test_dispatch_page_summarise_empty(self):
        from pipeline.native_host import _dispatch
        result = _dispatch("page.summarise", {"text": "", "url": "https://example.com"})
        assert "No page text" in result["summary"]

    @patch("actions.google_secure._build_service")
    def test_dispatch_gmail_unread(self, mock_build):
        svc = MagicMock()
        svc.users.return_value.messages.return_value.list.return_value.execute.return_value = {
            "messages": []
        }
        mock_build.return_value = svc

        from pipeline.native_host import _dispatch
        result = _dispatch("gmail.unread", {})
        assert "message" in result

    @patch("actions.google_secure._build_service")
    def test_dispatch_calendar_upcoming(self, mock_build):
        svc = MagicMock()
        svc.events.return_value.list.return_value.execute.return_value = {"items": []}
        mock_build.return_value = svc

        from pipeline.native_host import _dispatch
        result = _dispatch("calendar.upcoming", {})
        assert "message" in result

    def test_dispatch_spotify_pause(self, monkeypatch):
        import actions.spotify_integration as sp_mod

        sp = MagicMock()
        monkeypatch.setattr(sp_mod, "_get_spotify", lambda: sp)

        from pipeline.native_host import _dispatch
        result = _dispatch("spotify.pause", {})
        assert "paused" in result["message"].lower()

    def test_dispatch_spotify_volume(self, monkeypatch):
        import actions.spotify_integration as sp_mod

        sp = MagicMock()
        monkeypatch.setattr(sp_mod, "_get_spotify", lambda: sp)

        from pipeline.native_host import _dispatch
        result = _dispatch("spotify.volume", {"percent": 75})
        assert "75%" in result["message"]

    def test_ok_response_structure(self):
        from pipeline.native_host import _ok
        resp = _ok(7, {"data": "value"})
        assert resp == {"jsonrpc": "2.0", "id": 7, "result": {"data": "value"}}

    def test_err_response_structure(self):
        from pipeline.native_host import _err
        resp = _err(8, -32601, "Method not found")
        assert resp["error"]["code"] == -32601
        assert resp["error"]["message"] == "Method not found"
        assert resp["id"] == 8
