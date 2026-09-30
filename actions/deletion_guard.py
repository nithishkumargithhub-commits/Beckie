"""
JARVIS – Deletion Impact Analyzer and Pre-flight Safety Guard.

Analyzes the full blast radius of any file or directory targeted for deletion:
- File & directory counts.
- Total cumulative storage size.
- Recency of modifications (detects recently active workspaces).
- Project affiliation (Git repository, Python, Node.js, Rust/Cargo, etc.).
- Protected system paths detection (Windows directory, Program Files, system roots).
- Risk level assessment (LOW, MEDIUM, HIGH, CRITICAL).
- Tier 0 (SAFE / READ) – no approval required for analysis.
- Detailed audit logging with timestamps.
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime
import logging
import os
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Set, Union

from actions.file_ops import format_size
from core.audit_logger import AuditLogger
from core.permission_broker import PermissionBroker, PermissionTier

logger = logging.getLogger("Jarvis.Actions.DeletionGuard")

# Project markers identifying repository root or codebases
PROJECT_MARKERS: Dict[str, str] = {
    ".git": "Git repository",
    "pyproject.toml": "Python project (pyproject.toml)",
    "package.json": "Node.js / Web project (package.json)",
    "Cargo.toml": "Rust project (Cargo.toml)",
    "go.mod": "Go module project (go.mod)",
    "pom.xml": "Java Maven project (pom.xml)",
    "build.gradle": "Gradle project (build.gradle)",
    "requirements.txt": "Python project (requirements.txt)",
    ".vscode": "VS Code workspace",
    ".idea": "JetBrains IDE workspace",
    "CMakeLists.txt": "C/C++ CMake project",
}

# Critical system directories that must NEVER be deleted
PROTECTED_SYSTEM_NAMES: Set[str] = {
    "windows",
    "system32",
    "syswow64",
    "program files",
    "program files (x86)",
    "programdata",
    "appdata",
    "$recycle.bin",
    "system volume information",
    "recovery",
    "boot",
}


@dataclass
class DeletionImpact:
    path: str
    exists: bool
    is_directory: bool
    file_count: int
    dir_count: int
    total_size_bytes: int
    total_size_formatted: str
    newest_mtime: Optional[float]
    newest_mtime_formatted: str
    days_since_newest_edit: Optional[float]
    is_recently_active: bool
    project_affiliation: Optional[str]
    is_system_path: bool
    risk_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    summary: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "exists": self.exists,
            "is_directory": self.is_directory,
            "file_count": self.file_count,
            "dir_count": self.dir_count,
            "total_size_bytes": self.total_size_bytes,
            "total_size_formatted": self.total_size_formatted,
            "newest_mtime": self.newest_mtime,
            "newest_mtime_formatted": self.newest_mtime_formatted,
            "days_since_newest_edit": self.days_since_newest_edit,
            "is_recently_active": self.is_recently_active,
            "project_affiliation": self.project_affiliation,
            "is_system_path": self.is_system_path,
            "risk_level": self.risk_level,
            "summary": self.summary,
        }


class DeletionImpactAnalyzer:
    """Pre-flight analyzer checking file counts, size, recency, and project affiliation."""

    def __init__(
        self,
        broker: Optional[PermissionBroker] = None,
        audit_logger: Optional[AuditLogger] = None,
    ):
        self.broker = broker
        self.audit_logger = audit_logger

    def analyze(self, target_path: Union[str, Path]) -> DeletionImpact:
        """
        Perform a thorough deletion impact analysis.
        Tier 0 (SAFE / READ) – no approval required.
        """
        start_time = time.time()
        p = Path(target_path).resolve()

        if not p.exists():
            impact = DeletionImpact(
                path=str(p),
                exists=False,
                is_directory=False,
                file_count=0,
                dir_count=0,
                total_size_bytes=0,
                total_size_formatted="0 B",
                newest_mtime=None,
                newest_mtime_formatted="N/A (Does not exist)",
                days_since_newest_edit=None,
                is_recently_active=False,
                project_affiliation=None,
                is_system_path=False,
                risk_level="LOW",
                summary=f"Path '{p}' does not exist on disk.",
            )
            return impact

        is_system = self._is_critical_system_path(p)
        project_affiliation = self._detect_project_affiliation(p)

        file_count = 0
        dir_count = 0
        total_size = 0
        newest_mtime: Optional[float] = None

        if is_system:
            file_count = 1
            total_size = 0
            newest_mtime = None
        elif p.is_file() or p.is_symlink():
            try:
                st = p.stat()
                file_count = 1
                total_size = st.st_size
                newest_mtime = st.st_mtime
            except Exception as exc:
                logger.warning("Error stating file %s: %s", p, exc)
        elif p.is_dir():
            dir_count = 1
            for root, dirs, files in os.walk(p):
                dir_count += len(dirs)
                for fn in files:
                    file_count += 1
                    fp = Path(root) / fn
                    try:
                        st = fp.stat()
                        total_size += st.st_size
                        if newest_mtime is None or st.st_mtime > newest_mtime:
                            newest_mtime = st.st_mtime
                    except Exception:
                        continue

        now = time.time()
        days_since_edit = None
        newest_mtime_str = "Unknown"
        is_recently_active = False

        if newest_mtime is not None:
            days_since_edit = round((now - newest_mtime) / (24 * 3600), 2)
            newest_mtime_str = datetime.datetime.fromtimestamp(newest_mtime).strftime("%Y-%m-%d %H:%M:%S")
            # Considered recently active if modified within the last 7 days
            is_recently_active = days_since_edit < 7.0

        # Assess risk level
        risk_level = self._compute_risk_level(
            is_system=is_system,
            is_directory=p.is_dir(),
            file_count=file_count,
            total_size=total_size,
            is_recently_active=is_recently_active,
            project_affiliation=project_affiliation,
        )

        # Format descriptive summary
        summary = self._build_summary(
            target_path=str(p),
            is_directory=p.is_dir(),
            file_count=file_count,
            dir_count=dir_count,
            total_size_fmt=format_size(total_size),
            newest_mtime_str=newest_mtime_str,
            days_since_edit=days_since_edit,
            project_affiliation=project_affiliation,
            is_system=is_system,
            risk_level=risk_level,
        )

        impact = DeletionImpact(
            path=str(p),
            exists=True,
            is_directory=p.is_dir(),
            file_count=file_count,
            dir_count=dir_count,
            total_size_bytes=total_size,
            total_size_formatted=format_size(total_size),
            newest_mtime=newest_mtime,
            newest_mtime_formatted=newest_mtime_str,
            days_since_newest_edit=days_since_edit,
            is_recently_active=is_recently_active,
            project_affiliation=project_affiliation,
            is_system_path=is_system,
            risk_level=risk_level,
            summary=summary,
        )

        if self.audit_logger is not None:
            self.audit_logger.log_action(
                action_type="windows_control",
                action_name="analyze_deletion_impact",
                tier=PermissionTier.READ.value,
                status="success",
                user_approved=True,
                actor="system",
                resource=f"path:{p}",
                details={
                    "file_count": file_count,
                    "total_size_bytes": total_size,
                    "risk_level": risk_level,
                    "project": project_affiliation,
                    "is_system_path": is_system,
                },
                duration_ms=int((time.time() - start_time) * 1000),
            )

        return impact

    def _detect_project_affiliation(self, path: Path) -> Optional[str]:
        """Check if path or its ancestors are part of a software project."""
        curr = path if path.is_dir() else path.parent
        home = Path.home().resolve()

        # Inspect current dir and ancestors up to 5 levels
        for _ in range(6):
            if curr.resolve() == home or curr.parent == curr:
                break
            for marker, desc in PROJECT_MARKERS.items():
                if (curr / marker).exists():
                    rel = path.relative_to(curr) if path != curr else "root"
                    return f"{desc} ({curr.name}, item: {rel})"
            curr = curr.parent

        return None

    def _is_critical_system_path(self, path: Path) -> bool:
        """Check if path is a protected Windows root or system folder."""
        # Drive root check (e.g. C:\)
        if len(path.parts) <= 1 or str(path).rstrip("\\/").endswith(":"):
            return True

        # User profile root check (e.g. C:\Users\username)
        home = Path.home().resolve()
        if path.resolve() == home:
            return True

        # System directory names check
        for part in path.parts:
            clean = part.lower().strip()
            if clean in PROTECTED_SYSTEM_NAMES:
                # If path is the system folder itself or directly inside Windows
                if clean in ("windows", "system32", "program files", "program files (x86)"):
                    return True

        return False

    @staticmethod
    def _compute_risk_level(
        is_system: bool,
        is_directory: bool,
        file_count: int,
        total_size: int,
        is_recently_active: bool,
        project_affiliation: Optional[str],
    ) -> str:
        if is_system:
            return "CRITICAL"

        if project_affiliation and (is_recently_active or file_count > 50 or total_size > 100 * 1024 * 1024):
            return "HIGH"

        if file_count > 200 or total_size > 500 * 1024 * 1024:
            return "HIGH"

        if file_count > 10 or total_size > 20 * 1024 * 1024 or is_recently_active:
            return "MEDIUM"

        return "LOW"

    @staticmethod
    def _build_summary(
        target_path: str,
        is_directory: bool,
        file_count: int,
        dir_count: int,
        total_size_fmt: str,
        newest_mtime_str: str,
        days_since_edit: Optional[float],
        project_affiliation: Optional[str],
        is_system: bool,
        risk_level: str,
    ) -> str:
        lines = [
            f"Deletion Impact Analysis for: {target_path}",
            f"  * Target Type: {'Directory' if is_directory else 'Single File'}",
            f"  * Total Files: {file_count:,} file{'s' if file_count != 1 else ''}" + (f" across {dir_count} directories" if is_directory else ""),
            f"  * Total Space: {total_size_fmt}",
            f"  * Most Recent Edit: {newest_mtime_str} (" + (f"{days_since_edit} days ago" if days_since_edit is not None else "N/A") + ")",
        ]

        if project_affiliation:
            lines.append(f"  * Project Affiliation: [PROJECT] {project_affiliation}")
        else:
            lines.append("  * Project Affiliation: None detected (standalone files)")

        if is_system:
            lines.append("  * Protected Path: [ALERT] CRITICAL WINDOWS SYSTEM DIRECTORY")

        lines.append(f"  * Overall Risk: [{risk_level}]")
        return "\n".join(lines)


# Default singleton instance
deletion_guard = DeletionImpactAnalyzer()


def analyze_deletion_impact(target_path: Union[str, Path]) -> DeletionImpact:
    return deletion_guard.analyze(target_path)
