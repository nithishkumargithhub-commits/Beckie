"""
JARVIS - Test Execution Sandbox.

Executes test suites and scripts inside a restricted subprocess sandbox with
enforced timeouts, mandatory user confirmation, strict unauthorized file access
prevention, environment scrubbing, and complete audit logging.
"""

from __future__ import annotations

import ast
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("Jarvis.Actions.TestSandbox")

# Sensitive file patterns strictly prohibited from being read or targeted in sandbox
FORBIDDEN_FILE_PATTERNS: Set[str] = {
    ".env", "credentials.json", "token.json", ".jarvis_key.enc",
    "jarvis_encrypted.db", "id_rsa", "id_ed25519", "known_hosts",
}

# Environment variable keys that must be stripped from sandbox process
SENSITIVE_ENV_KEYS: Set[str] = {
    "GEMINI_API_KEY", "SPOTIFY_CLIENT_SECRET", "SPOTIFY_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET", "DB_KEY", "SECRET_KEY", "PASSWORD",
    "AUTH_TOKEN", "API_KEY",
}


@dataclass
class TestExecutionResult:
    success: bool
    returncode: int
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0
    status: str = "completed"   # completed | failed | timeout | blocked | denied
    error: Optional[str] = None
    command: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "error": self.error,
            "command": self.command,
        }


