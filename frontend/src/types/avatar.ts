/**
 * avatar.ts – Type definitions for BECKIE Local 3D Avatar System
 *
 * Implements strict schema contracts for:
 * - Asset discovery and validation
 * - Truthful capability and feature detection (Section 4 Manifest Schema)
 * - Finite State Machine (FSM) avatar behavior (15 discrete states)
 * - Navigation waypoints & dashboard-safe zones
 * - User consent, revocable permissions & local audit
 */

export type AvatarFsmState =
  | 'HIDDEN'
  | 'SPAWNING'
  | 'IDLE'
  | 'OBSERVING'
  | 'WALKING'
  | 'HOVERING'
  | 'FLYING'
  | 'LISTENING'
  | 'THINKING'
  | 'SPEAKING'
  | 'GREETING'
  | 'GESTURING'
  | 'SAFE_WEAPON_POSE'
  | 'PAUSED'
  | 'ERROR';

export type RecommendedMode =
  | 'static_ambient'
  | 'rigged_idle'
  | 'rigged_character'
  | 'requires_review';

export type AvatarQuality = 'Low' | 'Balanced' | 'High';

export type AnimationRole =
  | 'idle'
  | 'walk'
  | 'run'
  | 'fly'
  | 'hover'
  | 'talk'
  | 'wave'
  | 'gesture'
  | 'weapon'
  | 'unknown';

export interface ManifestAnimationClip {
  name: string;
  durationSeconds: number;
  matchedRole: AnimationRole;
}

export interface DetectedCapabilities {
  canRender: boolean;
  canIdle: boolean;
  canWalk: boolean;
  canHover: boolean;
  canFly: boolean;
  canTalk: boolean;
  canGesture: boolean;
  canUseSafeWeaponPose: boolean;
  // Backward compatibility alias for UI checks
  canRun?: boolean;
  canUseWeapon?: boolean;
}

export interface DetectedFeatures {
  humanoidRigConfidence: 'none' | 'low' | 'medium' | 'high';

  hasHeadBone: boolean;
  headBone: string | null;

  hasNeckBone: boolean;
  neckBone: string | null;

  hasJawBone: boolean;
  jawBone: string | null;

  hasHandBones: boolean;
  leftHandBone: string | null;
  rightHandBone: string | null;

  hasLegBones: boolean;
  leftFootBone: string | null;
  rightFootBone: string | null;

  hasWings: boolean;
  wingBoneNames: string[];
  wingMeshNames: string[];

  hasWeaponLikeMesh: boolean;
  weaponMeshNames: string[];

  hasMouthBlendshapes: boolean;
  hasEyeBlendshapes: boolean;
  morphTargetNames: string[];

  // Backward compatibility aliases
  wingBones?: string[];
  weaponMeshes?: string[];
  hasJawOrMouthBlendshape?: boolean;
  morphTargets?: string[];
}

export interface AvatarManifest {
  assetId: string;
  displayName: string;
  sourceFile: string;
  runtimeFile: string;
  format: 'glb';
  analyzedAt: string;
  fileSizeBytes: number;

  meshCount: number;
  triangleCount: number;
  materialCount: number;
  textureCount: number;

  hasSkeleton: boolean;
  boneNames: string[];
  animationClips: ManifestAnimationClip[];

  detectedFeatures: DetectedFeatures;
  detectedCapabilities: DetectedCapabilities;

  recommendedMode: RecommendedMode;
  warnings: string[];

  // Backward compatibility fields
  licenseNote?: string;
}

export interface DiscoveredAsset {
  fileName: string;
  relativePath: string;
  format: string;
  sizeBytes: number;
  sizeMb: number;
  isRuntimeReady: boolean;
  isLarge: boolean;
  location: string;
}

export interface AvatarPermissions {
  enabled: boolean;
  ambientMovement: boolean;
  proceduralHover: boolean;
  flightBehavior: boolean;
  weaponPose: boolean;
  reducedMotion: boolean;
  suspendUnderLoad: boolean;
  quality: AvatarQuality;
  volume: number;
  rememberChoice: boolean;
}

export interface AvatarSystemState extends AvatarPermissions {
  activeAssetId: string | null;
  activeManifestPath: string | null;
  runtimeFilePath: string | null;
}

export interface AvatarSpeechState {
  isSpeaking: boolean;
  textSnippet: string;
  voiceEngine: string;
  amplitude: number;
  visemeEnvelope: number[];
}

export interface AvatarZoneWaypoint {
  id: string;
  name: string;
  position: [number, number, number];
  rotation: [number, number, number];
  description: string;
}

export type SafeZoneKey =
  | 'centerCoreZone'
  | 'leftObservationZone'
  | 'rightObservationZone'
  | 'upperOrbitZone'
  | 'lowerCenterZone'
  | 'spotifyStationZone'
  | 'affectiveZone'
  | 'networkZone';

export interface FlightTuning {
  wingSpeedMultiplier: number;
  liftMultiplier: number;
  dwellTimeMultiplier: number;
  speechCalloutsEnabled: boolean;
  voiceAudioEnabled: boolean;
}

export interface BlenderDetectionInfo {
  isAvailable: boolean;
  blenderPath: string | null;
  blenderVersion: string | null;
  instructions: string;
}

export interface ConversionPreviewInfo {
  sourceFileName: string;
  sourceSizeBytes: number;
  sourceSizeMb: number;
  sourcePath: string;
  outputPath: string;
  action: string;
  linkedTexturesDetected: boolean;
  processedLocallyOnly: boolean;
}

export interface ConversionReportInfo {
  sourceFile: string;
  outputFile: string;
  convertedAt: string;
  blenderVersion: string | null;
  success: boolean;
  warnings: string[];
  meshCount: number;
  triangleCount: number;
  materialCount: number;
  textureCount: number;
  hasArmature: boolean;
  animationCount: number;
}
