"""
JARVIS – @audit_log and @require_permission decorators.

Usage:

    from core.decorators import audit_log, require_permission
    from core.permission_broker import PermissionTier

    @audit_log(action_type="file_op", action_name="read_file", tier="read")
    def read_file(path: str) -> str:
        ...

    @require_permission("delete_file", PermissionTier.DESTRUCTIVE)
    @audit_log(action_type="file_op", action_name="delete_file", tier="destructive")
    def delete_file(path: str) -> None:
        ...

Both decorators are composable and thread-safe.
"""

from __future__ import annotations

import functools
import logging
import time
import traceback
from typing import Any, Callable, Optional, TypeVar

logger = logging.getLogger("Jarvis.Core.Decorators")

F = TypeVar("F", bound=Callable[..., Any])


# ---------------------------------------------------------------------------
# @audit_log
# ---------------------------------------------------------------------------

def audit_log(
    action_type: str,
    action_name: Optional[str] = None,
    tier: str = "read",
    actor: str = "llm",
    extract_resource: Optional[Callable[..., Optional[str]]] = None,
) -> Callable[[F], F]:
    """
    Decorator that records every function call to the JARVIS audit log.

    Args:
        action_type:       One of: permission_check | llm_query | file_op | oauth | system
        action_name:       Audit action label. Defaults to the decorated function name.
        tier:              Permission tier string: safe | read | write | destructive
        actor:             Who triggers this call: llm | user | system | daemon
        extract_resource:  Optional callable(args, kwargs) -> str for resource labelling.

    The decorator records:
        - start timestamp
        - status: "completed" | "error"
        - duration_ms
        - exception details on error (without leaking secrets)
    """

    def decorator(fn: F) -> F:
        resolved_name = action_name or fn.__name__

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.monotonic()
            resource: Optional[str] = None

            if extract_resource is not None:
                try:
                    resource = extract_resource(args, kwargs)
                except Exception:
                    pass

            try:
                result = fn(*args, **kwargs)
                duration_ms = int((time.monotonic() - start) * 1000)
                _emit_audit(
                    action_type=action_type,
                    action_name=resolved_name,
                    tier=tier,
                    actor=actor,
                    status="completed",
                    resource=resource,
                    duration_ms=duration_ms,
                )
                return result

            except Exception as exc:
                duration_ms = int((time.monotonic() - start) * 1000)
                _emit_audit(
                    action_type=action_type,
                    action_name=resolved_name,
                    tier=tier,
                    actor=actor,
                    status="error",
                    resource=resource,
                    duration_ms=duration_ms,
                    details={"error": str(exc), "type": type(exc).__name__},
                )
                raise

        return wrapper  # type: ignore[return-value]

    return decorator


def audit_log_async(
    action_type: str,
    action_name: Optional[str] = None,
    tier: str = "read",
    actor: str = "llm",
    extract_resource: Optional[Callable[..., Optional[str]]] = None,
) -> Callable[[F], F]:
    """Async variant of @audit_log for coroutine functions."""

    def decorator(fn: F) -> F:
        resolved_name = action_name or fn.__name__

        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.monotonic()
            resource: Optional[str] = None

            if extract_resource is not None:
                try:
                    resource = extract_resource(args, kwargs)
                except Exception:
                    pass

            try:
                result = await fn(*args, **kwargs)
                duration_ms = int((time.monotonic() - start) * 1000)
                _emit_audit(
                    action_type=action_type,
                    action_name=resolved_name,
                    tier=tier,
                    actor=actor,
                    status="completed",
                    resource=resource,
                    duration_ms=duration_ms,
                )
                return result

            except Exception as exc:
                duration_ms = int((time.monotonic() - start) * 1000)
                _emit_audit(
                    action_type=action_type,
                    action_name=resolved_name,
                    tier=tier,
                    actor=actor,
                    status="error",
                    resource=resource,
                    duration_ms=duration_ms,
                    details={"error": str(exc), "type": type(exc).__name__},
                )
                raise

        return wrapper  # type: ignore[return-value]

    return decorator


# ---------------------------------------------------------------------------
# @require_permission
# ---------------------------------------------------------------------------

def require_permission(
    action_name: str,
    tier: Optional[Any] = None,  # PermissionTier enum
    broker_attr: str = "_broker",
    session_attr: str = "_session_id",
) -> Callable[[F], F]:
    """
    Decorator that gates a function behind the PermissionBroker.

    The decorated function's first positional argument (``self``) must expose
    a PermissionBroker as ``self.<broker_attr>``.  If the broker is not
    present, the function is called directly (fail-open for standalone use).

    Args:
        action_name:   The logical action name to check.
        tier:          Optional PermissionTier override to register for this action.
        broker_attr:   Attribute name on ``self`` holding the PermissionBroker.
        session_attr:  Attribute name on ``self`` holding the session ID.

    Raises:
        PermissionError: If the permission broker denies the request.
    """

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            broker = None
            if args:
                broker = getattr(args[0], broker_attr, None)

            if broker is None:
                logger.debug(
                    "No broker found on self.%s; skipping permission gate for %s",
                    broker_attr,
                    action_name,
                )
                return fn(*args, **kwargs)

            # Optionally register a custom tier override
            if tier is not None:
                broker.register_action(action_name, tier)

            result = broker.request(action_name)
            if not result.granted:
                raise PermissionError(
                    f"Action '{action_name}' denied by PermissionBroker "
                    f"(tier={result.tier.value}, reason={result.reason})"
                )

            return fn(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


# ---------------------------------------------------------------------------
# Internal emit helper
# ---------------------------------------------------------------------------

def _emit_audit(
    action_type: str,
    action_name: str,
    tier: str,
    actor: str,
    status: str,
    resource: Optional[str],
    duration_ms: int,
    details: Optional[dict[str, Any]] = None,
) -> None:
    """
    Emit an audit record to the AuditLogger singleton (if initialised).
    Silently no-ops if the logger is not yet set up.
    """
    try:
        from core.audit_logger import get_audit_logger
        al = get_audit_logger()
        al.log(
            action_type=action_type,
            action_name=action_name,
            status=status,
            tier=tier,
            actor=actor,
            resource=resource,
            duration_ms=duration_ms,
            details=details or {},
        )
    except Exception as exc:
        logger.debug("Audit emit failed (non-fatal): %s", exc)
