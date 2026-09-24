"""
JARVIS – Audit Logger.

Writes every action (permission check, LLM query, file op, OAuth, system event)
to the SQLite audit_logs table with full metadata.  Thread-safe; non-blocking
via an internal queue + background writer thread.
"""

from __future__ import annotations

import json
import logging
import queue
import sqlite3
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("Jarvis.Core.AuditLogger")


# ---------------------------------------------------------------------------
# Audit record dataclass
# ---------------------------------------------------------------------------

@dataclass
class AuditRecord:
    action_type: str        # permission_check | llm_query | file_op | oauth | system
    action_name: str        # e.g. "read_file", "chat_completion"
    session_id: str
    status: str             # approved | denied | auto_approved | error | started | completed
    tier: Optional[str] = None       # safe | read | write | destructive
    user_approved: bool = False
    actor: str = "llm"               # llm | user | system | daemon
    resource: Optional[str] = None   # path or URI (sanitised, no credentials)
    details: dict[str, Any] = field(default_factory=dict)
    duration_ms: Optional[int] = None
    timestamp: str = field(
        default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
    )
    id: Optional[int] = None         # set after DB insert


# ---------------------------------------------------------------------------
# Audit Logger
# ---------------------------------------------------------------------------

class AuditLogger:
    """
    Non-blocking audit logger backed by SQLite.

    Records are enqueued immediately and written asynchronously by a
    background daemon thread, ensuring the calling thread is never blocked
    by DB I/O.
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        session_id: Optional[str] = None,
        queue_maxsize: int = 1000,
    ) -> None:
        from db.schema import DB_PATH, _get_connection

        self._db_path = db_path or DB_PATH
        self._get_conn = _get_connection
        self._session_id = session_id or uuid.uuid4().hex
        self._queue: queue.Queue[Optional[AuditRecord]] = queue.Queue(maxsize=queue_maxsize)
        self._stop_event = threading.Event()

        self._writer = threading.Thread(
            target=self._write_loop, name="AuditLogger-Writer", daemon=True
        )
        self._writer.start()
        logger.info("AuditLogger started (session=%s, db=%s)", self._session_id, self._db_path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def log(
        self,
        action_type: str,
        action_name: str,
        status: str,
        tier: Optional[str] = None,
        user_approved: bool = False,
        actor: str = "llm",
        resource: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
        duration_ms: Optional[int] = None,
        session_id: Optional[str] = None,
    ) -> None:
        """Enqueue an audit record (non-blocking)."""
        record = AuditRecord(
            action_type=action_type,
            action_name=action_name,
            session_id=session_id or self._session_id,
            status=status,
            tier=tier,
            user_approved=user_approved,
            actor=actor,
            resource=self._sanitise_resource(resource),
            details=details or {},
            duration_ms=duration_ms,
        )
        try:
            self._queue.put_nowait(record)
        except queue.Full:
            logger.error(
                "Audit queue full – dropping record: %s / %s", action_type, action_name
            )

    def log_permission(
        self,
        action_name: str,
        tier: str,
        granted: bool,
        user_approved: bool = False,
        resource: Optional[str] = None,
        actor: str = "llm",
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        status = "approved" if granted else "denied"
        if granted and not user_approved:
            status = "auto_approved"
        self.log(
            action_type="permission_check",
            action_name=action_name,
            status=status,
            tier=tier,
            user_approved=user_approved,
            actor=actor,
            resource=resource,
            details=details,
        )

    def log_llm_query(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        model: str,
        duration_ms: int,
        status: str = "completed",
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        self.log(
            action_type="llm_query",
            action_name="chat_completion",
            status=status,
            actor="llm",
            duration_ms=duration_ms,
            details={
                "model": model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                **(details or {}),
            },
        )

    def log_file_op(
        self,
        operation: str,
        path: str,
        status: str,
        user_approved: bool = False,
        duration_ms: Optional[int] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        self.log(
            action_type="file_op",
            action_name=operation,
            status=status,
            tier="write" if operation in ("write_file", "delete_file") else "read",
            user_approved=user_approved,
            resource=path,
            duration_ms=duration_ms,
            details=details,
        )

    def log_oauth(
        self,
        provider: str,
        operation: str,
        status: str,
        account: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        self.log(
            action_type="oauth",
            action_name=f"{provider}_{operation}",
            status=status,
            tier="write",
            actor="user",
            resource=f"oauth://{provider}/{account or 'unknown'}",
            details=details,
        )

    def log_system(
        self,
        event: str,
        status: str = "completed",
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        self.log(
            action_type="system",
            action_name=event,
            status=status,
            actor="system",
            details=details,
        )

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def recent(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return the most recent audit records from the DB."""
        try:
            conn = self._get_conn(self._db_path)
            rows = conn.execute(
                """
                SELECT * FROM audit_logs
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            conn.close()
            return list(rows)
        except Exception as exc:
            logger.error("Failed to query audit logs: %s", exc)
            return []

    def session_summary(self, session_id: Optional[str] = None) -> dict[str, Any]:
        """Return aggregate stats for a session."""
        sid = session_id or self._session_id
        try:
            conn = self._get_conn(self._db_path)
            rows = conn.execute(
                """
                SELECT action_type, status, COUNT(*) as cnt
                FROM audit_logs
                WHERE session_id = ?
                GROUP BY action_type, status
                """,
                (sid,),
            ).fetchall()
            conn.close()
            breakdown: dict[str, Any] = {}
            for r in rows:
                breakdown.setdefault(r["action_type"], {})[r["status"]] = r["cnt"]
            return {"session_id": sid, "breakdown": breakdown}
        except Exception as exc:
            logger.error("Session summary error: %s", exc)
            return {"session_id": sid, "breakdown": {}, "error": str(exc)}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def flush(self, timeout: float = 5.0) -> None:
        """Block until the queue is empty or timeout expires."""
        try:
            self._queue.join()
        except Exception:
            pass

    def stop(self) -> None:
        """Gracefully stop the background writer."""
        self._queue.put(None)  # sentinel
        self._writer.join(timeout=5.0)
        logger.info("AuditLogger stopped")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _write_loop(self) -> None:
        """Background thread: dequeue records and write to SQLite."""
        # Keep a persistent connection in this thread
        try:
            from db.schema import _get_connection
            conn = _get_connection(self._db_path)
        except Exception as exc:
            logger.error("AuditLogger could not open DB connection: %s", exc)
            return

        INSERT_SQL = """
            INSERT INTO audit_logs
                (timestamp, session_id, action_type, action_name, tier, status,
                 user_approved, actor, resource, details_json, duration_ms)
            VALUES
                (:timestamp, :session_id, :action_type, :action_name, :tier, :status,
                 :user_approved, :actor, :resource, :details_json, :duration_ms)
        """

        while True:
            record = self._queue.get()
            if record is None:  # shutdown sentinel
                self._queue.task_done()
                break
            try:
                conn.execute(
                    INSERT_SQL,
                    {
                        "timestamp":    record.timestamp,
                        "session_id":   record.session_id,
                        "action_type":  record.action_type,
                        "action_name":  record.action_name,
                        "tier":         record.tier,
                        "status":       record.status,
                        "user_approved": 1 if record.user_approved else 0,
                        "actor":        record.actor,
                        "resource":     record.resource,
                        "details_json": json.dumps(record.details),
                        "duration_ms":  record.duration_ms,
                    },
                )
                conn.commit()
                logger.debug(
                    "Audited: %s / %s [%s]", record.action_type, record.action_name, record.status
                )
            except Exception as exc:
                logger.error(
                    "Failed to write audit record (%s/%s): %s",
                    record.action_type, record.action_name, exc,
                )
                conn.rollback()
            finally:
                self._queue.task_done()

        conn.close()

    @staticmethod
    def _sanitise_resource(resource: Optional[str]) -> Optional[str]:
        """Strip credentials from resource strings before logging."""
        if resource is None:
            return None
        # Remove anything that looks like a token or password in URLs
        import re
        sanitised = re.sub(r"(?i)(token|key|secret|password|auth)=[^&\s]*", r"\1=***", resource)
        return sanitised[:512]  # cap at 512 chars


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_logger_instance: Optional[AuditLogger] = None


def get_audit_logger(
    db_path: Optional[Path] = None,
    session_id: Optional[str] = None,
) -> AuditLogger:
    """Return the module-level singleton AuditLogger."""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = AuditLogger(db_path=db_path, session_id=session_id)
    return _logger_instance
