"""
JARVIS – Safe Windows Brightness Control using screen-brightness-control.

Features:
- Multi-monitor support (internal laptop display and external monitors via DDC/CI).
- Backend via pywin32 / WMI for internal displays and VCP for external displays.
- Tier 0 for brightness query and monitor discovery (no approval required).
- Tier 2 (WRITE) for brightness modification (requires explicit confirmation dialog).
- Detailed audit logging of all operations with timestamps.
- Robust error handling for external monitors lacking DDC/CI support.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, List, Optional, Union

from actions.windows_dialog import show_confirmation_dialog
from core.audit_logger import AuditLogger
from core.permission_broker import PermissionBroker, PermissionTier

logger = logging.getLogger("Jarvis.Actions.Brightness")


class BrightnessController:
    """Manages display brightness for internal and external monitors."""

    def __init__(
        self,
        broker: Optional[PermissionBroker] = None,
        audit_logger: Optional[AuditLogger] = None,
        dialog_fn: Optional[Callable[[str, str, bool], bool]] = None,
    ):
        self.broker = broker
        self.audit_logger = audit_logger
        self.dialog_fn = dialog_fn or (lambda title, msg, is_destr: show_confirmation_dialog(title, msg, is_destr))

    def list_monitors(self) -> List[Dict[str, Any]]:
        """
        List all detected internal and external displays with metadata.
        Tier 0 (SAFE) – no approval required.
        """
        start_time = time.time()
        displays: List[Dict[str, Any]] = []

        try:
            import screen_brightness_control as sbc

            monitors_info = sbc.list_monitors_info()
            for idx, info in enumerate(monitors_info):
                name = info.get("name", f"Display {idx}")
                model = info.get("model", "Unknown")
                method = str(info.get("method", ""))
                is_external = "VCP" in method or "vcp" in method.lower()
                manufacturer = info.get("manufacturer", "Generic")

                # Get current brightness for this specific monitor
                current_brightness = None
                try:
                    b_levels = sbc.get_brightness(display=idx)
                    if isinstance(b_levels, list) and len(b_levels) > 0:
                        current_brightness = b_levels[0]
                    elif isinstance(b_levels, int):
                        current_brightness = b_levels
                except Exception as b_err:
                    logger.debug("Could not read brightness for display %s: %s", name, b_err)

                displays.append({
                    "index": idx,
                    "name": name,
                    "model": model,
                    "manufacturer": manufacturer,
                    "is_external": is_external,
                    "method": method,
                    "brightness": current_brightness,
                })
        except Exception as exc:
            logger.error("Error listing monitors: %s", exc)

        # Audit log Tier 0 query
        if self.audit_logger is not None:
            self.audit_logger.log_action(
                action_type="windows_control",
                action_name="list_monitors",
                tier=PermissionTier.SAFE.value,
                status="success",
                user_approved=True,
                actor="user",
                resource="hardware:display",
                details={"monitor_count": len(displays)},
                duration_ms=int((time.time() - start_time) * 1000),
            )

        return displays

    def get_brightness(self, display: Optional[Union[int, str]] = None) -> Union[List[int], int, None]:
        """
        Get current brightness percentage (0-100).
        If display is None, returns a list of brightness values for all monitors.
        Tier 0 (SAFE) – no approval required.
        """
        start_time = time.time()
        try:
            import screen_brightness_control as sbc

            kwargs = {}
            if display is not None:
                kwargs["display"] = display

            result = sbc.get_brightness(**kwargs)
            val = result[0] if (isinstance(result, list) and len(result) == 1) else result

            if self.audit_logger is not None:
                self.audit_logger.log_action(
                    action_type="windows_control",
                    action_name="get_brightness",
                    tier=PermissionTier.SAFE.value,
                    status="success",
                    user_approved=True,
                    actor="user",
                    resource=f"display:{display if display is not None else 'all'}",
                    details={"brightness": val},
                    duration_ms=int((time.time() - start_time) * 1000),
                )
            return val
        except Exception as exc:
            logger.error("Failed to get brightness: %s", exc)
            if self.audit_logger is not None:
                self.audit_logger.log_action(
                    action_type="windows_control",
                    action_name="get_brightness",
                    tier=PermissionTier.SAFE.value,
                    status="failed",
                    user_approved=True,
                    actor="user",
                    resource=f"display:{display if display is not None else 'all'}",
                    details={"error": str(exc)},
                    duration_ms=int((time.time() - start_time) * 1000),
                )
            return None

    def set_brightness(
        self,
        level: int,
        display: Optional[Union[int, str]] = None,
        force_unconfirmed: bool = False,
    ) -> tuple[bool, str]:
        """
        Set screen brightness level (0-100).
        Tier 2 (WRITE) – requires confirmation dialog before modification.

        Parameters:
            level: Target brightness (0-100).
            display: Display index or name (None = all displays).
            force_unconfirmed: If True, bypasses prompt (used when already confirmed via caller).

        Returns:
            tuple[bool, str]: (Success status, descriptive message).
        """
        start_time = time.time()
        level = max(0, min(100, int(level)))
        action_name = "set_brightness"
        target_desc = f"Display {display}" if display is not None else "all displays"

        # Tier 2 confirmation check
        user_approved = True
        if not force_unconfirmed:
            if self.broker is not None:
                perm = self.broker.request(
                    action_name=action_name,
                    resource=f"display:{display if display is not None else 'all'}",
                    details={"level": level},
                    actor="user",
                )
                if not perm.granted:
                    msg = f"Brightness adjustment to {level}% on {target_desc} cancelled by user."
                    return False, msg
                user_approved = perm.user_approved
            else:
                title = "JARVIS – Confirm Brightness Change"
                prompt_msg = (
                    f"Action: Set Screen Brightness\n"
                    f"Target: {target_desc}\n"
                    f"Requested Level: {level}%\n\n"
                    f"Do you want to apply this brightness change?"
                )
                user_approved = self.dialog_fn(title, prompt_msg, False)
                if not user_approved:
                    msg = f"Brightness change to {level}% cancelled by user."
                    self._log_audit(action_name, "cancelled", level, display, False, start_time, msg)
                    return False, msg

        # Execute brightness change
        try:
            import screen_brightness_control as sbc

            kwargs = {}
            if display is not None:
                kwargs["display"] = display

            sbc.set_brightness(level, **kwargs)
            msg = f"Screen brightness set to {level}% on {target_desc}."
            logger.info(msg)
            self._log_audit(action_name, "success", level, display, user_approved, start_time, msg)
            return True, msg

        except Exception as exc:
            err_msg = str(exc)
            logger.error("Error setting brightness: %s", exc)

            # Check if external monitor DDC/CI failure
            if "VCP" in err_msg or "DDC" in err_msg or "display" in err_msg.lower():
                diagnostic = (
                    f"Failed to adjust external monitor brightness ({err_msg}). "
                    f"Please verify DDC/CI is enabled in the monitor's on-screen display (OSD) settings."
                )
            else:
                diagnostic = f"Could not adjust display brightness: {err_msg}"

            self._log_audit(action_name, "failed", level, display, user_approved, start_time, diagnostic)
            return False, diagnostic

    def _log_audit(
        self,
        action_name: str,
        status: str,
        level: int,
        display: Optional[Union[int, str]],
        approved: bool,
        start_time: float,
        message: str,
    ) -> None:
        if self.audit_logger is not None:
            self.audit_logger.log_action(
                action_type="windows_control",
                action_name=action_name,
                tier=PermissionTier.WRITE.value,
                status=status,
                user_approved=approved,
                actor="user",
                resource=f"display:{display if display is not None else 'all'}",
                details={"level": level, "result": message},
                duration_ms=int((time.time() - start_time) * 1000),
            )


# Default module instance and convenience wrappers
brightness_controller = BrightnessController()


def list_monitors() -> List[Dict[str, Any]]:
    return brightness_controller.list_monitors()


def get_brightness(display: Optional[Union[int, str]] = None) -> Union[List[int], int, None]:
    return brightness_controller.get_brightness(display)


def set_brightness(level: int = 70, display: Optional[Union[int, str]] = None) -> str:
    success, msg = brightness_controller.set_brightness(level, display)
    return msg
