"""Avatar Asset Analyzer (Server-side & Standalone).

Performs strict, truthful analysis of GLB / glTF 3D assets:
- Inspects scene hierarchy, mesh names, node names, bone names
- Detects skeletons, animation clips, and morph targets
- Evaluates wing features, weapon-like objects, hand bones, and facial controls
- Computes deterministic capability flags using Section 4 conservative rules
- NEVER claims 'automatic training'
- Outputs schema-compliant beckie-avatar-manifest.json and avatar-manifest.json
"""

import os
import json
import uuid
import struct
import re
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from .avatar_audit import get_audit_logger

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GENERATED_DIR = os.path.join(BASE_DIR, "assets", "avatars", "beckie", "generated")
MANIFEST_PATH = os.path.join(GENERATED_DIR, "avatar-manifest.json")
MANIFESTS_DIR = os.path.join(BASE_DIR, "assets", "avatars", "beckie", "manifests")
BECKIE_MANIFEST_PATH = os.path.join(MANIFESTS_DIR, "beckie-avatar-manifest.json")


class AvatarAssetAnalyzer:
    """Truthful asset analyzer for local 3D models."""

    def __init__(self):
        os.makedirs(GENERATED_DIR, exist_ok=True)
        os.makedirs(MANIFESTS_DIR, exist_ok=True)

    def analyze_glb_file(self, full_path: str, relative_source: str) -> Dict[str, Any]:
        """Parse GLB binary container and extract glTF JSON metadata."""
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"Model file not found: {full_path}")

        file_size = os.path.getsize(full_path)
        warnings: List[str] = []

        if file_size > 250 * 1024 * 1024:
            warnings.append(
                f"Asset is extremely large ({round(file_size / (1024 * 1024), 1)} MB > 250 MB). Memory pressure possible."
            )

        # Read GLB header & JSON chunk
        gltf: Dict[str, Any] = {}
        with open(full_path, "rb") as f:
            header = f.read(12)
            if len(header) < 12:
                raise ValueError("Corrupt GLB file: header truncated")
            magic, version, length = struct.unpack("<4sII", header)
            if magic != b"glTF":
                raise ValueError(f"Invalid magic identifier: {magic}, expected b'glTF'")

            chunk_header = f.read(8)
            if len(chunk_header) < 8:
                raise ValueError("Corrupt GLB file: chunk header truncated")
            chunk_len, chunk_type = struct.unpack("<II", chunk_header)
            # chunk_type 0x4E4F534A is JSON
            json_bytes = f.read(chunk_len)
            try:
                gltf = json.loads(json_bytes.decode("utf-8"))
            except Exception as e:
                raise ValueError(f"Failed to parse glTF JSON chunk: {e}")

        # 1. Inspect Hierarchy & Nodes
        nodes = gltf.get("nodes", [])
        node_names = [n.get("name", f"node_{i}") for i, n in enumerate(nodes)]

        # 2. Inspect Meshes, Primitives & Materials
        meshes = gltf.get("meshes", [])
        mesh_names = [m.get("name", f"mesh_{i}") for i, m in enumerate(meshes)]
        mesh_count = len(meshes)
        material_count = len(gltf.get("materials", []))
        texture_count = len(gltf.get("textures", []))
        triangle_count = self._estimate_triangle_count(gltf)

        # 3. Inspect Skeletons / Armatures
        skins = gltf.get("skins", [])
        has_skeleton = len(skins) > 0
        bone_names: List[str] = []
        if has_skeleton:
            joint_indices = set()
            for s in skins:
                joint_indices.update(s.get("joints", []))
            for idx in joint_indices:
                if idx < len(nodes):
                    bone_names.append(nodes[idx].get("name", f"bone_{idx}"))

        # 4. Inspect Animation Clips
        animations = gltf.get("animations", [])
        structured_clips: List[Dict[str, Any]] = []
        animation_clip_names: List[str] = []
        for i, a in enumerate(animations):
            clip_name = a.get("name", f"anim_{i}")
            animation_clip_names.append(clip_name)
            role = self._match_animation_role(clip_name)
            structured_clips.append({
                "name": clip_name,
                "durationSeconds": 0.0,
                "matchedRole": role,
            })

        # 5. Inspect Morph Targets (Blendshapes)
        morph_targets: List[str] = []
        for m in meshes:
            if "extras" in m and "targetNames" in m["extras"]:
                morph_targets.extend(m["extras"]["targetNames"])
            for p in m.get("primitives", []):
                for target_dict in p.get("targets", []):
                    for tn in target_dict.keys():
                        if tn not in morph_targets:
                            morph_targets.append(tn)

        # 6. Feature Detection (Wings, Weapons, Hands, Head, Mouth)
        features, feature_warnings = self._detect_features(
            node_names, mesh_names, bone_names, morph_targets, relative_source, has_skeleton
        )
        warnings.extend(feature_warnings)

        # 7. Capabilities Computation
        capabilities = self._detect_capabilities(has_skeleton, bone_names, animation_clip_names, features)

        # 8. Conservative Recommendation
        if not has_skeleton:
            recommended_mode = "static_ambient"
            warnings.append("This asset is not rigged. Beckie can use ambient motion only.")
        elif len(animation_clip_names) >= 2 and capabilities["canWalk"]:
            recommended_mode = "rigged_character"
        elif has_skeleton:
            recommended_mode = "rigged_idle"
        else:
            recommended_mode = "requires_review"

        display_name = os.path.splitext(os.path.basename(relative_source))[0]
        asset_id = str(uuid.uuid4())

        manifest = {
            "assetId": asset_id,
            "displayName": display_name,
            "sourceFile": relative_source.replace("\\", "/"),
            "runtimeFile": relative_source.replace("\\", "/"),
            "format": "glb",
            "analyzedAt": datetime.now(timezone.utc).isoformat(),
            "fileSizeBytes": file_size,
            "licenseNote": "user supplied local asset",
            "meshCount": mesh_count,
            "triangleCount": triangle_count,
            "materialCount": material_count,
            "textureCount": texture_count,
            "hasSkeleton": has_skeleton,
            "boneNames": bone_names,
            "animationClips": structured_clips,
            "detectedFeatures": features,
            "detectedCapabilities": capabilities,
            "recommendedMode": recommended_mode,
            "warnings": warnings,
        }

        # Save to both primary manifest paths
        with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        with open(BECKIE_MANIFEST_PATH, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        asset_manifest_path = os.path.join(MANIFESTS_DIR, f"{asset_id}.json")
        with open(asset_manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        get_audit_logger().log(
            action="CAPABILITY_DETECTION",
            asset_id=asset_id,
            source_file=relative_source,
            details={
                "hasSkeleton": has_skeleton,
                "meshCount": mesh_count,
                "animationClips": animation_clip_names,
                "capabilities": capabilities,
                "features": features,
                "recommendedMode": recommended_mode,
            },
            user_approved=True,
            warnings=warnings,
        )

        return manifest

    def _estimate_triangle_count(self, gltf: Dict[str, Any]) -> int:
        triangles = 0
        meshes = gltf.get("meshes", [])
        accessors = gltf.get("accessors", [])
        for m in meshes:
            for p in m.get("primitives", []):
                idx = p.get("indices")
                if idx is not None and idx < len(accessors):
                    count = accessors[idx].get("count", 0)
                    triangles += count // 3
                elif "POSITION" in p.get("attributes", {}):
                    pos_idx = p["attributes"]["POSITION"]
                    if pos_idx < len(accessors):
                        triangles += accessors[pos_idx].get("count", 0) // 3
        return triangles

    def _match_animation_role(self, clip_name: str) -> str:
        c = clip_name.lower()
        if re.search(r"(idle|stand|wait)", c):
            return "idle"
        elif re.search(r"(walk|stride|step)", c):
            return "walk"
        elif re.search(r"(run|sprint|dash)", c):
            return "run"
        elif re.search(r"(fly|flight)", c):
            return "fly"
        elif re.search(r"(hover|levitate)", c):
            return "hover"
        elif re.search(r"(talk|speak|dialogue)", c):
            return "talk"
        elif re.search(r"(wave|greet|bow)", c):
            return "wave"
        elif re.search(r"(gesture|point|shrug)", c):
            return "gesture"
        elif re.search(r"(weapon|attack|sword|slash)", c):
            return "weapon"
        return "unknown"

    def _detect_features(
        self,
        node_names: List[str],
        mesh_names: List[str],
        bone_names: List[str],
        morph_targets: List[str],
        relative_source: str = "",
        has_skeleton: bool = False,
    ) -> Tuple[Dict[str, Any], List[str]]:
        warnings: List[str] = []

        # Wings detection
        wing_regex = re.compile(r"(wing|wing_l|wing_r|leftwing|rightwing|feather|archangel)", re.IGNORECASE)
        wing_bones = [b for b in bone_names if wing_regex.search(b)]
        wing_nodes = [n for n in (node_names + mesh_names) if wing_regex.search(n)]
        has_wings = (
            len(wing_bones) > 0
            or len(wing_nodes) > 0
            or bool(wing_regex.search(relative_source))
        )

        # Hand bones detection
        left_hand_bone = None
        right_hand_bone = None
        for b in bone_names:
            if re.search(r"(left.*hand|hand.*l|wrist.*l|l.*wrist)", b, re.IGNORECASE):
                left_hand_bone = b
            elif re.search(r"(right.*hand|hand.*r|wrist.*r|r.*wrist)", b, re.IGNORECASE):
                right_hand_bone = b
        has_hand_bones = left_hand_bone is not None or right_hand_bone is not None

        # Leg / Foot bones detection
        left_foot_bone = None
        right_foot_bone = None
        for b in bone_names:
            if re.search(r"(left.*foot|foot.*l|ankle.*l|l.*foot)", b, re.IGNORECASE):
                left_foot_bone = b
            elif re.search(r"(right.*foot|foot.*r|ankle.*r|r.*foot)", b, re.IGNORECASE):
                right_foot_bone = b
        has_leg_bones = (
            left_foot_bone is not None
            or right_foot_bone is not None
            or any(re.search(r"(leg|thigh|calf|knee)", b, re.IGNORECASE) for b in bone_names)
        )

        # Weapon-like meshes
        weapon_regex = re.compile(r"(sword|katana|blade|staff|shield|gun|weapon|halberd|spear|bow|boss)", re.IGNORECASE)
        weapon_meshes = [m for m in mesh_names if weapon_regex.search(m)]
        for n in node_names:
            if weapon_regex.search(n) and n not in weapon_meshes:
                weapon_meshes.append(n)
        has_weapon_like_mesh = (
            len(weapon_meshes) > 0
            or bool(weapon_regex.search(relative_source))
        )

        # Head bone
        head_bone = None
        for b in bone_names:
            if re.search(r"(head|skull)", b, re.IGNORECASE) and not re.search(r"headlight", b, re.IGNORECASE):
                head_bone = b
                break
        has_head_bone = head_bone is not None

        # Neck bone
        neck_bone = None
        for b in bone_names:
            if re.search(r"neck", b, re.IGNORECASE):
                neck_bone = b
                break
        has_neck_bone = neck_bone is not None

        # Jaw bone
        jaw_bone = None
        for b in bone_names:
            if re.search(r"(jaw|chin)", b, re.IGNORECASE):
                jaw_bone = b
                break
        has_jaw_bone = jaw_bone is not None

        # Mouth / Jaw blendshapes
        mouth_regex = re.compile(r"(jaw|mouth|lip|viseme|v_aa|v_oh|v_ch|smile|talk)", re.IGNORECASE)
        has_mouth = any(mouth_regex.search(mt) for mt in morph_targets)

        eye_regex = re.compile(r"(eye|blink|brow|wink)", re.IGNORECASE)
        has_eyes = any(eye_regex.search(mt) for mt in morph_targets)

        # Rig confidence score
        if has_skeleton and has_head_bone and has_hand_bones and has_leg_bones:
            rig_confidence = "high"
        elif has_skeleton and (has_hand_bones or has_leg_bones):
            rig_confidence = "medium"
        elif has_skeleton:
            rig_confidence = "low"
        else:
            rig_confidence = "none"

        # Contextual warnings
        if has_wings and not wing_bones:
            warnings.append("Wing geometry detected, but no wing bones found. Dynamic wing flap cannot be rigged.")
        if has_weapon_like_mesh and not has_hand_bones:
            warnings.append("Weapon-like geometry detected, but no hand bones present for posing.")

        features = {
            "humanoidRigConfidence": rig_confidence,
            "hasHeadBone": has_head_bone,
            "headBone": head_bone,
            "hasNeckBone": has_neck_bone,
            "neckBone": neck_bone,
            "hasJawBone": has_jaw_bone,
            "jawBone": jaw_bone,
            "hasHandBones": has_hand_bones,
            "leftHandBone": left_hand_bone,
            "rightHandBone": right_hand_bone,
            "hasLegBones": has_leg_bones,
            "leftFootBone": left_foot_bone,
            "rightFootBone": right_foot_bone,
            "hasWings": has_wings,
            "wingBoneNames": wing_bones,
            "wingMeshNames": wing_nodes,
            "hasWeaponLikeMesh": has_weapon_like_mesh,
            "weaponMeshNames": weapon_meshes,
            "hasMouthBlendshapes": has_mouth,
            "hasEyeBlendshapes": has_eyes,
            "morphTargetNames": morph_targets,
            # Backward compatibility aliases
            "wingBones": wing_bones,
            "weaponMeshes": weapon_meshes,
            "hasJawOrMouthBlendshape": has_mouth,
            "morphTargets": morph_targets,
        }
        return features, warnings

    def _detect_capabilities(
        self,
        has_skeleton: bool,
        bone_names: List[str],
        animation_clips: List[str],
        features: Dict[str, Any],
    ) -> Dict[str, bool]:
        """Apply strict capability rules from Section 4."""
        clips_lower = [c.lower() for c in animation_clips]

        # 1. Render: Always true for valid loaded asset
        can_render = True

        # 2. Idle: Always supported procedurally (floating/bobbing) or via clip
        can_idle = True

        # 3. Walk: Requires humanoid skeleton (hips/spine/leg) AND walk animation clip
        has_legs = features.get("hasLegBones", False) or any(
            re.search(r"(leg|foot|thigh|knee|hip)", b, re.IGNORECASE) for b in bone_names
        )
        has_walk_clip = any("walk" in c for c in clips_lower)
        can_walk = has_skeleton and has_legs and has_walk_clip

        # 4. Hover: Always supported procedurally in 3D HUD (bobbing / floating)
        can_hover = True

        # 5. Fly: Requires wing bones AND fly animation clip
        has_fly_clip = any(re.search(r"(fly|flight)", c) for c in clips_lower)
        has_wing_bones = len(features.get("wingBoneNames", [])) > 0 or len(features.get("wingBones", [])) > 0
        can_fly = features.get("hasWings", False) and has_wing_bones and has_fly_clip

        # 6. Talk: Requires mouth/jaw blendshape OR (skeleton + talk clip)
        has_talk_clip = any("talk" in c or "speak" in c for c in clips_lower)
        can_talk = (
            features.get("hasMouthBlendshapes", False)
            or features.get("hasJawBone", False)
            or (has_skeleton and has_talk_clip)
        )

        # 7. Gesture: Requires hand/arm bones and animation clip
        has_arms = any(re.search(r"(arm|hand|shoulder)", b, re.IGNORECASE) for b in bone_names)
        has_gesture_clip = any(re.search(r"(wave|gesture|bow|nod|greet)", c) for c in clips_lower)
        can_gesture = has_skeleton and has_arms and has_gesture_clip

        # 8. Weapon Safe Pose: Requires hand bone AND weapon mesh
        can_use_safe_weapon_pose = features.get("hasHandBones", False) and features.get("hasWeaponLikeMesh", False)

        return {
            "canRender": can_render,
            "canIdle": can_idle,
            "canWalk": can_walk,
            "canHover": can_hover,
            "canFly": can_fly,
            "canTalk": can_talk,
            "canGesture": can_gesture,
            "canUseSafeWeaponPose": can_use_safe_weapon_pose,
            # Backward compatibility aliases
            "canRun": can_walk and any("run" in c for c in clips_lower),
            "canUseWeapon": can_use_safe_weapon_pose,
        }


_singleton_analyzer: Optional[AvatarAssetAnalyzer] = None


def get_avatar_analyzer() -> AvatarAssetAnalyzer:
    global _singleton_analyzer
    if _singleton_analyzer is None:
        _singleton_analyzer = AvatarAssetAnalyzer()
    return _singleton_analyzer
