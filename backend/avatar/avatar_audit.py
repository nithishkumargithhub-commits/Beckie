"""Avatar Local Audit Logging.

Maintains a secure, local-only audit trail in logs/avatar_audit.jsonl.
Zero cloud transmission. Every asset discovery, validation, capability detection,
permission grant, state transition, and removal is recorded.
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

logger = logging.getLogger("Avatar.Audit")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
AUDIT_LOG_PATH = os.path.join(BASE_DIR, "logs", "avatar_audit.jsonl")


class AvatarAuditLogger:
    """Thread-safe append-only local audit log for Avatar lifecycle events."""

    def __init__(self, log_path: str = AUDIT_LOG_PATH):
        self.log_path = log_path
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)

    def log(
        self,
        action: str,
        asset_id: Optional[str] = None,
        source_file: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        user_approved: bool = False,
        warnings: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Record an immutable audit entry."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action.upper(),
            "assetId": asset_id,
            "sourceFile": source_file,
            "userApproved": user_approved,
            "warnings": warnings or [],
            "details": details or {},
        }

        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
            logger.info(f"[AvatarAudit] {entry['action']}: {entry.get('sourceFile') or ''} (approved={user_approved})")
        except Exception as e:
            logger.error(f"[AvatarAudit] Failed to write audit log: {e}")

        return entry

    def get_recent_entries(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve recent audit logs in reverse chronological order."""
        if not os.path.exists(self.log_path):
            return []

        entries = []
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.error(f"[AvatarAudit] Failed to read audit log: {e}")

        return list(reversed(entries[-limit:]))


_singleton_logger: Optional[AvatarAuditLogger] = None


def get_audit_logger() -> AvatarAuditLogger:
    global _singleton_logger
    if _singleton_logger is None:
        _singleton_logger = AvatarAuditLogger()
    return _singleton_logger
