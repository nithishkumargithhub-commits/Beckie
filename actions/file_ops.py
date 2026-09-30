"""
JARVIS – Safe Windows File Operations and App Launcher.

Capabilities:
1. Open approved apps:
   - Strictly enforced whitelist of allowed applications.
   - Tier 2 (WRITE) – requires explicit user confirmation dialog before launch.
   - Secure execution via subprocess.Popen without shell injection risk.
2. Search folders:
   - Fast, recursive user folder searching with pattern matching.
   - Tier 0 (SAFE / READ) – no approval required.
3. Show metadata:
   - Comprehensive file & directory attributes, sizes, timestamps, and hashes.
   - Tier 0 (SAFE / READ) – no approval required.
4. Comprehensive audit logging for all operations with timestamps.
"""

from __future__ import annotations

import datetime
import hashlib
import logging
import os
from pathlib import Path
import re
import subprocess
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from actions.windows_dialog import show_confirmation_dialog
from core.audit_logger import AuditLogger
from core.permission_broker import PermissionBroker, PermissionTier

logger = logging.getLogger("Jarvis.Actions.FileOps")

# Strict registry of approved applications
APPROVED_APPS: Dict[str, Dict[str, str]] = {
    "notepad": {"cmd": "notepad.exe", "desc": "Windows Notepad text editor"},
    "calculator": {"cmd": "calc.exe", "desc": "Windows Calculator"},
    "calc": {"cmd": "calc.exe", "desc": "Windows Calculator"},
    "explorer": {"cmd": "explorer.exe", "desc": "Windows File Explorer"},
    "file explorer": {"cmd": "explorer.exe", "desc": "Windows File Explorer"},
    "cmd": {"cmd": "cmd.exe", "desc": "Windows Command Prompt"},
    "command prompt": {"cmd": "cmd.exe", "desc": "Windows Command Prompt"},
    "terminal": {"cmd": "wt.exe", "desc": "Windows Terminal"},
    "paint": {"cmd": "mspaint.exe", "desc": "Windows Paint"},
    "code": {"cmd": "code.cmd", "desc": "Visual Studio Code"},
    "vscode": {"cmd": "code.cmd", "desc": "Visual Studio Code"},
    "spotify": {"cmd": "spotify.exe", "desc": "Spotify Music Player"},
    "chrome": {"cmd": "chrome.exe", "desc": "Google Chrome Web Browser"},
    "edge": {"cmd": "msedge.exe", "desc": "Microsoft Edge Web Browser"},
}

DEFAULT_SEARCH_ROOTS = [
    Path.home() / "Desktop",
    Path.home() / "Documents",
    Path.home() / "Downloads",
    Path.home() / "Pictures",
    Path.home() / "Music",
    Path.home() / "Videos",
]


