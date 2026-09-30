"""
JARVIS – Safe Recycle Bin File Deletion using Windows Shell API.

Features:
- Moves files and folders to the Windows Recycle Bin (SHFileOperationW + FOF_ALLOWUNDO).
- NEVER performs unrecoverable permanent deletion (no os.remove or shutil.rmtree).
- Integrated pre-flight Deletion Impact Analysis (file count, size, recency, project affiliation).
- Strict block on protected Windows system paths.
- Tier 3 (DESTRUCTIVE) – requires explicit confirmation dialog.
- Full audit logging of deletion events with before-and-after state and timestamps.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import logging
from pathlib import Path
import time
from typing import Callable, Optional, Tuple, Union

from actions.deletion_guard import DeletionImpact, DeletionImpactAnalyzer
from actions.windows_dialog import show_confirmation_dialog
from core.audit_logger import AuditLogger
from core.permission_broker import PermissionBroker, PermissionTier

logger = logging.getLogger("Jarvis.Actions.RecycleBin")

# Windows Shell API Constants
FO_DELETE = 0x0003
FOF_ALLOWUNDO = 0x0040          # Preserves undo information, moving to Recycle Bin
FOF_NOCONFIRMATION = 0x0010     # Do not show standard Windows prompt (we show our own dialog)
FOF_SILENT = 0x0004             # Do not display progress dialog
FOF_NOERRORUI = 0x0400          # Do not display system error UI


class SHFILEOPSTRUCTW(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("wFunc", wintypes.UINT),
        ("pFrom", wintypes.LPCWSTR),
        ("pTo", wintypes.LPCWSTR),
        ("fFlags", wintypes.WORD),
        ("fAnyOperationsAborted", wintypes.BOOL),
        ("hNameMappings", wintypes.LPVOID),
        ("lpszProgressTitle", wintypes.LPCWSTR),
    ]


class RecycleBinManager:
    """Manages safe item deletion via Windows Recycle Bin with impact analysis."""

    def __init__(
        self,
        broker: Optional[PermissionBroker] = None,
        audit_logger: Optional[AuditLogger] = None,
        dialog_fn: Optional[Callable[[str, str, bool], bool]] = None,
        analyzer: Optional[DeletionImpactAnalyzer] = None,
    ):
        self.broker = broker
        self.audit_logger = audit_logger
        self.dialog_fn = dialog_fn or (lambda title, msg, is_destr: show_confirmation_dialog(title, msg, is_destr))
        self.analyzer = analyzer or DeletionImpactAnalyzer(broker=broker, audit_logger=audit_logger)

    def move_to_recycle_bin(
        self,
        target_path: Union[str, Path],
        force_unconfirmed: bool = False,
    ) -> Tuple[bool, str, Optional[DeletionImpact]]:
        """
        Safely move a file or folder to the Windows Recycle Bin.
        Tier 3 (DESTRUCTIVE) – requires explicit confirmation dialog.

        Returns:
            Tuple[bool, str, Optional[DeletionImpact]]:
                (Success status, message, deletion impact analysis)
        """
        start_time = time.time()
        p = Path(target_path).resolve()
        action_name = "recycle_bin_move"

        # 1. Existence check
        if not p.exists():
            err = f"Target does not exist: {p}"
            logger.warning(err)
            return False, err, None

        # 2. Deletion Impact Analysis
        impact = self.analyzer.analyze(p)

        # 3. Block protected system paths outright
        if impact.is_system_path:
            err = (
                f"SAFETY BLOCKED: Cannot delete protected Windows system directory: {p}. "
                f"Modifying system directories could render Windows unbootable."
            )
            logger.critical(err)
            if self.audit_logger is not None:
                self.audit_logger.log_action(
                    action_type="windows_control",
                    action_name=action_name,
                    tier=PermissionTier.DESTRUCTIVE.value,
                    status="blocked_system_path",
                    user_approved=False,
                    actor="user",
                    resource=f"path:{p}",
                    details={"impact": impact.to_dict(), "error": err},
                    duration_ms=int((time.time() - start_time) * 1000),
                )
            return False, err, impact

        # 4. Tier 3 Confirmation Dialog
        user_approved = True
        if not force_unconfirmed:
            if self.broker is not None:
                perm = self.broker.request(
                    action_name=action_name,
                    resource=f"path:{p}",
                    details={"impact": impact.to_dict()},
                    actor="user",
                )
                if not perm.granted:
                    msg = f"Move to Recycle Bin for '{p.name}' was cancelled by user."
                    return False, msg, impact
                user_approved = perm.user_approved
            else:
                title = "JARVIS – Confirm Move to Recycle Bin"
                prompt_msg = (
                    f"{impact.summary}\n\n"
                    f"Notice: The target will be moved to the Windows Recycle Bin (NOT permanently erased).\n"
                    f"You can restore it later if needed.\n\n"
                    f"Do you want to send this item to the Recycle Bin?"
                )
                user_approved = self.dialog_fn(title, prompt_msg, True)
                if not user_approved:
                    msg = f"Deletion of '{p.name}' was cancelled by user."
                    if self.audit_logger is not None:
                        self.audit_logger.log_action(
                            action_type="windows_control",
                            action_name=action_name,
                            tier=PermissionTier.DESTRUCTIVE.value,
                            status="cancelled",
                            user_approved=False,
                            actor="user",
                            resource=f"path:{p}",
                            details={"impact": impact.to_dict(), "result": msg},
                            duration_ms=int((time.time() - start_time) * 1000),
                        )
                    return False, msg, impact

        # 5. Execute SHFileOperationW with FOF_ALLOWUNDO
        try:
            # Path must be double-null-terminated for SHFileOperationW
            str_path = str(p) + "\0\0"

            op = SHFILEOPSTRUCTW()
            op.hwnd = 0
            op.wFunc = FO_DELETE
            op.pFrom = str_path
            op.pTo = None
            op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI
            op.fAnyOperationsAborted = False
            op.hNameMappings = None
            op.lpszProgressTitle = None

            ret = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))

            if ret != 0 or op.fAnyOperationsAborted:
                err = f"Windows Shell operation failed with code {ret} (aborted={op.fAnyOperationsAborted})."
                logger.error(err)
                if self.audit_logger is not None:
                    self.audit_logger.log_action(
                        action_type="windows_control",
                        action_name=action_name,
                        tier=PermissionTier.DESTRUCTIVE.value,
                        status="failed",
                        user_approved=user_approved,
                        actor="user",
                        resource=f"path:{p}",
                        details={"error_code": ret, "impact": impact.to_dict()},
                        duration_ms=int((time.time() - start_time) * 1000),
                    )
                return False, err, impact

            msg = f"Successfully moved '{p.name}' ({impact.total_size_formatted}) to Windows Recycle Bin."
            logger.info(msg)

            if self.audit_logger is not None:
                self.audit_logger.log_action(
                    action_type="windows_control",
                    action_name=action_name,
                    tier=PermissionTier.DESTRUCTIVE.value,
                    status="success",
                    user_approved=user_approved,
                    actor="user",
                    resource=f"path:{p}",
                    details={
                        "file_count": impact.file_count,
                        "total_size_bytes": impact.total_size_bytes,
                        "risk_level": impact.risk_level,
                        "result": msg,
                    },
                    duration_ms=int((time.time() - start_time) * 1000),
                )

            return True, msg, impact

        except Exception as exc:
            err = f"Unexpected error moving '{p}' to Recycle Bin: {exc}"
            logger.error(err)
            if self.audit_logger is not None:
                self.audit_logger.log_action(
                    action_type="windows_control",
                    action_name=action_name,
                    tier=PermissionTier.DESTRUCTIVE.value,
                    status="error",
                    user_approved=user_approved,
                    actor="user",
                    resource=f"path:{p}",
                    details={"error": str(exc), "impact": impact.to_dict()},
                    duration_ms=int((time.time() - start_time) * 1000),
                )
            return False, err, impact


# Default singleton instance and convenience wrapper
recycle_bin = RecycleBinManager()


def move_to_recycle_bin(target_path: Union[str, Path]) -> Tuple[bool, str]:
    success, msg, _ = recycle_bin.move_to_recycle_bin(target_path)
    return success, msg
