"""Avatar Asset Discovery & Validation Service.

Searches only approved local directories:
- <project-root>/assets/avatars/beckie/source/
- <project-root>/corrupted-archangel-six-wings-boss/
- <project-root>/jarvis-main-folder/
- user-approved native file picker paths

Strictly enforces security rules:
- Rejects path traversal (../, ..\\)
- Rejects remote URLs (http://, https://, ftp://)
- Validates supported formats (.glb, .gltf, .fbx, .obj, .blend)
- Never alters or overwrites source files
"""

import os
import glob
import logging
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger("Avatar.Discovery")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

APPROVED_DIRECTORIES = [
    os.path.join(BASE_DIR, "assets", "avatars", "beckie", "source"),
    os.path.join(BASE_DIR, "assets", "avatars", "beckie", "generated"),
    os.path.join(BASE_DIR, "corrupted-archangel-six-wings-boss"),
    os.path.join(BASE_DIR, "jarvis-main-folder"),
]

SUPPORTED_EXTENSIONS = [".glb", ".gltf", ".fbx", ".obj", ".blend"]


class AvatarDiscoveryService:
    """Safe asset scanner restricted strictly to local project asset folders."""

    def __init__(self, base_dir: str = BASE_DIR):
        self.base_dir = base_dir
        for d in APPROVED_DIRECTORIES:
            os.makedirs(d, exist_ok=True)

    def validate_path_safety(self, file_path: str) -> Tuple[bool, Optional[str]]:
        """Verify that a path is local, does not traverse, and has a valid extension."""
        if not file_path or not isinstance(file_path, str):
            return False, "File path cannot be empty"

        # Reject remote URLs
        if file_path.lower().startswith(("http://", "https://", "ftp://", "file://")):
            return False, "Remote URLs are strictly prohibited. Local assets only."

        # Normalize and resolve path
        norm_path = os.path.normpath(file_path)
        if ".." in norm_path.split(os.sep):
            return False, "Path traversal sequence (..) detected and rejected."

        # Check extension
        ext = os.path.splitext(norm_path)[1].lower()
        if ext not in SUPPORTED_EXTENSIONS:
            return False, f"Unsupported 3D format '{ext}'. Supported: {', '.join(SUPPORTED_EXTENSIONS)}"

        return True, None

    def discover_local_assets(self) -> List[Dict[str, Any]]:
        """Scan approved folders for 3D model candidates."""
        candidates = []
        seen_paths = set()

        for folder in APPROVED_DIRECTORIES:
            if not os.path.exists(folder):
                continue

            for root, _, files in os.walk(folder):
                for f in files:
                    ext = os.path.splitext(f)[1].lower()
                    if ext in SUPPORTED_EXTENSIONS:
                        full_path = os.path.normpath(os.path.join(root, f))
                        if full_path in seen_paths:
                            continue
                        seen_paths.add(full_path)

                        rel_path = os.path.relpath(full_path, self.base_dir).replace("\\", "/")
                        size_bytes = os.path.getsize(full_path)
                        size_mb = round(size_bytes / (1024 * 1024), 2)

                        candidates.append({
                            "fileName": f,
                            "relativePath": rel_path,
                            "format": ext.replace(".", ""),
                            "sizeBytes": size_bytes,
                            "sizeMb": size_mb,
                            "isRuntimeReady": ext in [".glb", ".gltf"],
                            "isLarge": size_mb > 250.0,
                            "location": os.path.basename(os.path.dirname(full_path)),
                        })

        # Sort with runtime ready (.glb/.gltf) first, then by size
        candidates.sort(key=lambda x: (not x["isRuntimeReady"], x["fileName"]))
        return candidates


_singleton_discovery: Optional[AvatarDiscoveryService] = None


def get_avatar_discovery() -> AvatarDiscoveryService:
    global _singleton_discovery
    if _singleton_discovery is None:
        _singleton_discovery = AvatarDiscoveryService()
    return _singleton_discovery
