"""
JARVIS – Encrypted SQLite schema manager.

Uses sqlcipher3 for at-rest encryption and Windows DPAPI to protect
the database key so no secrets ever live in source code or env vars.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

logger = logging.getLogger("Jarvis.DB.Schema")

# ---------------------------------------------------------------------------
# DPAPI key management (Windows-only; falls back to raw key on other OS)
# ---------------------------------------------------------------------------

def _dpapi_protect(plaintext: bytes) -> bytes:
    """Encrypt bytes with Windows DPAPI (user-scope)."""
    if sys.platform != "win32":
        raise RuntimeError("DPAPI is only available on Windows")
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    data = ctypes.create_string_buffer(plaintext)
    blob_in = DATA_BLOB(len(plaintext), data)
    blob_out = DATA_BLOB()

    if not ctypes.windll.crypt32.CryptProtectData(  # type: ignore[attr-defined]
        ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
    ):
        raise OSError("CryptProtectData failed")

    result = ctypes.string_at(blob_out.pbData, blob_out.cbData)
    ctypes.windll.kernel32.LocalFree(blob_out.pbData)  # type: ignore[attr-defined]
    return result


def _dpapi_unprotect(ciphertext: bytes) -> bytes:
    """Decrypt bytes with Windows DPAPI (user-scope)."""
    if sys.platform != "win32":
        raise RuntimeError("DPAPI is only available on Windows")
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    data = ctypes.create_string_buffer(ciphertext)
    blob_in = DATA_BLOB(len(ciphertext), data)
    blob_out = DATA_BLOB()

    if not ctypes.windll.crypt32.CryptUnprotectData(  # type: ignore[attr-defined]
        ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
    ):
        raise OSError("CryptUnprotectData failed")

    result = ctypes.string_at(blob_out.pbData, blob_out.cbData)
    ctypes.windll.kernel32.LocalFree(blob_out.pbData)  # type: ignore[attr-defined]
    return result


# ---------------------------------------------------------------------------
# Key store – persists the DPAPI-wrapped SQLCipher key on disk
# ---------------------------------------------------------------------------

class KeyStore:
    """Manages the encrypted database key using Windows DPAPI."""

    def __init__(self, key_path: Path) -> None:
        self._path = key_path

    def ensure_key(self) -> str:
        """Return the hex SQLCipher passphrase, creating and persisting it if new."""
        if self._path.exists():
            return self._load_key()
        return self._create_key()

    def _create_key(self) -> str:
        raw = os.urandom(32)  # 256-bit random key
        if sys.platform == "win32":
            wrapped = _dpapi_protect(raw)
        else:
            wrapped = raw  # Dev/CI fallback: not for production on non-Windows
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_bytes(wrapped)
        logger.info("Created new database key at %s", self._path)
        return raw.hex()

    def _load_key(self) -> str:
        wrapped = self._path.read_bytes()
        if sys.platform == "win32":
            raw = _dpapi_unprotect(wrapped)
        else:
            raw = wrapped
        return raw.hex()


# ---------------------------------------------------------------------------
# Dict row factory (compatible with both sqlite3 and sqlcipher3 cursors)
# ---------------------------------------------------------------------------

def _dict_row_factory(cursor: object, row: tuple) -> dict:
    """Return rows as dicts; works with both sqlite3 and sqlcipher3 cursors."""
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Database path configuration
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "jarvis_encrypted.db"
KEY_PATH = DATA_DIR / ".jarvis_key.enc"

DATA_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------

def _get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """
    Open a database connection.
    If sqlcipher3 is available the database is encrypted at rest.
    Falls back to plain sqlite3 with a warning (dev/CI only).
    """
    try:
        import sqlcipher3  # type: ignore
        key_store = KeyStore(KEY_PATH)
        passphrase = key_store.ensure_key()
        conn = sqlcipher3.connect(str(db_path))
        conn.execute(f"PRAGMA key=\"x'{passphrase}'\"")
        conn.execute("PRAGMA cipher_page_size=4096")
        conn.execute("PRAGMA kdf_iter=256000")
        conn.execute("PRAGMA cipher_hmac_algorithm=HMAC_SHA512")
        conn.execute("PRAGMA cipher_kdf_algorithm=PBKDF2_HMAC_SHA512")
        logger.debug("Opened encrypted SQLite connection (SQLCipher)")
    except ImportError:
        logger.warning(
            "sqlcipher3 not available – using plain SQLite (development mode only!)"
        )
        conn = sqlite3.connect(str(db_path))

    conn.row_factory = _dict_row_factory
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_db(db_path: Path = DB_PATH) -> Generator[sqlite3.Connection, None, None]:
    """Context manager that yields a connection and auto-commits or rolls back."""
    conn = _get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Schema DDL
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
-- ─────────────────────────────────────────────────────────────────
-- Reminders
-- ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS reminders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL,
    body        TEXT,
    due_at      TEXT    NOT NULL,
    recurrence  TEXT    NOT NULL DEFAULT 'none',
    priority    TEXT    NOT NULL DEFAULT 'normal',
    status      TEXT    NOT NULL DEFAULT 'pending',
    source      TEXT    NOT NULL DEFAULT 'user',
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_reminders_due ON reminders(due_at, status);

-- ─────────────────────────────────────────────────────────────────
-- Meetings
-- ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS meetings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT    NOT NULL,
    description     TEXT,
    location        TEXT,
    start_at        TEXT    NOT NULL,
    end_at          TEXT    NOT NULL,
    attendees_json  TEXT    NOT NULL DEFAULT '[]',
    calendar_id     TEXT,
    status          TEXT    NOT NULL DEFAULT 'confirmed',
    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_meetings_start ON meetings(start_at);

-- ─────────────────────────────────────────────────────────────────
-- Preferences  (key-value, JSON-encoded values, namespace-scoped)
-- ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS preferences (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    namespace   TEXT    NOT NULL DEFAULT 'user',
    key         TEXT    NOT NULL,
    value       TEXT,
    is_secret   INTEGER NOT NULL DEFAULT 0,
    updated_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE (namespace, key)
);

-- ─────────────────────────────────────────────────────────────────
-- OAuth tokens  (token_enc is Fernet-encrypted JSON)
-- ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS oauth_tokens (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    provider    TEXT    NOT NULL,
    account     TEXT    NOT NULL,
    token_enc   BLOB    NOT NULL,
    scopes      TEXT,
    expires_at  TEXT,
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE (provider, account)
);

-- ─────────────────────────────────────────────────────────────────
-- Audit log  (append-only; rows are never deleted)
-- ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    session_id      TEXT    NOT NULL,
    action_type     TEXT    NOT NULL,
    action_name     TEXT    NOT NULL,
    tier            TEXT,
    status          TEXT    NOT NULL,
    user_approved   INTEGER NOT NULL DEFAULT 0,
    actor           TEXT    NOT NULL DEFAULT 'llm',
    resource        TEXT,
    details_json    TEXT    NOT NULL DEFAULT '{}',
    duration_ms     INTEGER
);
CREATE INDEX IF NOT EXISTS idx_audit_ts      ON audit_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_session ON audit_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_audit_action  ON audit_logs(action_type, action_name);

-- ─────────────────────────────────────────────────────────────────
-- Conversation history  (rolling short-term memory)
-- ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS conversation_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT    NOT NULL,
    role        TEXT    NOT NULL,
    content     TEXT    NOT NULL,
    tokens      INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_conv_session ON conversation_history(session_id, created_at);

-- ─────────────────────────────────────────────────────────────────
-- Schema version bookkeeping
-- ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER PRIMARY KEY,
    applied_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    description TEXT
);
"""

CURRENT_SCHEMA_VERSION = 1


def init_db(db_path: Path = DB_PATH) -> None:
    """Create all tables and stamp the schema version."""
    with get_db(db_path) as conn:
        conn.executescript(SCHEMA_SQL)
        row = conn.execute(
            "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
        ).fetchone()
        if row is None or row["version"] < CURRENT_SCHEMA_VERSION:
            conn.execute(
                "INSERT OR IGNORE INTO schema_version (version, description) VALUES (?,?)",
                (
                    CURRENT_SCHEMA_VERSION,
                    "Initial schema: reminders, meetings, preferences, "
                    "oauth_tokens, audit_logs, conversation_history",
                ),
            )
    logger.info(
        "Database initialised at %s (schema v%d)", db_path, CURRENT_SCHEMA_VERSION
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    init_db()
    print(f"✓ Database initialised at {DB_PATH}")
