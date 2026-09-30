"""
JARVIS – Windows Startup Option using Task Scheduler (schtasks).

Features:
- Windows Task Scheduler integration for logon startup.
- Disabled by default.
- Querying startup status is Tier 0 (SAFE / READ – no approval required).
- Enabling or disabling startup is Tier 2 (WRITE – requires explicit confirmation dialog).
- Non-admin limited privilege execution (/rl limited) for security.
- Comprehensive audit logging with timestamps.
"""

from __future__ import annotations

import logging
from pathlib import Path
import subprocess
import time
from typing import Any, Callable, Dict, Optional, Tuple

from actions.windows_dialog import show_confirmation_dialog
from core.audit_logger import AuditLogger
from core.permission_broker import PermissionBroker, PermissionTier

logger = logging.getLogger("Jarvis.Actions.StartupManager")

TASK_NAME = "JARVIS_Assistant"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TARGET_BAT = PROJECT_ROOT / "jarvis.bat"


class StartupManager:
    """Manages automatic startup via Windows Task Scheduler."""

    def __init__(
        self,
        broker: Optional[PermissionBroker] = None,
        audit_logger: Optional[AuditLogger] = None,
        dialog_fn: Optional[Callable[[str, str, bool], bool]] = None,
        task_name: str = TASK_NAME,
        cmd_runner: Optional[Callable[[list[str]], Tuple[int, str, str]]] = None,
    ):
        self.broker = broker
        self.audit_logger = audit_logger
        self.dialog_fn = dialog_fn or (lambda title, msg, is_destr: show_confirmation_dialog(title, msg, is_destr))
        self.task_name = task_name
        self._cmd_runner = cmd_runner or self._default_run_command

    @staticmethod
    def _default_run_command(cmd: list[str]) -> Tuple[int, str, str]:
        """Run system command and return (returncode, stdout, stderr)."""
        proc = subprocess.run(cmd, capture_output=True, text=True, shell=False)
        return proc.returncode, proc.stdout, proc.stderr

    def is_startup_enabled(self) -> bool:
        """
        Check if the JARVIS scheduled startup task exists.
        Tier 0 (SAFE / READ) – no approval required.
        """
        status = self.get_startup_status()
        return status.get("enabled", False)

    def get_startup_status(self) -> Dict[str, Any]:
        """
        Inspect the status of the JARVIS startup task.
        Tier 0 (SAFE / READ) – no approval required.
        """
        start_time = time.time()
        cmd = ["schtasks", "/query", "/tn", self.task_name, "/fo", "CSV"]
        code, stdout, stderr = self._cmd_runner(cmd)

        enabled = (code == 0)
        status_info = {
            "task_name": self.task_name,
            "enabled": enabled,
            "schedule": "At user logon" if enabled else "Disabled (Default)",
            "output": stdout.strip() if enabled else stderr.strip(),
        }

        if self.audit_logger is not None:
            self.audit_logger.log_action(
                action_type="windows_control",
                action_name="get_startup_status",
                tier=PermissionTier.READ.value,
                status="success",
                user_approved=True,
                actor="user",
                resource=f"task:{self.task_name}",
                details=status_info,
                duration_ms=int((time.time() - start_time) * 1000),
            )

        return status_info

    def enable_startup(
        self,
        command_path: Optional[str] = None,
        force_unconfirmed: bool = False,
    ) -> Tuple[bool, str]:
        """
        Enable JARVIS to start automatically at Windows user logon.
        Tier 2 (WRITE) – requires explicit confirmation dialog.

        Parameters:
            command_path: Path to executable or batch script.
            force_unconfirmed: If True, bypass confirmation dialog.
        """
        start_time = time.time()
        target = command_path or str(DEFAULT_TARGET_BAT)
        action_name = "enable_startup"

        # Tier 2 confirmation check
        user_approved = True
        if not force_unconfirmed:
            if self.broker is not None:
                perm = self.broker.request(
                    action_name=action_name,
                    resource=f"task:{self.task_name}",
                    details={"target_command": target},
                    actor="user",
                )
                if not perm.granted:
                    msg = "Enabling Windows startup was cancelled by user."
                    return False, msg
                user_approved = perm.user_approved
            else:
                title = "JARVIS – Confirm Windows Startup Configuration"
                prompt_msg = (
                    f"Action: Enable Automatic Windows Startup\n"
                    f"Task Name: {self.task_name}\n"
                    f"Trigger: When user logs on\n"
                    f"Command: {target}\n\n"
                    f"Do you want JARVIS to start automatically at Windows startup?"
                )
                user_approved = self.dialog_fn(title, prompt_msg, False)
                if not user_approved:
                    msg = "Enabling Windows startup was cancelled by user."
                    if self.audit_logger is not None:
                        self.audit_logger.log_action(
                            action_type="windows_control",
                            action_name=action_name,
                            tier=PermissionTier.WRITE.value,
                            status="cancelled",
                            user_approved=False,
                            actor="user",
                            resource=f"task:{self.task_name}",
                            details={"result": msg},
                            duration_ms=int((time.time() - start_time) * 1000),
                        )
                    return False, msg

        # Execute schtasks /create
        # /sc onlogon = Run on user logon
        # /rl limited = Standard user permissions (no elevation prompt)
        # /f = Overwrite existing task
        cmd = [
            "schtasks",
            "/create",
            "/tn", self.task_name,
            "/tr", f'"{target}"',
            "/sc", "onlogon",
            "/rl", "limited",
            "/f",
        ]

        try:
            code, stdout, stderr = self._cmd_runner(cmd)
            if code == 0:
                msg = f"JARVIS startup task created successfully. JARVIS will start automatically at logon."
                logger.info(msg)
                if self.audit_logger is not None:
                    self.audit_logger.log_action(
                        action_type="windows_control",
                        action_name=action_name,
                        tier=PermissionTier.WRITE.value,
                        status="success",
                        user_approved=user_approved,
                        actor="user",
                        resource=f"task:{self.task_name}",
                        details={"target_command": target, "result": msg},
                        duration_ms=int((time.time() - start_time) * 1000),
                    )
                return True, msg
            else:
                err = f"Failed to create startup task (code {code}): {stderr.strip() or stdout.strip()}"
                logger.error(err)
                if self.audit_logger is not None:
                    self.audit_logger.log_action(
                        action_type="windows_control",
                        action_name=action_name,
                        tier=PermissionTier.WRITE.value,
                        status="failed",
                        user_approved=user_approved,
                        actor="user",
                        resource=f"task:{self.task_name}",
                        details={"target_command": target, "error": err},
                        duration_ms=int((time.time() - start_time) * 1000),
                    )
                return False, err
        except Exception as exc:
            err = f"Error creating startup task: {exc}"
            logger.error(err)
            return False, err

    def disable_startup(self, force_unconfirmed: bool = False) -> Tuple[bool, str]:
        """
        Disable JARVIS automatic startup by deleting the scheduled task.
        Tier 2 (WRITE) – requires explicit confirmation dialog.
        """
        start_time = time.time()
        action_name = "disable_startup"

        # Tier 2 confirmation check
        user_approved = True
        if not force_unconfirmed:
            if self.broker is not None:
                perm = self.broker.request(
                    action_name=action_name,
                    resource=f"task:{self.task_name}",
                    details={},
                    actor="user",
                )
                if not perm.granted:
                    msg = "Disabling Windows startup was cancelled by user."
                    return False, msg
                user_approved = perm.user_approved
            else:
                title = "JARVIS – Confirm Disable Windows Startup"
                prompt_msg = (
                    f"Action: Disable Windows Startup\n"
                    f"Task Name: {self.task_name}\n\n"
                    f"Do you want to remove JARVIS from Windows startup?"
                )
                user_approved = self.dialog_fn(title, prompt_msg, False)
                if not user_approved:
                    msg = "Disabling Windows startup was cancelled by user."
                    if self.audit_logger is not None:
                        self.audit_logger.log_action(
                            action_type="windows_control",
                            action_name=action_name,
                            tier=PermissionTier.WRITE.value,
                            status="cancelled",
                            user_approved=False,
                            actor="user",
                            resource=f"task:{self.task_name}",
                            details={"result": msg},
                            duration_ms=int((time.time() - start_time) * 1000),
                        )
                    return False, msg

        cmd = ["schtasks", "/delete", "/tn", self.task_name, "/f"]
        try:
            code, stdout, stderr = self._cmd_runner(cmd)
            # Code 0 is success; if task doesn't exist, it's already disabled
            msg = f"JARVIS automatic startup has been disabled."
            logger.info(msg)
            if self.audit_logger is not None:
                self.audit_logger.log_action(
                    action_type="windows_control",
                    action_name=action_name,
                    tier=PermissionTier.WRITE.value,
                    status="success",
                    user_approved=user_approved,
                    actor="user",
                    resource=f"task:{self.task_name}",
                    details={"result": msg},
                    duration_ms=int((time.time() - start_time) * 1000),
                )
            return True, msg
        except Exception as exc:
            err = f"Error disabling startup task: {exc}"
            logger.error(err)
            return False, err


# Default singleton instance
startup_manager = StartupManager()


def is_startup_enabled() -> bool:
    return startup_manager.is_startup_enabled()


def enable_startup(command_path: Optional[str] = None) -> Tuple[bool, str]:
    return startup_manager.enable_startup(command_path)


def disable_startup() -> Tuple[bool, str]:
    return startup_manager.disable_startup()
