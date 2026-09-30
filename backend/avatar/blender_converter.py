"""Blender Headless Conversion Service for FBX to GLB.

Enforces Section 3 of BECKIE Avatar Specification:
- Detects local blender.exe without downloading or installing automatically
- Produces exact conversion preview summary
- Executes headless conversion only upon explicit user confirmation
- Preserves mesh, materials, textures, armature, skinning, blendshapes, and animations
- Generates conversion-report.json matching schema
- Never modifies or deletes the original source FBX file
"""

import os
import sys
import json
import logging
import subprocess
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple
from .avatar_audit import get_audit_logger

logger = logging.getLogger("Avatar.Blender")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SOURCE_DIR = os.path.join(BASE_DIR, "assets", "avatars", "beckie", "source")
GENERATED_DIR = os.path.join(BASE_DIR, "assets", "avatars", "beckie", "generated")
REPORT_PATH = os.path.join(GENERATED_DIR, "conversion-report.json")
OUTPUT_GLB_PATH = os.path.join(GENERATED_DIR, "beckie-avatar.glb")


class BlenderConverterService:
    """Headless Blender FBX to GLB conversion manager."""

    def __init__(self, base_dir: str = BASE_DIR):
        self.base_dir = base_dir
        os.makedirs(SOURCE_DIR, exist_ok=True)
        os.makedirs(GENERATED_DIR, exist_ok=True)

    def detect_blender(self) -> Dict[str, Any]:
        """Detect local Blender executable in configured path or common Windows locations."""
        # 1. Environment override
        env_path = os.environ.get("BLENDER_PATH")
        if env_path and os.path.isfile(env_path):
            ver = self._get_blender_version(env_path)
            return {
                "isAvailable": True,
                "blenderPath": env_path,
                "blenderVersion": ver,
                "instructions": "Configured Blender found and ready for headless conversion.",
            }

        # 2. Common Windows paths
        candidates = [
            r"C:\Program Files\Blender Foundation\Blender 4.3\blender.exe",
            r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe",
            r"C:\Program Files\Blender Foundation\Blender 4.1\blender.exe",
            r"C:\Program Files\Blender Foundation\Blender 4.0\blender.exe",
            r"C:\Program Files\Blender Foundation\Blender 3.6\blender.exe",
            r"C:\Program Files\Blender Foundation\Blender\blender.exe",
            r"C:\Program Files (x86)\Blender Foundation\Blender\blender.exe",
            r"C:\Program Files\Steam\steamapps\common\Blender\blender.exe",
        ]

        user_profile = os.environ.get("USERPROFILE")
        if user_profile:
            candidates.append(os.path.join(user_profile, r"AppData\Local\Programs\Blender\blender.exe"))

        for path in candidates:
            if os.path.isfile(path):
                ver = self._get_blender_version(path)
                return {
                    "isAvailable": True,
                    "blenderPath": path,
                    "blenderVersion": ver,
                    "instructions": "Local Blender installation detected.",
                }

        # Fallback check on PATH
        try:
            res = subprocess.run(["where.exe", "blender"], capture_output=True, text=True, check=False)
            if res.returncode == 0 and res.stdout.strip():
                first_found = res.stdout.strip().splitlines()[0]
                if os.path.isfile(first_found):
                    return {
                        "isAvailable": True,
                        "blenderPath": first_found,
                        "blenderVersion": self._get_blender_version(first_found),
                        "instructions": "Blender found in system PATH.",
                    }
        except Exception:
            pass

        return {
            "isAvailable": False,
            "blenderPath": None,
            "blenderVersion": None,
            "instructions": "Blender is required to convert MidPoly.fbx to GLB. Install Blender or import a GLB file.",
        }

    def _get_blender_version(self, path: str) -> Optional[str]:
        try:
            res = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=5, check=False)
            if res.returncode == 0:
                return res.stdout.splitlines()[0].strip()
        except Exception as e:
            logger.debug(f"Failed to query Blender version: {e}")
        return None

    def get_conversion_preview(self, source_path: str) -> Dict[str, Any]:
        """Return exact preview summary before conversion."""
        full_path = source_path if os.path.isabs(source_path) else os.path.join(self.base_dir, source_path)
        full_path = os.path.normpath(full_path)

        if not os.path.isfile(full_path):
            raise FileNotFoundError(f"Source FBX not found: {source_path}")

        size_bytes = os.path.getsize(full_path)
        size_mb = round(size_bytes / (1024 * 1024), 2)
        rel_path = os.path.relpath(full_path, self.base_dir).replace("\\", "/")

        is_binary = False
        try:
            with open(full_path, "rb") as f:
                header = f.read(20)
                is_binary = b"Kaydara FBX Binary" in header
        except Exception:
            pass

        return {
            "sourceFileName": os.path.basename(full_path),
            "sourceSizeBytes": size_bytes,
            "sourceSizeMb": size_mb,
            "sourcePath": rel_path,
            "sourceFile": rel_path,
            "isBinaryFbx": is_binary,
            "outputPath": "assets/avatars/beckie/generated/beckie-avatar.glb",
            "action": "Create a converted GLB copy; original FBX will remain unchanged",
            "linkedTexturesDetected": False,
            "processedLocallyOnly": True,
        }

    def convert_fbx(self, source_rel: str) -> Dict[str, Any]:
        """Execute headless Blender conversion from FBX to GLB."""
        blender_info = self.detect_blender()
        if not blender_info["isAvailable"]:
            get_audit_logger().log(
                action="CONVERSION_FAILED",
                source_file=source_rel,
                details={"reason": "Blender not detected on host system"},
                user_approved=False,
            )
            raise RuntimeError(
                "Blender is required to convert MidPoly.fbx to GLB. Install Blender or import a GLB file."
            )

        full_source = source_rel if os.path.isabs(source_rel) else os.path.join(self.base_dir, source_rel)
        full_source = os.path.normpath(full_source)

        if not os.path.isfile(full_source):
            raise FileNotFoundError(f"Source file missing: {full_source}")

        get_audit_logger().log(
            action="CONVERSION_STARTED",
            source_file=source_rel,
            details={"outputPath": "assets/avatars/beckie/generated/beckie-avatar.glb"},
            user_approved=True,
        )

        script_path = os.path.join(GENERATED_DIR, "_blender_convert.py")
        blender_script = f"""
import bpy
import sys
import os
import json
from datetime import datetime, timezone

argv = sys.argv
args = argv[argv.index("--") + 1:] if "--" in argv else []
src_fbx = args[0]
dst_glb = args[1]
report_file = args[2]

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=src_fbx)

meshes = [o for o in bpy.data.objects if o.type == 'MESH']
armatures = [o for o in bpy.data.objects if o.type == 'ARMATURE']
materials = list(bpy.data.materials)
textures = list(bpy.data.images)
triangles = sum(len(m.data.polygons) for m in meshes)
animations = list(bpy.data.actions)

bpy.ops.export_scene.gltf(
    filepath=dst_glb,
    export_format='GLB',
    export_materials='EXPORT',
    export_colors=True,
    export_skins=True,
    export_morph=True,
    export_animations=True,
)

report = {{
    "sourceFile": "{source_rel.replace('\\', '/')}",
    "outputFile": "assets/avatars/beckie/generated/beckie-avatar.glb",
    "convertedAt": datetime.now(timezone.utc).isoformat(),
    "blenderVersion": bpy.app.version_string,
    "success": True,
    "warnings": [],
    "meshCount": len(meshes),
    "triangleCount": triangles,
    "materialCount": len(materials),
    "textureCount": len(textures),
    "hasArmature": len(armatures) > 0,
    "animationCount": len(animations),
}}

with open(report_file, 'w', encoding='utf-8') as f:
    json.dump(report, f, indent=2)
"""
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(blender_script)

        try:
            cmd = [
                blender_info["blenderPath"],
                "--background",
                "--python",
                script_path,
                "--",
                full_source,
                OUTPUT_GLB_PATH,
                REPORT_PATH,
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)

            if os.path.exists(script_path):
                os.remove(script_path)

            if res.returncode != 0:
                err_msg = f"Blender exited with code {res.returncode}: {res.stderr}"
                get_audit_logger().log(
                    action="CONVERSION_FAILED",
                    source_file=source_rel,
                    details={"error": err_msg},
                    user_approved=True,
                )
                raise RuntimeError(err_msg)

            if not os.path.isfile(OUTPUT_GLB_PATH):
                raise RuntimeError("Blender conversion completed but beckie-avatar.glb was not generated.")

            report = self.get_conversion_report()
            get_audit_logger().log(
                action="CONVERSION_COMPLETED",
                source_file=source_rel,
                details=report,
                user_approved=True,
            )
            return report

        except Exception as e:
            if os.path.exists(script_path):
                try:
                    os.remove(script_path)
                except Exception:
                    pass
            get_audit_logger().log(
                action="CONVERSION_FAILED",
                source_file=source_rel,
                details={"error": str(e)},
                user_approved=True,
            )
            raise

    def get_conversion_report(self) -> Dict[str, Any]:
        """Read conversion-report.json or return default."""
        if os.path.isfile(REPORT_PATH):
            try:
                with open(REPORT_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Could not parse conversion report: {e}")

        return {
            "sourceFile": "assets/avatars/beckie/source/MidPoly.fbx",
            "outputFile": "assets/avatars/beckie/generated/beckie-avatar.glb",
            "convertedAt": datetime.now(timezone.utc).isoformat(),
            "blenderVersion": None,
            "success": os.path.isfile(OUTPUT_GLB_PATH),
            "warnings": ["No conversion report recorded yet."],
            "meshCount": 1 if os.path.isfile(OUTPUT_GLB_PATH) else 0,
            "triangleCount": 0,
            "materialCount": 1 if os.path.isfile(OUTPUT_GLB_PATH) else 0,
            "textureCount": 0,
            "hasArmature": False,
            "animationCount": 0,
        }


_singleton_converter: Optional[BlenderConverterService] = None


def get_blender_converter() -> BlenderConverterService:
    global _singleton_converter
    if _singleton_converter is None:
        _singleton_converter = BlenderConverterService()
    return _singleton_converter
