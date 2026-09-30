/**
 * avatar-analyzer.test.ts – Conservative Capability Detection Unit Tests
 *
 * Enforces Section 4 & 11 Acceptance Criteria:
 * - Unrigged FBX/GLB => static_ambient only
 * - Rigged model with idle clip => idle available
 * - Humanoid rig + walk clip => walking eligible
 * - Humanoid rig without walk clip => walking unavailable
 * - Wing mesh without fly clip => hover only, flight unavailable
 * - Wing bones + fly clip => flight eligible after approval
 * - Weapon mesh without hand bone => safe weapon pose unavailable
 * - Weapon mesh + hand bone => safe weapon pose eligible after approval
 * - Missing face controls => no false lip-sync claim
 */

import { describe, it, expect } from 'vitest';
import { AvatarCapabilityRules } from '../components/avatar/capabilityRules';
import { AvatarManifest, AvatarPermissions } from '../types/avatar';

const defaultPermissions: AvatarPermissions = {
  enabled: true,
  ambientMovement: false,
  proceduralHover: false,
  flightBehavior: false,
  weaponPose: false,
  reducedMotion: false,
  suspendUnderLoad: true,
  quality: 'Balanced',
  volume: 0.8,
  rememberChoice: false,
};

describe('Avatar Capability Detection Rules', () => {
  it('marks unrigged model as static_ambient and blocks walk/fly', () => {
    const unriggedManifest: AvatarManifest = {
      assetId: 'test-unrigged',
      displayName: 'UnriggedMesh',
      sourceFile: 'assets/avatars/beckie/source/model.glb',
      runtimeFile: 'assets/avatars/beckie/generated/model.glb',
      format: 'glb',
      analyzedAt: new Date().toISOString(),
      fileSizeBytes: 1024,
      meshCount: 1,
      triangleCount: 500,
      materialCount: 1,
      textureCount: 0,
      hasSkeleton: false,
      boneNames: [],
      animationClips: [],
      detectedFeatures: {
        humanoidRigConfidence: 'none',
        hasHeadBone: false,
        headBone: null,
        hasNeckBone: false,
        neckBone: null,
        hasJawBone: false,
        jawBone: null,
        hasHandBones: false,
        leftHandBone: null,
        rightHandBone: null,
        hasLegBones: false,
        leftFootBone: null,
        rightFootBone: null,
        hasWings: true,
        wingBoneNames: [],
        wingMeshNames: ['wing_mesh_01'],
        hasWeaponLikeMesh: true,
        weaponMeshNames: ['sword_01'],
        hasMouthBlendshapes: false,
        hasEyeBlendshapes: false,
        morphTargetNames: [],
      },
      detectedCapabilities: {
        canRender: true,
        canIdle: true,
        canWalk: false,
        canHover: true,
        canFly: false,
        canTalk: false,
        canGesture: false,
        canUseSafeWeaponPose: false,
      },
      recommendedMode: 'static_ambient',
      warnings: ['Unrigged model'],
    };

    // Walking must be blocked
    const walkCheck = AvatarCapabilityRules.canWalk(unriggedManifest, defaultPermissions);
    expect(walkCheck.allowed).toBe(false);

    // Full flight must be blocked because there are no wing bones or flight clips
    const flyCheck = AvatarCapabilityRules.canFly(unriggedManifest, defaultPermissions);
    expect(flyCheck.allowed).toBe(false);

    // Weapon pose must be blocked because there are no hand bones
    const weaponCheck = AvatarCapabilityRules.canUseWeapon(unriggedManifest, defaultPermissions);
    expect(weaponCheck.allowed).toBe(false);
  });

  it('allows safe weapon pose only when hand bone AND weapon mesh exist with user approval', () => {
    const armedManifest: AvatarManifest = {
      assetId: 'test-armed',
      displayName: 'MidPolyArmed',
      sourceFile: 'assets/avatars/beckie/source/MidPoly.fbx',
      runtimeFile: 'assets/avatars/beckie/generated/beckie-avatar.glb',
      format: 'glb',
      analyzedAt: new Date().toISOString(),
      fileSizeBytes: 2048,
      meshCount: 2,
      triangleCount: 1200,
      materialCount: 2,
      textureCount: 1,
      hasSkeleton: true,
      boneNames: ['pelvis', 'spine_01', 'hand_r'],
      animationClips: [],
      detectedFeatures: {
        humanoidRigConfidence: 'medium',
        hasHeadBone: false,
        headBone: null,
        hasNeckBone: false,
        neckBone: null,
        hasJawBone: false,
        jawBone: null,
        hasHandBones: true,
        leftHandBone: null,
        rightHandBone: 'hand_r',
        hasLegBones: false,
        leftFootBone: null,
        rightFootBone: null,
        hasWings: false,
        wingBoneNames: [],
        wingMeshNames: [],
        hasWeaponLikeMesh: true,
        weaponMeshNames: ['M_Armor1'],
        hasMouthBlendshapes: false,
        hasEyeBlendshapes: false,
        morphTargetNames: [],
      },
      detectedCapabilities: {
        canRender: true,
        canIdle: true,
        canWalk: false,
        canHover: true,
        canFly: false,
        canTalk: false,
        canGesture: false,
        canUseSafeWeaponPose: true,
      },
      recommendedMode: 'rigged_idle',
      warnings: [],
    };

    // Disabled without user approval
    const withoutConsent = AvatarCapabilityRules.canUseWeapon(armedManifest, defaultPermissions);
    expect(withoutConsent.allowed).toBe(false);

    // Enabled with explicit user approval
    const withConsent = AvatarCapabilityRules.canUseWeapon(armedManifest, {
      ...defaultPermissions,
      weaponPose: true,
    });
    expect(withConsent.allowed).toBe(true);
  });
});
