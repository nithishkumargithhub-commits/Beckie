"""
JARVIS – Encrypted OAuth Token Store.

Tokens are stored as Fernet-encrypted JSON blobs inside the SQLCipher
database so they are double-encrypted at rest:
  Layer 1 – SQLCipher (AES-256, key protected by Windows DPAPI)
  Layer 2 – Fernet envelope (per-provider, key stored in same DB)

Public API
----------
  save_token(provider, account, token_data, scopes, expires_at)
  load_token(provider, account) -> dict | None
  delete_token(provider, account)
  token_needs_refresh(provider, account) -> bool
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet

from db.schema import get_db

logger = logging.getLogger("Jarvis.Core.TokenStore")

# Namespace used to store the per-provider Fernet key in the preferences table
_FERNET_KEY_NAMESPACE = "oauth_fernet_keys"


# ---------------------------------------------------------------------------
# Fernet key management (one key per provider, stored in the encrypted DB)
# ---------------------------------------------------------------------------

def _get_or_create_fernet(provider: str) -> Fernet:
    """Return the Fernet instance for *provider*, creating the key if absent."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT value FROM preferences WHERE namespace=? AND key=?",
            (_FERNET_KEY_NAMESPACE, provider),
        ).fetchone()
        if row and row["value"]:
            key = row["value"].encode()
        else:
            key = Fernet.generate_key()
            conn.execute(
                """INSERT OR REPLACE INTO preferences (namespace, key, value, is_secret)
                   VALUES (?, ?, ?, 1)""",
                (_FERNET_KEY_NAMESPACE, provider, key.decode()),
            )
            logger.info("Generated new Fernet key for provider '%s'", provider)
    return Fernet(key)


# ---------------------------------------------------------------------------
# Public CRUD
# ---------------------------------------------------------------------------

def save_token(
    provider: str,
    account: str,
    token_data: Dict[str, Any],
    scopes: Optional[str] = None,
    expires_at: Optional[str] = None,
) -> None:
    """Fernet-encrypt *token_data* and upsert into oauth_tokens."""
    fernet = _get_or_create_fernet(provider)
    token_json = json.dumps(token_data).encode()
    token_enc = fernet.encrypt(token_json)

    with get_db() as conn:
        conn.execute(
            """INSERT INTO oauth_tokens (provider, account, token_enc, scopes, expires_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(provider, account)
               DO UPDATE SET
                 token_enc  = excluded.token_enc,
                 scopes     = excluded.scopes,
                 expires_at = excluded.expires_at,
                 updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now')""",
            (provider, account, token_enc, scopes, expires_at),
        )
    logger.info("Token saved for provider='%s' account='%s'", provider, account)


def load_token(provider: str, account: str) -> Optional[Dict[str, Any]]:
    """Decrypt and return the stored token dict, or None if absent."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT token_enc FROM oauth_tokens WHERE provider=? AND account=?",
            (provider, account),
        ).fetchone()

    if row is None:
        return None

    fernet = _get_or_create_fernet(provider)
    try:
        token_json = fernet.decrypt(row["token_enc"])
        return json.loads(token_json)
    except Exception as exc:
        logger.error("Failed to decrypt token for %s/%s: %s", provider, account, exc)
        return None


def delete_token(provider: str, account: str) -> None:
    """Remove a stored token (e.g. on explicit sign-out)."""
    with get_db() as conn:
        conn.execute(
            "DELETE FROM oauth_tokens WHERE provider=? AND account=?",
            (provider, account),
        )
    logger.info("Token deleted for provider='%s' account='%s'", provider, account)


def token_needs_refresh(provider: str, account: str) -> bool:
    """Return True if token is missing or within 5 minutes of expiry."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT expires_at FROM oauth_tokens WHERE provider=? AND account=?",
            (provider, account),
        ).fetchone()

    if row is None or not row["expires_at"]:
        return True

    try:
        expires = datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00"))
        delta = expires - datetime.now(tz=timezone.utc)
        return delta.total_seconds() < 300  # refresh within 5 min window
    except Exception:
        return True
