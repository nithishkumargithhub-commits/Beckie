"""
Tests for Coding & Activity Assistance Features.

Covers:
1. Antigravity IDE project folder watcher (watchdog library)
2. Code review with Qwen3 8B (diff analysis, patch suggestions, approval requirement, >80% accuracy)
3. Test execution sandbox (timeout, user confirmation, unauthorized file access prevention)
4. Activity tracking (strictly approved categories, domains, study sessions, meetings)
5. Daily/weekly summary reports (SQLite aggregation, Markdown export, uncertainty statements)
6. Audit logging of all code actions (review, patch, test)
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Generator
from unittest.mock import Mock, patch

import pytest

from actions.activity_tracker import (
    APPROVED_CATEGORIES,
    ActivityCategory,
    ActivityTracker,
    get_activity_tracker,
    validate_category,
)
from actions.code_review import (
    CodeReviewResult,
    CodeReviewer,
    ReviewIssue,
    get_code_reviewer,
)
from actions.folder_watcher import (
    AntigravityFolderWatcher,
    FileChangeEvent,
    get_folder_watcher,
)
from actions.summary_reporter import (
    ActivitySummary,
    SummaryReporter,
    get_summary_reporter,
)
from actions.test_sandbox import (
    TestExecutionResult,
    TestExecutionSandbox,
    get_test_sandbox,
)
from core.audit_logger import AuditLogger
from db.schema import get_db, init_db


# ---------------------------------------------------------------------------
# 1. Antigravity Folder Watcher Tests
# ---------------------------------------------------------------------------

class TestFolderWatcher:
    def test_watcher_creation_and_lifecycle(self, tmp_path: Path) -> None:
        watcher = AntigravityFolderWatcher(watch_path=tmp_path, debounce_seconds=0.1, auto_audit=False)
        assert not watcher.is_running()
        watcher.start()
        assert watcher.is_running()
        watcher.stop()
        assert not watcher.is_running()

    def test_context_manager_support(self, tmp_path: Path) -> None:
        with AntigravityFolderWatcher(watch_path=tmp_path, debounce_seconds=0.1, auto_audit=False) as watcher:
            assert watcher.is_running()
        assert not watcher.is_running()

    def test_debounce_and_event_notification(self, tmp_path: Path) -> None:
        received_events: list[FileChangeEvent] = []
        watcher = AntigravityFolderWatcher(watch_path=tmp_path, debounce_seconds=0.1, auto_audit=False)
        watcher.add_listener(lambda ev: received_events.append(ev))

        watcher.start()
        try:
            # Create a code file
            code_file = tmp_path / "hello.py"
            code_file.write_text("print('hello')", encoding="utf-8")

            # Wait for debouncing
            time.sleep(0.4)

            # Modify file rapidly
            code_file.write_text("print('hello world')", encoding="utf-8")
            time.sleep(0.4)

            assert len(received_events) >= 1
            latest = received_events[-1]
            assert latest.is_code is True
            assert "hello.py" in latest.file_path
            assert latest.event_type in ("created", "modified")
        finally:
            watcher.stop()

    def test_ignored_directories_and_files(self, tmp_path: Path) -> None:
        received_events: list[FileChangeEvent] = []
        watcher = AntigravityFolderWatcher(watch_path=tmp_path, debounce_seconds=0.1, auto_audit=False)
        watcher.add_listener(lambda ev: received_events.append(ev))

        watcher.start()
        try:
            # Create files in ignored dir (.git, .venv)
            git_dir = tmp_path / ".git"
            git_dir.mkdir()
            (git_dir / "index").write_text("dummy", encoding="utf-8")

            # Create ignored extension (.tmp, .db)
            (tmp_path / "cache.db").write_text("dummy", encoding="utf-8")

            time.sleep(0.3)
            # Ignored files should not trigger code events
            assert len(received_events) == 0
        finally:
            watcher.stop()


# ---------------------------------------------------------------------------
# 2. Code Review & Patch Tests (Qwen3 8B, Diff, Approval, >80% Accuracy)
# ---------------------------------------------------------------------------

class TestCodeReview:
    @pytest.fixture
    def reviewer(self) -> CodeReviewer:
        return CodeReviewer(model_name="qwen3:8b", auto_audit=False)

    def test_clean_code_passes(self, reviewer: CodeReviewer) -> None:
        code = (
            "def add_numbers(a: int, b: int) -> int:\n"
            "    \"\"\"Adds two integers safely.\"\"\"\n"
            "    return a + b\n"
        )
        res = reviewer.review_code(code, filename="clean.py")
        assert res.passed is True
        assert res.score >= 80
        assert len(res.issues) == 0
        assert "uncertainty_statement" in res.to_dict()

    def test_detects_security_vulnerabilities(self, reviewer: CodeReviewer) -> None:
        # SQL Injection
        sql_vuln = "def get_user(uid):\n    return db.execute(f'SELECT * FROM users WHERE id = {uid}')\n"
        res = reviewer.review_code(sql_vuln)
        assert any(i.rule_id == "SEC_SQL_INJECTION" for i in res.issues)
        assert res.passed is False

        # Insecure Shell Execution
        shell_vuln = "import subprocess\ndef run(cmd):\n    subprocess.run(cmd, shell=True)\n"
        res = reviewer.review_code(shell_vuln)
        assert any(i.rule_id == "SEC_SUBPROCESS_SHELL" for i in res.issues)

        # Unsafe Eval
        eval_vuln = "def calc(expr):\n    return eval(expr)\n"
        res = reviewer.review_code(eval_vuln)
        assert any(i.rule_id == "SEC_UNSAFE_EXEC" for i in res.issues)

        # Path Traversal
        traversal = "def read(fname):\n    return open('../secrets/' + fname).read()\n"
        res = reviewer.review_code(traversal)
        assert any(i.rule_id == "SEC_PATH_TRAVERSAL" for i in res.issues)

    def test_detects_bugs_and_syntax_errors(self, reviewer: CodeReviewer) -> None:
        # Zero division
        zero_div = "def calculate():\n    return 10 / 0\n"
        res = reviewer.review_code(zero_div)
        assert any(i.rule_id == "BUG_ZERO_DIVISION" for i in res.issues)

        # Mutable default argument
        mutable_def = "def append_val(val, target=[]):\n    target.append(val)\n    return target\n"
        res = reviewer.review_code(mutable_def)
        assert any(i.rule_id == "BUG_MUTABLE_DEFAULT" for i in res.issues)

        # Syntax error
        syntax_err = "def broken(\n    return 42\n"
        res = reviewer.review_code(syntax_err)
        assert any(i.rule_id == "SYNTAX_ERROR" for i in res.issues)
        assert res.passed is False

    def test_diff_analysis(self, reviewer: CodeReviewer) -> None:
        diff_str = (
            "--- a/calc.py\n"
            "+++ b/calc.py\n"
            "@@ -1,3 +1,3 @@\n"
            " def divide(x, y):\n"
            "-    return x / y\n"
            "+    return eval(x + '/' + y)\n"
        )
        res = reviewer.review_diff(diff_str)
        assert any(i.rule_id == "SEC_UNSAFE_EXEC" for i in res.issues)
        assert res.passed is False

    def test_accuracy_benchmark_exceeds_80_percent(self, reviewer: CodeReviewer) -> None:
        """
        Benchmark test verifying code review accuracy >80% across sample projects / snippets.
        """
        samples = [
            # (code, has_flaw, label)
            ("def safe_func(x, y): return x + y", False, "safe_func"),
            ("def vuln_sql(uid): conn.execute(f'SELECT * FROM x WHERE id={uid}')", True, "sql_injection"),
            ("def vuln_eval(code): return eval(code)", True, "eval_exec"),
            ("def vuln_shell(c): os.system(c)", True, "os_system"),
            ("def div_zero(): return 100 / 0", True, "div_zero"),
            ("def mutable(x=[]): pass", True, "mutable_default"),
            ("def open_leak(): f = open('test.txt'); return f.read()", True, "resource_leak"),
            ("def syntax_fail(:", True, "syntax_error"),
            ("def clean_filter(items): return [i for i in items if i > 0]", False, "clean_filter"),
            ("def safe_subproc(args): subprocess.run(args, shell=False)", False, "safe_subprocess"),
        ]

        correct_classifications = 0
        for code, expected_flawed, name in samples:
            res = reviewer.review_code(code, filename=f"{name}.py")
            detected_flawed = not res.passed or len(res.issues) > 0
            if detected_flawed == expected_flawed:
                correct_classifications += 1

        accuracy = correct_classifications / len(samples)
        # Requirement: Code review accuracy > 80% on sample projects
        assert accuracy >= 0.80, f"Code review accuracy was {accuracy*100:.1f}%, expected >= 80%"

    def test_patch_application_requires_user_approval(self, reviewer: CodeReviewer, tmp_path: Path) -> None:
        target = tmp_path / "fixme.py"
        target.write_text("x = 10 / 0\n", encoding="utf-8")

        # Without user approval -> strictly DENIED
        success, msg = reviewer.apply_patch(target, "x = 10 / 1\n", user_approved=False)
        assert success is False
        assert "User approval required" in msg
        assert target.read_text(encoding="utf-8") == "x = 10 / 0\n"

        # With user approval -> APPLIED with backup
        success, msg = reviewer.apply_patch(target, "x = 10 / 1\n", user_approved=True)
        assert success is True
        assert target.read_text(encoding="utf-8") == "x = 10 / 1\n"
        assert (tmp_path / "fixme.py.bak").exists()


# ---------------------------------------------------------------------------
# 3. Test Execution Sandbox Tests (Timeout, User Confirmation, Security)
# ---------------------------------------------------------------------------

class TestSandbox:
    @pytest.fixture
    def sandbox(self, tmp_path: Path) -> TestExecutionSandbox:
        return TestExecutionSandbox(sandbox_root=tmp_path, default_timeout_seconds=2.0, auto_audit=False)

    def test_execution_requires_user_confirmation(self, sandbox: TestExecutionSandbox) -> None:
        cmd = [sys.executable, "-c", "print('hello')"]
        # Without confirmation -> denied
        res = sandbox.execute_test(cmd, user_confirmed=False)
        assert res.success is False
        assert res.status == "denied"
        assert "user confirmation required" in res.error.lower()

        # With confirmation -> executed
        res = sandbox.execute_test(cmd, user_confirmed=True)
        assert res.success is True
        assert res.status == "completed"
        assert res.stdout == "hello"

    def test_timeout_enforcement(self, sandbox: TestExecutionSandbox) -> None:
        # Command that hangs for 10 seconds
        cmd = [sys.executable, "-c", "import time; time.sleep(10)"]
        res = sandbox.execute_test(cmd, user_confirmed=True, timeout=0.5)
        assert res.success is False
        assert res.status == "timeout"
        assert "timed out" in res.error.lower()

    def test_prevents_unauthorized_file_access(self, sandbox: TestExecutionSandbox, tmp_path: Path) -> None:
        # 1. Target outside sandbox root
        outside_path = tmp_path.parent / "unauthorized.txt"
        is_safe, reason = sandbox.validate_path_safety(outside_path)
        assert is_safe is False
        assert "outside sandbox root" in reason

        # 2. Path traversal
        traversal_path = tmp_path / ".." / "outside.txt"
        is_safe, reason = sandbox.validate_path_safety(traversal_path)
        assert is_safe is False
        assert "Path traversal" in reason

        # 3. Sensitive file access (.env, credentials)
        sensitive_file = tmp_path / ".env"
        is_safe, reason = sandbox.validate_path_safety(sensitive_file)
        assert is_safe is False
        assert "sensitive credential file" in reason

        # Executing command with unauthorized path should be blocked
        cmd = [sys.executable, "-c", "pass", str(sensitive_file)]
        res = sandbox.execute_test(cmd, user_confirmed=True)
        assert res.success is False
        assert res.status == "blocked"

    def test_ast_script_inspection_blocks_credential_theft(self, sandbox: TestExecutionSandbox, tmp_path: Path) -> None:
        malicious_script = tmp_path / "steal.py"
        malicious_script.write_text("open('.env').read()\n", encoding="utf-8")

        res = sandbox.execute_test(
            [sys.executable, str(malicious_script)],
            user_confirmed=True,
            test_file=malicious_script,
        )
        assert res.success is False
        assert res.status == "blocked"
        assert "sensitive file" in res.error.lower()

    def test_environment_scrubbing(self, sandbox: TestExecutionSandbox) -> None:
        clean_env = sandbox._prepare_sanitized_environment()
        for key in clean_env.keys():
            k_upper = key.upper()
            assert "SECRET" not in k_upper
            assert "TOKEN" not in k_upper
            assert "KEY" not in k_upper
            assert "PASSWORD" not in k_upper


# ---------------------------------------------------------------------------
# 4. Activity Tracker Tests (Approved Categories Only, Study, Meetings)
# ---------------------------------------------------------------------------

class TestActivityTracker:
    @pytest.fixture
    def tracker(self, tmp_db: Path) -> ActivityTracker:
        return ActivityTracker(db_path=tmp_db)

    def test_categories_match_approved_list_only(self) -> None:
        expected = {
            "Development", "Meeting", "Study Session", "Browser Research",
            "Communication", "Utility", "Break / Idle"
        }
        assert APPROVED_CATEGORIES == expected

        # Valid categories validate
        for cat in expected:
            assert validate_category(cat) == cat

        # Disallowed category raises ValueError
        with pytest.raises(ValueError) as exc:
            validate_category("UnauthorizedGamingCategory")
        assert "Disallowed category" in str(exc.value)

    def test_app_and_domain_classification(self, tracker: ActivityTracker) -> None:
        # Development
        assert tracker.classify_activity("code.exe") == ActivityCategory.DEVELOPMENT
        assert tracker.classify_activity("chrome.exe", domain="github.com") == ActivityCategory.DEVELOPMENT

        # Meeting
        assert tracker.classify_activity("zoom.exe") == ActivityCategory.MEETING
        assert tracker.classify_activity("chrome.exe", domain="meet.google.com") == ActivityCategory.MEETING

        # Study Session
        assert tracker.classify_activity("chrome.exe", domain="coursera.org") == ActivityCategory.STUDY_SESSION

        # Communication
        assert tracker.classify_activity("slack.exe") == ActivityCategory.COMMUNICATION

        # All results strictly in approved list
        all_results = [
            tracker.classify_activity("code.exe").value,
            tracker.classify_activity("zoom.exe").value,
            tracker.classify_activity("chrome.exe", domain="github.com").value,
        ]
        for r in all_results:
            assert r in APPROVED_CATEGORIES

    def test_study_sessions_lifecycle(self, tracker: ActivityTracker, tmp_db: Path) -> None:
        # Start session
        session = tracker.start_study_session(subject="Algorithms", goal="Solve dynamic programming problems")
        assert session["subject"] == "Algorithms"
        assert tracker.get_active_study_session() is not None

        # End session
        res = tracker.end_study_session(session["session_id"], notes="Solved 3 Leetcode problems")
        assert res["status"] == "completed"
        assert tracker.get_active_study_session() is None

        # Verify DB row
        with get_db(tmp_db) as conn:
            row = conn.execute("SELECT * FROM study_sessions WHERE session_id = ?", (session["session_id"],)).fetchone()
            assert row is not None
            assert row["subject"] == "Algorithms"
            assert row["status"] == "completed"

    def test_meeting_logging(self, tracker: ActivityTracker, tmp_db: Path) -> None:
        rec = tracker.log_meeting(
            title="Sprint Planning Meeting",
            duration_sec=1800.0,
            domain="meet.google.com",
            attendees=["alice", "bob"],
        )
        assert rec.category == ActivityCategory.MEETING.value

        with get_db(tmp_db) as conn:
            row = conn.execute("SELECT * FROM activity_logs WHERE category = 'Meeting'").fetchone()
            assert row is not None
            assert "Sprint Planning" in row["window_title"]
            assert row["duration_sec"] == 1800.0


# ---------------------------------------------------------------------------
# 5. Summary Reporter Tests (SQLite Aggregation, Markdown, Uncertainty)
# ---------------------------------------------------------------------------

class TestSummaryReporter:
    @pytest.fixture
    def reporter(self, tmp_db: Path, tmp_path: Path) -> SummaryReporter:
        return SummaryReporter(db_path=tmp_db, reports_dir=tmp_path / "reports")

    def test_daily_and_weekly_report_generation(self, reporter: SummaryReporter, tmp_db: Path) -> None:
        # Seed activity data
        tracker = ActivityTracker(db_path=tmp_db)
        tracker.log_activity("Development", "code.exe", "test.py - VS Code", domain=None, duration_sec=7200.0)
        tracker.log_activity("Meeting", "zoom.exe", "Team Standup", domain="zoom.us", duration_sec=1800.0)
        tracker.log_activity("Study Session", "chrome.exe", "Coursera ML", domain="coursera.org", duration_sec=3600.0)

        # 1. Daily report
        daily = reporter.generate_daily_report(export_file=True)
        assert daily.period_type == "daily"
        assert daily.total_time_hours > 0
        assert "Development" in daily.category_breakdown

        # Mandatory requirement: Uncertainty statement present
        assert "Uncertainty" in daily.uncertainty_statement or "uncertainty" in daily.uncertainty_statement.lower()
        assert "Uncertainty" in daily.markdown_content

        # 2. Weekly report
        weekly = reporter.generate_weekly_report(export_file=True)
        assert weekly.period_type == "weekly"
        assert "Uncertainty" in weekly.uncertainty_statement
        assert "## 1. Activity Breakdown (Approved Categories Only)" in weekly.markdown_content


# ---------------------------------------------------------------------------
# 6. Audit Logging of All Code Actions (review, patch, test)
# ---------------------------------------------------------------------------

class TestCodeActionAuditLogging:
    def test_audit_logs_code_review_patch_and_test(self, tmp_db: Path, tmp_path: Path) -> None:
        audit = AuditLogger(db_path=tmp_db)

        # 1. Review action
        reviewer = CodeReviewer(auto_audit=True, audit_logger=audit)
        reviewer._log_audit_review("test.py", CodeReviewResult(passed=True, score=95, duration_ms=15))

        # 2. Patch action
        reviewer._log_audit_patch("test.py", status="completed", user_approved=True, details={})

        # 3. Test action
        sandbox = TestExecutionSandbox(sandbox_root=tmp_path, auto_audit=True, audit_logger=audit)
        sandbox._log_audit(["pytest", "tests"], status="completed", user_approved=True, duration_ms=250)

        audit.flush()

        with get_db(tmp_db) as conn:
            rows = conn.execute("SELECT action_type, action_name, status, user_approved FROM audit_logs").fetchall()
            action_types = {r["action_type"] for r in rows}
            assert "code_review" in action_types
            assert "code_patch" in action_types
            assert "code_test" in action_types
        audit.stop()
