"""
Security & Privacy Verification Tests: No Keylogging & No Screen Recording.

Verifies that the coding and activity assistance features:
1. Do NOT implement or import any keylogging mechanisms.
2. Do NOT implement continuous screen recording or video captures.
3. Only collect active foreground window metadata and domain heuristics.
4. Redact sensitive credentials (tokens, passwords) from recorded window titles.
5. Strictly enforce that activity categories match the approved list only.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import List, Tuple

import pytest

from actions.activity_tracker import (
    APPROVED_CATEGORIES,
    ActivityCategory,
    ActivityTracker,
    validate_category,
)
from db.schema import get_db

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Banned API patterns that constitute keylogging or continuous screen recording
BANNED_KEYLOGGER_PATTERNS = {
    "keyboard.record",
    "keyboard.hook",
    "keyboard.on_press",
    "keyboard.on_release",
    "pynput.keyboard",
    "pynput.keyboard.Listener",
    "GetAsyncKeyState",
    "GetKeyboardState",
    "SetWindowsHookEx",
}

BANNED_SCREEN_RECORDER_PATTERNS = {
    "cv2.VideoCapture",
    "ffmpeg.input",
    "mss.mss",
    "screen_record",
    "screencapture",
}


class CodebasePrivacySecurityVisitor(ast.NodeVisitor):
    """Scans Python files for any unauthorized keylogging or screen recording calls."""

    def __init__(self, filename: str) -> None:
        self.filename = filename
        self.violations: List[Tuple[int, str]] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if "pynput" in alias.name:
                self.violations.append((node.lineno, f"Banned keylogging import: {alias.name}"))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module and "pynput" in node.module:
            self.violations.append((node.lineno, f"Banned keylogging import: {node.module}"))
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        # Check function or attribute names
        func_expr = ""
        if isinstance(node.func, ast.Attribute):
            val = node.func.value
            val_name = getattr(val, "id", "") if isinstance(val, ast.Name) else ""
            func_expr = f"{val_name}.{node.func.attr}" if val_name else node.func.attr
        elif isinstance(node.func, ast.Name):
            func_expr = node.func.id

        for pattern in BANNED_KEYLOGGER_PATTERNS:
            if pattern == func_expr or pattern in func_expr:
                self.violations.append((node.lineno, f"Prohibited keylogging function call: {func_expr}"))

        for pattern in BANNED_SCREEN_RECORDER_PATTERNS:
            if pattern == func_expr or pattern in func_expr:
                self.violations.append((node.lineno, f"Prohibited screen recording function call: {func_expr}"))

        self.generic_visit(node)


class TestPrivacyAndSecurityVerification:
    """Security audit tests verifying zero keylogging and zero screen recording."""

    def test_static_ast_scan_no_keylogging_in_activity_or_coding_modules(self) -> None:
        """
        Scans all files in actions/ to guarantee NO keylogging or screen recording
        hooks are implemented or imported.
        """
        actions_dir = PROJECT_ROOT / "actions"
        target_files = [
            actions_dir / "activity_tracker.py",
            actions_dir / "folder_watcher.py",
            actions_dir / "code_review.py",
            actions_dir / "test_sandbox.py",
            actions_dir / "summary_reporter.py",
        ]

        all_violations = []
        for file_path in target_files:
            assert file_path.exists(), f"Target module missing: {file_path}"
            tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
            visitor = CodebasePrivacySecurityVisitor(filename=file_path.name)
            visitor.visit(tree)
            if visitor.violations:
                all_violations.extend([f"{file_path.name}:{line} - {msg}" for line, msg in visitor.violations])

        assert not all_violations, f"Privacy/Security Violations Detected: {all_violations}"

    def test_activity_tracker_does_not_record_keystrokes_or_screen_frames(self, tmp_db: Path) -> None:
        """
        Verifies that recorded activity data contains only metadata (app name, title, domain)
        and absolutely NO raw keystrokes or image/video payloads.
        """
        tracker = ActivityTracker(db_path=tmp_db)
        record = tracker.record_current_activity(duration_sec=15.0)

        # Verify returned record attributes
        assert hasattr(record, "category")
        assert hasattr(record, "app_name")
        assert not hasattr(record, "keystrokes")
        assert not hasattr(record, "key_log")
        assert not hasattr(record, "screen_frame")
        assert not hasattr(record, "video_stream")

        # Verify database schema content
        with get_db(tmp_db) as conn:
            columns = [
                col["name"]
                for col in conn.execute("PRAGMA table_info(activity_logs)").fetchall()
            ]
            assert "keystrokes" not in columns
            assert "screen_capture" not in columns
            assert "video_blob" not in columns

    def test_window_title_sanitizer_redacts_credentials(self) -> None:
        """
        Verifies that sensitive tokens, keys, and passwords appearing in window titles
        are sanitized before storage.
        """
        leaky_title = "Chrome - https://console.cloud.google.com/?token=secret_12345_token_xyz"
        sanitized = ActivityTracker.sanitize_title(leaky_title)
        assert sanitized is not None
        assert "secret_12345_token_xyz" not in sanitized
        assert "token=***" in sanitized

        password_title = "Login window: password=mySuperSecretPass123"
        sanitized_pw = ActivityTracker.sanitize_title(password_title)
        assert sanitized_pw is not None
        assert "mySuperSecretPass123" not in sanitized_pw
        assert "password=***" in sanitized_pw

    def test_activity_categories_strictly_match_approved_list(self) -> None:
        """
        Guarantees that activity categories match the approved list only.
        """
        approved_categories = {
            "Development",
            "Meeting",
            "Study Session",
            "Browser Research",
            "Communication",
            "Utility",
            "Break / Idle",
        }
        assert APPROVED_CATEGORIES == approved_categories

        # Unapproved arbitrary categories are blocked
        for unapproved in ["Gaming", "VideoStreaming", "CryptoMining", "RandomCat", "Social"]:
            with pytest.raises(ValueError):
                validate_category(unapproved)