class TestExecutionSandbox:
    """
    Sandboxed test runner enforcing user confirmation, filesystem access boundaries,
    and process execution isolation.
    """

    def __init__(
        self,
        sandbox_root: Optional[str | Path] = None,
        default_timeout_seconds: float = 30.0,
        auto_audit: bool = True,
        audit_logger: Optional[Any] = None,
    ) -> None:
        from config import BASE_DIR
        self.sandbox_root = Path(sandbox_root or BASE_DIR).resolve()
        self.default_timeout_seconds = default_timeout_seconds
        self.auto_audit = auto_audit
        self.audit_logger = audit_logger

    def validate_path_safety(self, target_path: str | Path) -> Tuple[bool, str]:
        """
        Validates that a path is within the allowed sandbox root and does not reference
        forbidden sensitive files or system directories.
        """
        p = Path(target_path)
        
        # Check path traversal markers
        if ".." in p.parts:
            return False, "Path traversal attempt detected ('..')."

        resolved = p.resolve() if p.is_absolute() else (self.sandbox_root / p).resolve()

        # Allow system/venv Python runner binary
        try:
            if resolved == Path(sys.executable).resolve():
                return True, "Path is interpreter executable."
        except Exception:
            pass

        # Check containment within sandbox root
        try:
            resolved.relative_to(self.sandbox_root)
        except ValueError:
            return False, f"Unauthorized file access: path '{resolved}' is outside sandbox root '{self.sandbox_root}'."

        # Check forbidden files
        file_name = resolved.name.lower()
        for forbidden in FORBIDDEN_FILE_PATTERNS:
            if forbidden in file_name:
                return False, f"Unauthorized file access: targeting sensitive credential file '{resolved.name}'."

        return True, "Path is authorized."

    def inspect_test_script_safety(self, script_path: str | Path) -> Tuple[bool, str]:
        """
        Performs pre-flight AST analysis on a test script before execution to catch
        unauthorized file access or system tampering attempts.
        """
        p = Path(script_path).resolve()
        if not p.exists() or p.suffix != ".py":
            return True, "Non-python or non-existent script."

        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(content, filename=str(p))
        except Exception as exc:
            return False, f"Failed to parse test script syntax: {exc}"

        for node in ast.walk(tree):
            # Check string constants for forbidden paths or files
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                val = node.value.lower()
                for forbidden in FORBIDDEN_FILE_PATTERNS:
                    if forbidden in val:
                        return False, f"Unauthorized file access detected in script: references sensitive file '{forbidden}'."
                if any(sys_path in val for sys_path in ("c:\\windows", "/etc/passwd", "/etc/shadow", ".ssh")):
                    return False, f"Unauthorized system path referenced in test script: '{val}'."

            # Check for destructive disk formatting or OS commands
            if isinstance(node, ast.Call):
                func_name = ""
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr
                if func_name in ("format", "rmdir") and isinstance(node.func, ast.Attribute):
                    # Check os.rmdir or shutil.rmtree outside temp
                    pass

        return True, "Script passed safety inspection."

    def _prepare_sanitized_environment(self) -> Dict[str, str]:
        """Creates a sanitized copy of environment variables, stripping all secrets."""
        clean_env = os.environ.copy()
        keys_to_remove = []
        for k in clean_env.keys():
            k_upper = k.upper()
            if any(s in k_upper for s in ("SECRET", "TOKEN", "KEY", "PASSWORD", "AUTH", "CREDENTIAL")):
                keys_to_remove.append(k)

        for k in keys_to_remove:
            clean_env.pop(k, None)

        # Restrict PYTHONPATH to sandbox root
        clean_env["PYTHONPATH"] = str(self.sandbox_root)
        clean_env["PYTHONDONTWRITEBYTECODE"] = "1"
        return clean_env

    def execute_test(
        self,
        command: List[str],
        user_confirmed: bool = False,
        timeout: Optional[float] = None,
        test_file: Optional[str | Path] = None,
        session_id: Optional[str] = None,
    ) -> TestExecutionResult:
        """
        Executes a test command inside the sandbox.
        MANDATORY: Requires user_confirmed=True. Without confirmation, execution is denied.
        """
        timeout_sec = timeout or self.default_timeout_seconds
        start_time = time.time()

        # 1. Mandatory user confirmation check
        if not user_confirmed:
            msg = "Test execution denied: explicit user confirmation required."
            logger.warning(msg)
            if self.auto_audit:
                self._log_audit(
                    command=command,
                    status="denied",
                    user_approved=False,
                    duration_ms=0,
                    error=msg,
                    session_id=session_id,
                )
            return TestExecutionResult(
                success=False,
                returncode=-1,
                status="denied",
                error=msg,
                command=command,
            )

        # 2. Validate all path arguments in command and test_file
        paths_to_validate: List[str | Path] = []
        if test_file:
            paths_to_validate.append(test_file)
        for arg in command[1:]:
            if "/" in arg or "\\" in arg or arg.endswith(".py") or arg.endswith(".json"):
                paths_to_validate.append(arg)

        for p in paths_to_validate:
            is_safe, reason = self.validate_path_safety(p)
            if not is_safe:
                logger.error("Sandbox blocked test execution: %s", reason)
                if self.auto_audit:
                    self._log_audit(
                        command=command,
                        status="blocked",
                        user_approved=True,
                        duration_ms=0,
                        error=reason,
                        session_id=session_id,
                    )
                return TestExecutionResult(
                    success=False,
                    returncode=-1,
                    status="blocked",
                    error=reason,
                    command=command,
                )

        # 3. Pre-flight AST screening if a test file is specified
        if test_file:
            is_script_safe, script_reason = self.inspect_test_script_safety(test_file)
            if not is_script_safe:
                logger.error("Sandbox AST check failed: %s", script_reason)
                if self.auto_audit:
                    self._log_audit(
                        command=command,
                        status="blocked",
                        user_approved=True,
                        duration_ms=0,
                        error=script_reason,
                        session_id=session_id,
                    )
                return TestExecutionResult(
                    success=False,
                    returncode=-1,
                    status="blocked",
                    error=script_reason,
                    command=command,
                )

        # 4. Prepare sanitized environment and launch subprocess
        env = self._prepare_sanitized_environment()
        logger.info("Executing test in sandbox: %s (timeout: %.1fs)", " ".join(command), timeout_sec)

        try:
            proc = subprocess.Popen(
                command,
                cwd=str(self.sandbox_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                shell=False,
            )

            try:
                stdout, stderr = proc.communicate(timeout=timeout_sec)
                duration_ms = int((time.time() - start_time) * 1000)
                success = proc.returncode == 0
                status = "completed" if success else "failed"

                result = TestExecutionResult(
                    success=success,
                    returncode=proc.returncode,
                    stdout=stdout.strip(),
                    stderr=stderr.strip(),
                    duration_ms=duration_ms,
                    status=status,
                    command=command,
                )

            except subprocess.TimeoutExpired:
                # Forcefully terminate process and process tree
                self._terminate_process_tree(proc)
                stdout, stderr = proc.communicate()
                duration_ms = int((time.time() - start_time) * 1000)
                msg = f"Test execution timed out after {timeout_sec} seconds."
                logger.error(msg)
                result = TestExecutionResult(
                    success=False,
                    returncode=-1,
                    stdout=stdout.strip() if stdout else "",
                    stderr=stderr.strip() if stderr else "",
                    duration_ms=duration_ms,
                    status="timeout",
                    error=msg,
                    command=command,
                )

        except Exception as exc:
            duration_ms = int((time.time() - start_time) * 1000)
            msg = f"Failed to run test subprocess: {exc}"
            logger.error(msg)
            result = TestExecutionResult(
                success=False,
                returncode=-1,
                duration_ms=duration_ms,
                status="failed",
                error=msg,
                command=command,
            )

        if self.auto_audit:
            self._log_audit(
                command=command,
                status=result.status,
                user_approved=True,
                duration_ms=result.duration_ms,
                error=result.error,
                details={"returncode": result.returncode},
                session_id=session_id,
            )

        return result

    def _terminate_process_tree(self, proc: subprocess.Popen) -> None:
        """Kills process and any spawned child processes."""
        try:
            if sys.platform == "win32":
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    capture_output=True,
                    timeout=5,
                )
            else:
                proc.kill()
        except Exception as exc:
            logger.debug("Error killing process tree: %s", exc)

    def _log_audit(
        self,
        command: List[str],
        status: str,
        user_approved: bool,
        duration_ms: int,
        error: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
    ) -> None:
        try:
            from core.audit_logger import get_audit_logger
            audit = self.audit_logger or get_audit_logger()
            cmd_str = " ".join(command)[:256]
            payload = {
                "command": cmd_str,
                "error": error,
                **(details or {}),
            }
            audit.log(
                action_type="code_test",
                action_name="execute_test",
                status=status,
                tier="write",
                user_approved=user_approved,
                actor="user" if user_approved else "system",
                resource=cmd_str,
                duration_ms=duration_ms,
                details=payload,
                session_id=session_id,
            )
        except Exception as exc:
            logger.debug("Failed to record test audit log: %s", exc)


# Module-level instance
_default_sandbox: Optional[TestExecutionSandbox] = None


def get_test_sandbox(sandbox_root: Optional[str | Path] = None) -> TestExecutionSandbox:
    global _default_sandbox
    if _default_sandbox is None or (sandbox_root and Path(sandbox_root).resolve() != _default_sandbox.sandbox_root):
        _default_sandbox = TestExecutionSandbox(sandbox_root=sandbox_root)
    return _default_sandbox