def format_size(size_bytes: int) -> str:
    """Format bytes into human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


class SafeFileOperations:
    """Consolidated file operations and approved application launcher."""

    def __init__(
        self,
        broker: Optional[PermissionBroker] = None,
        audit_logger: Optional[AuditLogger] = None,
        dialog_fn: Optional[Callable[[str, str, bool], bool]] = None,
    ):
        self.broker = broker
        self.audit_logger = audit_logger
        self.dialog_fn = dialog_fn or (lambda title, msg, is_destr: show_confirmation_dialog(title, msg, is_destr))

    # ----------------------------------------------------------------------
    # 1. Approved Application Launcher
    # ----------------------------------------------------------------------

    def list_approved_apps(self) -> List[Dict[str, str]]:
        """
        List all approved applications in the whitelist.
        Tier 0 (SAFE) – no approval required.
        """
        return [{"name": name, "command": data["cmd"], "description": data["desc"]}
                for name, data in sorted(APPROVED_APPS.items())]

    def launch_approved_app(self, app_name: str, force_unconfirmed: bool = False) -> Tuple[bool, str]:
        """
        Launch an application from the approved whitelist.
        Tier 2 (WRITE) – requires explicit confirmation dialog before launching.

        Rejects unapproved applications with a clear error message.
        """
        start_time = time.time()
        clean_name = app_name.strip().lower()

        if clean_name not in APPROVED_APPS:
            err = (
                f"Application '{app_name}' is not in the approved whitelist. "
                f"Available approved apps: {', '.join(sorted(set(APPROVED_APPS.keys())))}"
            )
            logger.warning("Blocked launch of unapproved application: %r", app_name)
            if self.audit_logger is not None:
                self.audit_logger.log_action(
                    action_type="windows_control",
                    action_name="launch_app",
                    tier=PermissionTier.WRITE.value,
                    status="blocked_unapproved",
                    user_approved=False,
                    actor="user",
                    resource=f"app:{clean_name}",
                    details={"error": err},
                    duration_ms=int((time.time() - start_time) * 1000),
                )
            return False, err

        app_info = APPROVED_APPS[clean_name]
        binary = app_info["cmd"]
        desc = app_info["desc"]

        # Tier 2 confirmation check
        user_approved = True
        if not force_unconfirmed:
            if self.broker is not None:
                perm = self.broker.request(
                    action_name="launch_app",
                    resource=f"app:{clean_name}",
                    details={"command": binary, "description": desc},
                    actor="user",
                )
                if not perm.granted:
                    msg = f"Launch of '{desc}' was cancelled by user."
                    return False, msg
                user_approved = perm.user_approved
            else:
                title = "JARVIS – Confirm Application Launch"
                prompt_msg = (
                    f"Action: Launch Desktop Application\n"
                    f"Application: {clean_name.capitalize()} ({desc})\n"
                    f"Executable: {binary}\n\n"
                    f"Do you want to open this application?"
                )
                user_approved = self.dialog_fn(title, prompt_msg, False)
                if not user_approved:
                    msg = f"Launch of '{clean_name}' was cancelled by user."
                    if self.audit_logger is not None:
                        self.audit_logger.log_action(
                            action_type="windows_control",
                            action_name="launch_app",
                            tier=PermissionTier.WRITE.value,
                            status="cancelled",
                            user_approved=False,
                            actor="user",
                            resource=f"app:{clean_name}",
                            details={"result": msg},
                            duration_ms=int((time.time() - start_time) * 1000),
                        )
                    return False, msg

        # Launch safely without shell=True
        try:
            # On Windows, system utilities can be launched directly
            subprocess.Popen([binary], shell=False)
            msg = f"Launched {desc} successfully."
            logger.info(msg)

            if self.audit_logger is not None:
                self.audit_logger.log_action(
                    action_type="windows_control",
                    action_name="launch_app",
                    tier=PermissionTier.WRITE.value,
                    status="success",
                    user_approved=user_approved,
                    actor="user",
                    resource=f"app:{clean_name}",
                    details={"command": binary, "result": msg},
                    duration_ms=int((time.time() - start_time) * 1000),
                )
            return True, msg
        except Exception as exc:
            err = f"Failed to launch '{clean_name}': {exc}"
            logger.error(err)
            if self.audit_logger is not None:
                self.audit_logger.log_action(
                    action_type="windows_control",
                    action_name="launch_app",
                    tier=PermissionTier.WRITE.value,
                    status="failed",
                    user_approved=user_approved,
                    actor="user",
                    resource=f"app:{clean_name}",
                    details={"command": binary, "error": str(exc)},
                    duration_ms=int((time.time() - start_time) * 1000),
                )
            return False, err

    # ----------------------------------------------------------------------
    # 2. Folder Searcher
    # ----------------------------------------------------------------------

    def search_folders(
        self,
        query: str,
        roots: Optional[List[Path]] = None,
        max_results: int = 50,
        file_types: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for files matching query or extensions across specified folders.
        Tier 0 (SAFE / READ) – no approval required.
        """
        start_time = time.time()
        search_dirs = [Path(r) for r in roots] if roots else [p for p in DEFAULT_SEARCH_ROOTS if p.exists()]
        results: List[Dict[str, Any]] = []

        query_clean = query.strip().lower()
        # Clean common prefixes
        for prefix in ["search for file ", "find file ", "locate ", "search ", "find "]:
            if query_clean.startswith(prefix):
                query_clean = query_clean[len(prefix):].strip()
                break

        regex = re.compile(re.escape(query_clean).replace(r"\*", ".*"), re.IGNORECASE) if query_clean else None
        target_extensions = [e.lower() if e.startswith(".") else f".{e.lower()}" for e in file_types] if file_types else None

        for root in search_dirs:
            if not root.exists():
                continue
            try:
                for dirpath, dirnames, filenames in os.walk(root):
                    # Skip hidden directories
                    dirnames[:] = [d for d in dirnames if not d.startswith(".")]

                    for fn in filenames:
                        # Extension filter
                        if target_extensions and Path(fn).suffix.lower() not in target_extensions:
                            continue

                        # Name match
                        if regex and not regex.search(fn):
                            continue

                        full_path = Path(dirpath) / fn
                        try:
                            st = full_path.stat()
                            results.append({
                                "name": fn,
                                "path": str(full_path),
                                "size_bytes": st.st_size,
                                "size_formatted": format_size(st.st_size),
                                "modified_at": datetime.datetime.fromtimestamp(st.st_mtime).isoformat(),
                                "is_dir": False,
                            })
                        except Exception:
                            continue

                        if len(results) >= max_results:
                            break
                    if len(results) >= max_results:
                        break
            except Exception as exc:
                logger.warning("Error searching folder %s: %s", root, exc)

        if self.audit_logger is not None:
            self.audit_logger.log_action(
                action_type="windows_control",
                action_name="search_files",
                tier=PermissionTier.READ.value,
                status="success",
                user_approved=True,
                actor="user",
                resource=f"query:{query}",
                details={"match_count": len(results), "roots": [str(r) for r in search_dirs]},
                duration_ms=int((time.time() - start_time) * 1000),
            )

        return results

    # ----------------------------------------------------------------------
    # 3. File & Directory Metadata Viewer
    # ----------------------------------------------------------------------

    def show_metadata(self, target_path: Union[str, Path], compute_hash: bool = False) -> Dict[str, Any]:
        """
        Extract detailed metadata for a file or directory.
        Tier 0 (SAFE / READ) – no approval required.
        """
        start_time = time.time()
        p = Path(target_path).resolve()

        if not p.exists():
            raise FileNotFoundError(f"Path does not exist: {p}")

        st = p.stat()
        is_dir = p.is_dir()

        metadata: Dict[str, Any] = {
            "name": p.name,
            "path": str(p),
            "parent_dir": str(p.parent),
            "is_directory": is_dir,
            "is_file": p.is_file(),
            "is_symlink": p.is_symlink(),
            "extension": p.suffix if not is_dir else None,
            "size_bytes": st.st_size if not is_dir else 0,
            "size_formatted": format_size(st.st_size) if not is_dir else "N/A (Directory)",
            "created_at": datetime.datetime.fromtimestamp(st.st_ctime).isoformat(),
            "modified_at": datetime.datetime.fromtimestamp(st.st_mtime).isoformat(),
            "accessed_at": datetime.datetime.fromtimestamp(st.st_atime).isoformat(),
            "attributes": self._get_windows_attributes(p),
        }

        # Calculate SHA256 if requested and file is < 100MB
        if compute_hash and p.is_file() and st.st_size <= 100 * 1024 * 1024:
            try:
                hasher = hashlib.sha256()
                with open(p, "rb") as f:
                    for chunk in iter(lambda: f.read(65536), b""):
                        hasher.update(chunk)
                metadata["sha256"] = hasher.hexdigest()
            except Exception as h_err:
                metadata["sha256_error"] = str(h_err)

        if self.audit_logger is not None:
            self.audit_logger.log_action(
                action_type="windows_control",
                action_name="show_metadata",
                tier=PermissionTier.READ.value,
                status="success",
                user_approved=True,
                actor="user",
                resource=f"path:{p}",
                details={"is_directory": is_dir, "size_bytes": st.st_size},
                duration_ms=int((time.time() - start_time) * 1000),
            )

        return metadata

    @staticmethod
    def _get_windows_attributes(path: Path) -> List[str]:
        """Inspect Windows file attributes."""
        attrs = []
        try:
            import stat

            mode = path.stat().st_file_attributes
            if mode & stat.FILE_ATTRIBUTE_READONLY:
                attrs.append("ReadOnly")
            if mode & stat.FILE_ATTRIBUTE_HIDDEN:
                attrs.append("Hidden")
            if mode & stat.FILE_ATTRIBUTE_SYSTEM:
                attrs.append("System")
            if mode & stat.FILE_ATTRIBUTE_ARCHIVE:
                attrs.append("Archive")
            if mode & stat.FILE_ATTRIBUTE_COMPRESSED:
                attrs.append("Compressed")
            if mode & stat.FILE_ATTRIBUTE_ENCRYPTED:
                attrs.append("Encrypted")
        except Exception:
            pass
        return attrs


# Default singleton instance and convenience wrappers
file_ops = SafeFileOperations()


def launch_app(app_name: str) -> str:
    _, msg = file_ops.launch_approved_app(app_name)
    return msg


def search_folders(query: str, max_results: int = 50) -> List[Dict[str, Any]]:
    return file_ops.search_folders(query, max_results=max_results)


def show_metadata(file_path: Union[str, Path]) -> Dict[str, Any]:
    return file_ops.show_metadata(file_path)
