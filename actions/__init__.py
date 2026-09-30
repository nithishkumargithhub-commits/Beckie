"""
JARVIS – Actions Package.

Exposes core system control actions and safe Windows integrations.
"""

from actions.brightness import (
    BrightnessController,
    brightness_controller,
    get_brightness,
    list_monitors,
    set_brightness,
)
from actions.deletion_guard import (
    DeletionImpact,
    DeletionImpactAnalyzer,
    analyze_deletion_impact,
    deletion_guard,
)
from actions.file_ops import (
    APPROVED_APPS,
    SafeFileOperations,
    file_ops,
    format_size,
    launch_app,
    search_folders,
    show_metadata,
)
from actions.media_hotkeys import (
    MediaHotkeyManager,
    media_hotkeys,
)
from actions.recycle_bin import (
    RecycleBinManager,
    move_to_recycle_bin,
    recycle_bin,
)
from actions.startup_manager import (
    StartupManager,
    disable_startup,
    enable_startup,
    is_startup_enabled,
    startup_manager,
)
from actions.volume import (
    VolumeController,
    get_volume,
    is_muted,
    mute,
    set_volume,
    toggle_mute,
    unmute,
    volume_controller,
)
from actions.windows_dialog import (
    set_dialog_handler,
    show_confirmation_dialog,
)
from actions.folder_watcher import (
    AntigravityFolderWatcher,
    FileChangeEvent,
    get_folder_watcher,
)
from actions.code_review import (
    CodeReviewResult,
    CodeReviewer,
    ReviewIssue,
    get_code_reviewer,
)
from actions.test_sandbox import (
    TestExecutionResult,
    TestExecutionSandbox,
    get_test_sandbox,
)
from actions.activity_tracker import (
    APPROVED_CATEGORIES,
    ActivityCategory,
    ActivityRecord,
    ActivityTracker,
    get_activity_tracker,
    validate_category,
)
from actions.summary_reporter import (
    ActivitySummary,
    SummaryReporter,
    get_summary_reporter,
)

__all__ = [
    # Brightness
    "BrightnessController",
    "brightness_controller",
    "get_brightness",
    "set_brightness",
    "list_monitors",
    # Volume
    "VolumeController",
    "volume_controller",
    "get_volume",
    "set_volume",
    "mute",
    "unmute",
    "toggle_mute",
    "is_muted",
    # Media
    "MediaHotkeyManager",
    "media_hotkeys",
    # File Operations
    "SafeFileOperations",
    "file_ops",
    "launch_app",
    "search_folders",
    "show_metadata",
    "format_size",
    "APPROVED_APPS",
    # Deletion Impact
    "DeletionImpact",
    "DeletionImpactAnalyzer",
    "deletion_guard",
    "analyze_deletion_impact",
    # Recycle Bin
    "RecycleBinManager",
    "recycle_bin",
    "move_to_recycle_bin",
    # Startup
    "StartupManager",
    "startup_manager",
    "is_startup_enabled",
    "enable_startup",
    "disable_startup",
    # Windows Dialog
    "show_confirmation_dialog",
    "set_dialog_handler",
    # Folder Watcher
    "AntigravityFolderWatcher",
    "FileChangeEvent",
    "get_folder_watcher",
    # Code Review
    "CodeReviewer",
    "CodeReviewResult",
    "ReviewIssue",
    "get_code_reviewer",
    # Test Sandbox
    "TestExecutionSandbox",
    "TestExecutionResult",
    "get_test_sandbox",
    # Activity Tracker
    "ActivityCategory",
    "APPROVED_CATEGORIES",
    "validate_category",
    "ActivityRecord",
    "ActivityTracker",
    "get_activity_tracker",
    # Summary Reporter
    "SummaryReporter",
    "ActivitySummary",
    "get_summary_reporter",
]
