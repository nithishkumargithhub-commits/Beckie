"""
JARVIS – Visible Listening Indicator & System Tray State Manager.

Manages system tray icon state transitions:
  - IDLE: JARVIS standby / monitoring wake word (green ring)
  - LISTENING: Microphone active, recording user speech (pulsing red/amber)
  - PROCESSING: Whisper STT & Intent classification running (vibrant blue)
  - SPEAKING: Piper TTS streaming speech (purple/cyan)
  - MUTED: Microphone disabled, paused, or permission denied (gray)

Emergency Pause:
  - Tray menu action immediately halts microphone, tracking, and voice integrations.
  - Tier 0 action (instant, no approval required).
  - All pause/resume actions audit-logged with timestamps.
"""

from __future__ import annotations

import enum
import logging
import threading
import time
from typing import Callable, List, Optional
from PIL import Image, ImageDraw

logger = logging.getLogger("Jarvis.Pipeline.Indicator")


class IndicatorState(str, enum.Enum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    MUTED = "muted"


# State display metadata: (primary_color, secondary_color, tooltip_text)
STATE_THEMES = {
    IndicatorState.IDLE: ((34, 197, 94), (20, 83, 45), "JARVIS – Standby (Listening for 'Hey Beckie')"),
    IndicatorState.LISTENING: ((239, 68, 68), (127, 29, 29), "JARVIS – 🔴 Listening to voice..."),
    IndicatorState.PROCESSING: ((59, 130, 246), (30, 58, 138), "JARVIS – ⚙️ Processing speech..."),
    IndicatorState.SPEAKING: ((168, 85, 247), (88, 28, 135), "JARVIS – 🔊 Speaking..."),
    IndicatorState.MUTED: ((156, 163, 175), (75, 85, 99), "JARVIS – 🔇 Paused / Microphone Muted"),
}


def create_indicator_icon(state: IndicatorState, size: int = 64) -> Image.Image:
    """Generate a clean, high-resolution circular state indicator icon."""
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    fg_color, bg_color, _ = STATE_THEMES.get(state, STATE_THEMES[IndicatorState.IDLE])

    # Outer ambient glow ring
    draw.ellipse([4, 4, size - 4, size - 4], fill=bg_color)
    # Inner active core
    draw.ellipse([12, 12, size - 12, size - 12], fill=fg_color)

    # Accent center dot
    draw.ellipse([24, 24, size - 24, size - 24], fill=(255, 255, 255, 220))

    return image


class TrayListeningIndicator:
    """System tray icon state controller with emergency pause support."""

    def __init__(
        self,
        headless: bool = False,
        on_state_change: Optional[Callable[[IndicatorState], None]] = None,
        audit_logger=None,
    ):
        self.state: IndicatorState = IndicatorState.IDLE
        self.headless = headless
        self.on_state_change = on_state_change
        self.audit_logger = audit_logger
        self.is_paused: bool = False

        self._pause_handlers: List[Callable[[], None]] = []
        self._resume_handlers: List[Callable[[], None]] = []
        self._icon = None
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None

        if not self.headless:
            self._init_tray()

    def register_pause_handler(self, handler: Callable[[], None]) -> None:
        """Register a callback executed when emergency pause is activated."""
        self._pause_handlers.append(handler)

    def register_resume_handler(self, handler: Callable[[], None]) -> None:
        """Register a callback executed when JARVIS is resumed."""
        self._resume_handlers.append(handler)

    def pause(self) -> None:
        """
        Emergency pause button: immediately ceases microphone capture,
        tracking, and integrations.
        Tier 0 (SAFE) – no approval required.
        """
        start_time = time.time()
        with self._lock:
            self.is_paused = True
            self.set_state(IndicatorState.MUTED)
            logger.warning("EMERGENCY PAUSE ACTIVATED: Stopping mic, tracking, and voice integrations.")

            for handler in self._pause_handlers:
                try:
                    handler()
                except Exception as exc:
                    logger.error("Error executing pause handler: %s", exc)

        if self.audit_logger is not None:
            self.audit_logger.log_action(
                action_type="windows_control",
                action_name="emergency_pause",
                tier="safe",
                status="paused",
                user_approved=True,
                actor="user",
                resource="system:all_inputs",
                details={"action": "pause", "state": "muted"},
                duration_ms=int((time.time() - start_time) * 1000),
            )

    def resume(self) -> None:
        """
        Resume JARVIS normal operation.
        Tier 0 (SAFE) – no approval required.
        """
        start_time = time.time()
        with self._lock:
            self.is_paused = False
            self.set_state(IndicatorState.IDLE)
            logger.info("JARVIS RESUMED: Restoring normal standby operations.")

            for handler in self._resume_handlers:
                try:
                    handler()
                except Exception as exc:
                    logger.error("Error executing resume handler: %s", exc)

        if self.audit_logger is not None:
            self.audit_logger.log_action(
                action_type="windows_control",
                action_name="emergency_pause",
                tier="safe",
                status="resumed",
                user_approved=True,
                actor="user",
                resource="system:all_inputs",
                details={"action": "resume", "state": "idle"},
                duration_ms=int((time.time() - start_time) * 1000),
            )

    def toggle_pause(self) -> bool:
        """Toggle emergency pause state. Returns True if now paused, False if resumed."""
        if self.is_paused:
            self.resume()
            return False
        else:
            self.pause()
            return True

    def _on_toggle_pause_click(self, icon=None, item=None) -> None:
        """System tray menu item click handler."""
        self.toggle_pause()

    def _init_tray(self) -> None:
        try:
            import pystray

            initial_image = create_indicator_icon(self.state)
            _, _, title = STATE_THEMES[self.state]

            def _toggle_emotion(icon=None, item=None):
                try:
                    from security.privacy_controls import get_privacy_manager
                    pm = get_privacy_manager()
                    pm.update_settings(emotion_enabled=not pm.settings.emotion_enabled)
                except Exception as e:
                    logger.debug("Error toggling emotion from tray: %s", e)

            def _toggle_neutral(icon=None, item=None):
                try:
                    from security.privacy_controls import get_privacy_manager
                    pm = get_privacy_manager()
                    pm.update_settings(neutral_mode=not pm.settings.neutral_mode)
                except Exception as e:
                    logger.debug("Error toggling neutral mode from tray: %s", e)

            def _get_emotion_label(item=None):
                try:
                    from security.privacy_controls import get_privacy_manager
                    enabled = get_privacy_manager().settings.emotion_enabled
                    return "✓ Emotion Engine: ON" if enabled else "✗ Emotion Engine: OFF"
                except Exception:
                    return "Emotion Engine"

            def _get_neutral_label(item=None):
                try:
                    from security.privacy_controls import get_privacy_manager
                    neutral = get_privacy_manager().settings.neutral_mode
                    return "✓ Neutral Mode: ON" if neutral else "✗ Neutral Mode: OFF"
                except Exception:
                    return "Neutral Mode"

            menu = pystray.Menu(
                pystray.MenuItem("JARVIS Voice Assistant", lambda: None, enabled=False),
                pystray.MenuItem(
                    lambda item: "▶ Resume JARVIS" if self.is_paused else "⏸ Emergency Pause",
                    self._on_toggle_pause_click,
                ),
                pystray.MenuItem(_get_emotion_label, _toggle_emotion),
                pystray.MenuItem(_get_neutral_label, _toggle_neutral),
                pystray.MenuItem("Exit", self.stop),
            )

            self._icon = pystray.Icon("JARVIS", initial_image, title, menu=menu)
        except Exception as exc:
            logger.warning("pystray tray icon init failed (%s), running indicator headlessly", exc)
            self.headless = True

    def start(self) -> None:
        """Start tray icon loop in background thread."""
        if self.headless or self._icon is None:
            return
        self._thread = threading.Thread(target=self._icon.run, daemon=True)
        self._thread.start()
        logger.info("Tray indicator started.")

    def stop(self) -> None:
        """Stop and remove tray icon."""
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception:
                pass
        logger.info("Tray indicator stopped.")

    def set_state(self, new_state: IndicatorState) -> None:
        """Update the indicator state and tray icon appearance."""
        if self.state == new_state:
            return
        old_state = self.state
        self.state = new_state
        logger.info("Indicator state transition: %s -> %s", old_state.value, new_state.value)

        if not self.headless and self._icon is not None:
            try:
                new_img = create_indicator_icon(new_state)
                _, _, tooltip = STATE_THEMES.get(new_state, STATE_THEMES[IndicatorState.IDLE])
                self._icon.icon = new_img
                self._icon.title = tooltip
            except Exception as exc:
                logger.debug("Could not update tray icon visual: %s", exc)

        if self.on_state_change is not None:
            try:
                self.on_state_change(new_state)
            except Exception as exc:
                logger.error("Error in on_state_change callback: %s", exc)
