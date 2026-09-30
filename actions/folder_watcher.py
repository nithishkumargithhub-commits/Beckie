"""
JARVIS - Antigravity IDE Project Folder Watcher.

Monitors project directories using the `watchdog` library for code changes,
debounces rapid editor save events, computes diffs, notifies registered listeners,
and logs audit entries.
"""

from __future__ import annotations

import difflib
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger("Jarvis.Actions.FolderWatcher")

# Default extensions monitored for coding activity
DEFAULT_CODE_EXTENSIONS: Set[str] = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".scss",
    ".json", ".md", ".toml", ".yaml", ".yml", ".sql", ".sh", ".bat",
    ".ps1", ".c", ".cpp", ".h", ".hpp", ".rs", ".go", ".java", ".kt",
}

# Directories and file patterns to ignore
DEFAULT_IGNORE_DIRS: Set[str] = {
    ".git", ".venv", "venv", "__pycache__", "node_modules",
    ".pytest_cache", ".coverage", ".gemini", "dist", "build",
    ".idea", ".vscode", "logs", "data",
}

DEFAULT_IGNORE_EXTENSIONS: Set[str] = {
    ".pyc", ".pyo", ".pyd", ".db", ".db-wal", ".db-shm",
    ".enc", ".tmp", ".swp", ".bak",
}


@dataclass
class FileChangeEvent:
    """Represents a debounced file change detected by the folder watcher."""
    event_type: str         # "created" | "modified" | "deleted" | "moved"
    file_path: str          # Absolute path
    rel_path: str           # Relative path to watch root
    timestamp: float        # Unix timestamp
    diff: Optional[str] = None
    is_code: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "file_path": self.file_path,
            "rel_path": self.rel_path,
            "timestamp": self.timestamp,
            "diff": self.diff,
            "is_code": self.is_code,
            "metadata": self.metadata,
        }


