"""
JARVIS – 4-tier Permission Broker.

Tiers:
  SAFE        – Automatically approved; no prompt, just logged.
  READ        – Auto-approved but always audited.
  WRITE       – Requires explicit user confirmation via CLI/UI prompt.
  DESTRUCTIVE – Requires typed confirmation phrase + double audit entry.

On every restart, sensitive (WRITE + DESTRUCTIVE) permissions are cleared.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger("Jarvis.Core.PermissionBroker")


# ---------------------------------------------------------------------------
# Tier definitions
# ---------------------------------------------------------------------------

class PermissionTier(str, Enum):
    SAFE        = "safe"         # Read-only, no side effects – auto-approved
    READ        = "read"         # Reads external state – auto-approved, audited
    WRITE       = "write"        # Mutates local state – requires user approval
    DESTRUCTIVE = "destructive"  # Irreversible or high-risk – requires typed confirmation


# Human-readable descriptions shown to users during approval prompts
_TIER_DESCRIPTIONS: dict[PermissionTier, str] = {
    PermissionTier.SAFE:        "Safe (no side-effects, auto-approved)",
    PermissionTier.READ:        "Read-only (logged)",
    PermissionTier.WRITE:       "Write / Mutate (requires your approval)",
    PermissionTier.DESTRUCTIVE: "Destructive / Irreversible (requires explicit confirmation)",
}

# Default tier assignments for well-known action names
_DEFAULT_ACTION_TIERS: dict[str, PermissionTier] = {
    # SAFE (Tier 0)
    "get_time":             PermissionTier.SAFE,
    "get_weather":          PermissionTier.SAFE,
    "calculate":            PermissionTier.SAFE,
    "list_reminders":       PermissionTier.SAFE,
    "list_meetings":        PermissionTier.SAFE,
    "tell_joke":            PermissionTier.SAFE,
    "get_system_info":      PermissionTier.SAFE,
    "get_brightness":       PermissionTier.SAFE,
    "get_volume":           PermissionTier.SAFE,
    "is_muted":             PermissionTier.SAFE,
    "list_monitors":        PermissionTier.SAFE,
    "media_play_pause":     PermissionTier.SAFE,
    "media_next":           PermissionTier.SAFE,
    "media_prev":           PermissionTier.SAFE,
    "media_stop":           PermissionTier.SAFE,
    "register_hotkey":      PermissionTier.SAFE,
    "emergency_pause":      PermissionTier.SAFE,
    "list_approved_apps":   PermissionTier.SAFE,
    "generate_report":      PermissionTier.SAFE,
    # READ (Tier 1)
    "read_clipboard":       PermissionTier.READ,
    "list_files":           PermissionTier.READ,
    "read_file":            PermissionTier.READ,
    "search_web":           PermissionTier.READ,
    "check_email":          PermissionTier.READ,
    "list_tasks":           PermissionTier.READ,
    "read_preferences":     PermissionTier.READ,
    "screenshot":           PermissionTier.READ,
    "chat_completion":      PermissionTier.READ,
    "llm_query":            PermissionTier.READ,
    "search_files":         PermissionTier.READ,
    "show_metadata":        PermissionTier.READ,
    "analyze_deletion_impact": PermissionTier.READ,
    "get_startup_status":   PermissionTier.READ,
    "code_review":          PermissionTier.READ,
    "activity_track":       PermissionTier.READ,
    # WRITE (Tier 2)
    "create_reminder":      PermissionTier.WRITE,
    "update_reminder":      PermissionTier.WRITE,
    "create_meeting":       PermissionTier.WRITE,
    "write_file":           PermissionTier.WRITE,
    "apply_patch":          PermissionTier.WRITE,
    "execute_test":         PermissionTier.WRITE,
    "start_study_session":  PermissionTier.WRITE,
    "end_study_session":    PermissionTier.WRITE,
    "send_email":           PermissionTier.WRITE,
    "set_brightness":       PermissionTier.WRITE,
    "set_volume":           PermissionTier.WRITE,
    "mute_volume":          PermissionTier.WRITE,
    "unmute_volume":        PermissionTier.WRITE,
    "toggle_mute":          PermissionTier.WRITE,
    "launch_app":           PermissionTier.WRITE,
    "enable_startup":       PermissionTier.WRITE,
    "disable_startup":      PermissionTier.WRITE,
    "write_clipboard":      PermissionTier.WRITE,
    "add_task":             PermissionTier.WRITE,
    "set_preference":       PermissionTier.WRITE,
    "run_macro":            PermissionTier.WRITE,
    # DESTRUCTIVE (Tier 3)
    "recycle_bin_move":     PermissionTier.DESTRUCTIVE,
    "delete_file":          PermissionTier.DESTRUCTIVE,
    "delete_reminder":      PermissionTier.DESTRUCTIVE,
    "delete_meeting":       PermissionTier.DESTRUCTIVE,
    "empty_trash":          PermissionTier.DESTRUCTIVE,
    "revoke_oauth":         PermissionTier.DESTRUCTIVE,
    "lock_screen":          PermissionTier.DESTRUCTIVE,
    "shutdown":             PermissionTier.DESTRUCTIVE,
    "restart":              PermissionTier.DESTRUCTIVE,
    "run_code":             PermissionTier.DESTRUCTIVE,
    "execute_shell":        PermissionTier.DESTRUCTIVE,
}


# ---------------------------------------------------------------------------
# Permission result
# ---------------------------------------------------------------------------

@dataclass
class PermissionResult:
    granted: bool
    tier: PermissionTier
    action_name: str
    session_id: str
    user_approved: bool = False
    reason: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "granted": self.granted,
            "tier": self.tier.value,
            "action_name": self.action_name,
            "session_id": self.session_id,
            "user_approved": self.user_approved,
            "reason": self.reason,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Approval callback types
# ---------------------------------------------------------------------------

# Synchronous prompt: takes (action_name, tier, description) → bool
ApprovalCallback = Callable[[str, PermissionTier, str], bool]
# Synchronous destructive confirm: takes (action_name, phrase) → bool
DestructiveCallback = Callable[[str, str], bool]


def _default_approval_callback(
    action_name: str, tier: PermissionTier, description: str
) -> bool:
    """CLI fallback: prompts on stdin."""
    prompt = (
        f"\n[JARVIS] Action requires your approval\n"
        f"  Action : {action_name}\n"
        f"  Tier   : {_TIER_DESCRIPTIONS[tier]}\n"
        f"Allow? [y/N] "
    )
    try:
        answer = input(prompt).strip().lower()
        return answer in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False


def _default_destructive_callback(action_name: str, phrase: str) -> bool:
    """CLI fallback: prompts user to type the confirmation phrase."""
    prompt = (
        f"\n[JARVIS] ⚠️  DESTRUCTIVE action requested: {action_name}\n"
        f'  Type "{phrase}" to confirm, or press Enter to cancel: '
    )
    try:
        answer = input(prompt).strip()
        return answer == phrase
    except (EOFError, KeyboardInterrupt):
        return False


# ---------------------------------------------------------------------------
# Permission Broker
# ---------------------------------------------------------------------------

class PermissionBroker:
    """
    Central authority for action permission gating.

    Sensitive (WRITE + DESTRUCTIVE) grants are held in memory only and
    are automatically cleared on instantiation (i.e., every restart).
    """

    def __init__(
        self,
        session_id: Optional[str] = None,
        approval_cb: Optional[ApprovalCallback] = None,
        destructive_cb: Optional[DestructiveCallback] = None,
        audit_callback: Optional[Callable[[PermissionResult, dict[str, Any]], None]] = None,
    ) -> None:
        self._session_id: str = session_id or uuid.uuid4().hex
        self._approval_cb = approval_cb or _default_approval_callback
        self._destructive_cb = destructive_cb or _default_destructive_callback
        self._audit_cb = audit_callback  # optional sink for audit records

        # In-memory granted permissions; cleared on restart by design
        self._granted: set[str] = set()        # "{session_id}:{action_name}"
        self._lock = threading.Lock()

        # Custom tier overrides (settable at runtime, never persisted)
        self._tier_overrides: dict[str, PermissionTier] = {}

        logger.info(
            "PermissionBroker initialised (session=%s); "
            "all WRITE/DESTRUCTIVE permissions reset.",
            self._session_id,
        )

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def register_action(self, action_name: str, tier: PermissionTier) -> None:
        """Register or override the tier for a custom action name."""
        self._tier_overrides[action_name] = tier
        logger.debug("Registered action %r with tier %s", action_name, tier.value)

    def get_tier(self, action_name: str) -> PermissionTier:
        """Resolve the tier for an action (custom overrides take precedence)."""
        if action_name in self._tier_overrides:
            return self._tier_overrides[action_name]
        return _DEFAULT_ACTION_TIERS.get(action_name, PermissionTier.WRITE)

    # ------------------------------------------------------------------
    # Core gate
    # ------------------------------------------------------------------

    def request(
        self,
        action_name: str,
        resource: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
        actor: str = "llm",
    ) -> PermissionResult:
        """
        Request permission to perform *action_name*.
        Returns a PermissionResult; callers MUST check .granted before proceeding.
        """
        tier = self.get_tier(action_name)
        details = details or {}
        grant_key = f"{self._session_id}:{action_name}"

        result = self._evaluate(
            action_name=action_name,
            tier=tier,
            grant_key=grant_key,
            resource=resource,
            actor=actor,
        )

        self._emit_audit(result, resource=resource, details=details)
        return result

    def _evaluate(
        self,
        action_name: str,
        tier: PermissionTier,
        grant_key: str,
        resource: Optional[str],
        actor: str,
    ) -> PermissionResult:
        with self._lock:
            # --- SAFE: always granted ---
            if tier == PermissionTier.SAFE:
                logger.debug("SAFE action auto-approved: %s", action_name)
                return PermissionResult(
                    granted=True,
                    tier=tier,
                    action_name=action_name,
                    session_id=self._session_id,
                    user_approved=False,
                    reason="Safe tier: auto-approved",
                )

            # --- READ: auto-approved but audited ---
            if tier == PermissionTier.READ:
                logger.debug("READ action auto-approved (audited): %s", action_name)
                return PermissionResult(
                    granted=True,
                    tier=tier,
                    action_name=action_name,
                    session_id=self._session_id,
                    user_approved=False,
                    reason="Read tier: auto-approved with audit",
                )

            # --- WRITE: check memory cache, else prompt ---
            if tier == PermissionTier.WRITE:
                if grant_key in self._granted:
                    return PermissionResult(
                        granted=True,
                        tier=tier,
                        action_name=action_name,
                        session_id=self._session_id,
                        user_approved=True,
                        reason="Previously approved in this session",
                    )
                approved = self._approval_cb(
                    action_name,
                    tier,
                    _TIER_DESCRIPTIONS[tier],
                )
                if approved:
                    self._granted.add(grant_key)
                    logger.info("WRITE permission GRANTED by user: %s", action_name)
                else:
                    logger.warning("WRITE permission DENIED by user: %s", action_name)
                return PermissionResult(
                    granted=approved,
                    tier=tier,
                    action_name=action_name,
                    session_id=self._session_id,
                    user_approved=approved,
                    reason="User approved" if approved else "User denied",
                )

            # --- DESTRUCTIVE: typed confirmation required every time ---
            if tier == PermissionTier.DESTRUCTIVE:
                phrase = f"CONFIRM {action_name.upper()}"
                confirmed = self._destructive_cb(action_name, phrase)
                if confirmed:
                    logger.warning(
                        "DESTRUCTIVE permission CONFIRMED by user: %s (resource=%s)",
                        action_name,
                        resource,
                    )
                else:
                    logger.warning(
                        "DESTRUCTIVE permission REJECTED by user: %s",
                        action_name,
                    )
                return PermissionResult(
                    granted=confirmed,
                    tier=tier,
                    action_name=action_name,
                    session_id=self._session_id,
                    user_approved=confirmed,
                    reason="User confirmed destructive action"
                    if confirmed
                    else "User rejected destructive action",
                )

        # Unreachable – but keeps the linter happy
        return PermissionResult(
            granted=False,
            tier=tier,
            action_name=action_name,
            session_id=self._session_id,
            reason="Unknown tier",
        )

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def revoke_session_permissions(self) -> None:
        """Clear all in-memory grants for the current session."""
        with self._lock:
            before = len(self._granted)
            self._granted.clear()
        logger.info("Revoked %d in-memory permission grants for session %s", before, self._session_id)

    def is_granted(self, action_name: str) -> bool:
        """Check whether WRITE permission was previously granted this session."""
        key = f"{self._session_id}:{action_name}"
        with self._lock:
            return key in self._granted

    def grant_session_action(self, action_name: str) -> None:
        """Grant in-memory permission for a specific action for this session."""
        key = f"{self._session_id}:{action_name}"
        with self._lock:
            self._granted.add(key)
        logger.info("Granted in-memory session permission for action '%s'", action_name)

    def revoke_session_action(self, action_name: str) -> None:
        """Revoke in-memory permission for a specific action for this session."""
        key = f"{self._session_id}:{action_name}"
        with self._lock:
            self._granted.discard(key)
        logger.info("Revoked in-memory session permission for action '%s'", action_name)

    # ------------------------------------------------------------------
    # Audit emit
    # ------------------------------------------------------------------

    def _emit_audit(
        self,
        result: PermissionResult,
        resource: Optional[str],
        details: dict[str, Any],
    ) -> None:
        if self._audit_cb:
            try:
                self._audit_cb(result, {"resource": resource, **details})
            except Exception as exc:
                logger.error("Audit callback error: %s", exc)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def status_summary(self) -> dict[str, Any]:
        with self._lock:
            granted_list = sorted(self._granted)
        return {
            "session_id": self._session_id,
            "granted_write_actions": [g.split(":", 1)[1] for g in granted_list],
            "tier_overrides": {k: v.value for k, v in self._tier_overrides.items()},
        }