class _DebouncedEventHandler(FileSystemEventHandler):
    """
    Internal watchdog FileSystemEventHandler that filters irrelevant files
    and debounces rapid save events.
    """

    def __init__(
        self,
        watch_root: Path,
        debounce_seconds: float,
        on_event_callback: Callable[[FileChangeEvent], None],
        code_extensions: Optional[Set[str]] = None,
        ignore_dirs: Optional[Set[str]] = None,
        ignore_extensions: Optional[Set[str]] = None,
    ) -> None:
        super().__init__()
        self.watch_root = watch_root.resolve()
        self.debounce_seconds = debounce_seconds
        self.on_event_callback = on_event_callback
        self.code_extensions = code_extensions or DEFAULT_CODE_EXTENSIONS
        self.ignore_dirs = ignore_dirs or DEFAULT_IGNORE_DIRS
        self.ignore_extensions = ignore_extensions or DEFAULT_IGNORE_EXTENSIONS

        self._lock = threading.Lock()
        self._pending_timers: Dict[str, threading.Timer] = {}
        self._cached_contents: Dict[str, str] = {}
        self._init_cache()

    def _init_cache(self) -> None:
        """Cache initial file contents for text/code files (up to 512KB each) to enable diffing."""
        try:
            for root, dirs, files in os.walk(self.watch_root):
                dirs[:] = [d for d in dirs if d not in self.ignore_dirs]
                for file_name in files:
                    ext = Path(file_name).suffix.lower()
                    if ext in self.code_extensions:
                        full_p = os.path.join(root, file_name)
                        try:
                            if os.path.getsize(full_p) <= 512 * 1024:
                                with open(full_p, "r", encoding="utf-8", errors="ignore") as f:
                                    self._cached_contents[full_p] = f.read()
                        except Exception:
                            pass
        except Exception as e:
            logger.debug("Failed during initial cache scan: %s", e)

    def _should_ignore(self, path_str: str) -> bool:
        """Check if path should be ignored based on directories or extensions."""
        p = Path(path_str)
        # Check any parent directory part against ignore_dirs
        for part in p.parts:
            if part in self.ignore_dirs:
                return True
        ext = p.suffix.lower()
        if ext in self.ignore_extensions:
            return True
        if p.name.startswith("~") or p.name.startswith(".#"):
            return True
        return False

    def _is_code_file(self, path_str: str) -> bool:
        return Path(path_str).suffix.lower() in self.code_extensions

    def on_created(self, event: FileSystemEvent) -> None:
        if event.is_directory or self._should_ignore(event.src_path):
            return
        self._schedule_event("created", event.src_path)

    def on_modified(self, event: FileSystemEvent) -> None:
        if event.is_directory or self._should_ignore(event.src_path):
            return
        self._schedule_event("modified", event.src_path)

    def on_deleted(self, event: FileSystemEvent) -> None:
        if event.is_directory or self._should_ignore(event.src_path):
            return
        self._schedule_event("deleted", event.src_path)

    def on_moved(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        dest_path = getattr(event, "dest_path", None)
        if dest_path and not self._should_ignore(dest_path):
            self._schedule_event("moved", dest_path, src_path=event.src_path)

    def _schedule_event(self, event_type: str, file_path: str, src_path: Optional[str] = None) -> None:
        """Debounce events for the given file_path."""
        with self._lock:
            if file_path in self._pending_timers:
                self._pending_timers[file_path].cancel()

            timer = threading.Timer(
                self.debounce_seconds,
                self._process_debounced_event,
                args=(event_type, file_path, src_path),
            )
            self._pending_timers[file_path] = timer
            timer.daemon = True
            timer.start()

    def _process_debounced_event(
        self, event_type: str, file_path: str, src_path: Optional[str] = None
    ) -> None:
        with self._lock:
            self._pending_timers.pop(file_path, None)

        abs_path = os.path.abspath(file_path)
        try:
            rel_path = os.path.relpath(abs_path, self.watch_root)
        except ValueError:
            rel_path = abs_path

        diff_str: Optional[str] = None
        new_content: Optional[str] = None
        old_content = self._cached_contents.get(abs_path, "")

        if event_type in ("created", "modified") and os.path.exists(abs_path):
            try:
                if os.path.getsize(abs_path) <= 1024 * 1024:
                    with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                        new_content = f.read()

                    if old_content or new_content:
                        diff_lines = list(
                            difflib.unified_diff(
                                old_content.splitlines(keepends=True),
                                new_content.splitlines(keepends=True),
                                fromfile=f"a/{rel_path}",
                                tofile=f"b/{rel_path}",
                            )
                        )
                        diff_str = "".join(diff_lines) if diff_lines else None
                    self._cached_contents[abs_path] = new_content
            except Exception as e:
                logger.debug("Diff generation skipped for %s: %s", rel_path, e)
        elif event_type == "deleted":
            self._cached_contents.pop(abs_path, None)
            if old_content:
                diff_lines = list(
                    difflib.unified_diff(
                        old_content.splitlines(keepends=True),
                        [],
                        fromfile=f"a/{rel_path}",
                        tofile="/dev/null",
                    )
                )
                diff_str = "".join(diff_lines) if diff_lines else None

        metadata: Dict[str, Any] = {}
        if src_path:
            metadata["src_path"] = src_path

        change_event = FileChangeEvent(
            event_type=event_type,
            file_path=abs_path,
            rel_path=rel_path,
            timestamp=time.time(),
            diff=diff_str,
            is_code=self._is_code_file(abs_path),
            metadata=metadata,
        )

        try:
            self.on_event_callback(change_event)
        except Exception as e:
            logger.error("Error invoking folder watcher callback: %s", e)


class AntigravityFolderWatcher:
    """
    Project folder watcher for Antigravity IDE and repository files.
    """

    def __init__(
        self,
        watch_path: Optional[str | Path] = None,
        debounce_seconds: float = 0.5,
        code_extensions: Optional[Set[str]] = None,
        ignore_dirs: Optional[Set[str]] = None,
        auto_audit: bool = True,
    ) -> None:
        from config import BASE_DIR
        self.watch_path = Path(watch_path or BASE_DIR).resolve()
        self.debounce_seconds = debounce_seconds
        self.code_extensions = code_extensions or DEFAULT_CODE_EXTENSIONS
        self.ignore_dirs = ignore_dirs or DEFAULT_IGNORE_DIRS
        self.auto_audit = auto_audit

        self._observer: Optional[Observer] = None
        self._listeners: List[Callable[[FileChangeEvent], None]] = []
        self._history: List[FileChangeEvent] = []
        self._lock = threading.Lock()
        self._is_running = False

    def add_listener(self, listener: Callable[[FileChangeEvent], None]) -> None:
        """Register a callback for file change events."""
        with self._lock:
            if listener not in self._listeners:
                self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[FileChangeEvent], None]) -> None:
        """Unregister a callback."""
        with self._lock:
            if listener in self._listeners:
                self._listeners.remove(listener)

    def get_recent_events(self, limit: int = 50) -> List[FileChangeEvent]:
        """Return the most recent recorded file change events."""
        with self._lock:
            return list(self._history[-limit:])

    def _handle_event(self, event: FileChangeEvent) -> None:
        with self._lock:
            self._history.append(event)
            if len(self._history) > 1000:
                self._history = self._history[-1000:]
            current_listeners = list(self._listeners)

        if self.auto_audit:
            try:
                from core.audit_logger import get_audit_logger
                logger_instance = get_audit_logger()
                logger_instance.log(
                    action_type="file_op",
                    action_name=f"file_{event.event_type}",
                    status="completed",
                    tier="read",
                    actor="system",
                    resource=event.rel_path,
                    details={
                        "event_type": event.event_type,
                        "is_code": event.is_code,
                        "has_diff": bool(event.diff),
                    },
                )
            except Exception as e:
                logger.debug("Failed to record audit log for file change: %s", e)

        for listener in current_listeners:
            try:
                listener(event)
            except Exception as e:
                logger.error("Error in watcher listener: %s", e)

    def start(self) -> None:
        """Start the directory watcher observer."""
        if self._is_running:
            logger.warning("FolderWatcher is already running.")
            return

        if not self.watch_path.exists():
            raise FileNotFoundError(f"Watch directory does not exist: {self.watch_path}")

        handler = _DebouncedEventHandler(
            watch_root=self.watch_path,
            debounce_seconds=self.debounce_seconds,
            on_event_callback=self._handle_event,
            code_extensions=self.code_extensions,
            ignore_dirs=self.ignore_dirs,
        )

        self._observer = Observer()
        self._observer.schedule(handler, str(self.watch_path), recursive=True)
        self._observer.daemon = True
        self._observer.start()
        self._is_running = True
        logger.info("AntigravityFolderWatcher started on %s", self.watch_path)

    def stop(self) -> None:
        """Stop the directory watcher."""
        if not self._is_running or not self._observer:
            return
        self._observer.stop()
        self._observer.join(timeout=3.0)
        self._observer = None
        self._is_running = False
        logger.info("AntigravityFolderWatcher stopped.")

    def is_running(self) -> bool:
        return self._is_running

    def __enter__(self) -> AntigravityFolderWatcher:
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.stop()


# Module-level singleton
_default_watcher: Optional[AntigravityFolderWatcher] = None


def get_folder_watcher(watch_path: Optional[str | Path] = None) -> AntigravityFolderWatcher:
    global _default_watcher
    if _default_watcher is None or (watch_path and Path(watch_path).resolve() != _default_watcher.watch_path):
        _default_watcher = AntigravityFolderWatcher(watch_path=watch_path)
    return _default_watcher
