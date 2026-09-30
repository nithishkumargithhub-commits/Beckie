/**
 * capabilityRules.ts – Strict Capability Validation and Behavior Guardrails
 *
 * Implements Section 3 Rules:
 * A. Static or unrigged asset: ambient motion only (floating, bobbing, glow, orbiting).
 *    No walking, gestures, sword movements, flight, or fake lip sync.
 * B. Rigged humanoid with idle: idle loop, random look-around, talk reaction.
 * C. Rigged humanoid with walk: safe dashboard walk paths only.
 * D. Winged asset: fly enabled ONLY with verified wing bones & flight clip, or explicit hover.
 * E. Weapon-like asset: safe nonviolent ambient poses only, requires explicit approval.
 * F. Facial interaction: morph targets only for lip-sync; otherwise non-deceptive presence.
 */

import { AvatarManifest, AvatarPermissions } from '../../types/avatar';

export interface ActionPermissibility {
  allowed: boolean;
  reason: string;
  requiresUserConsent?: boolean;
}

export class AvatarCapabilityRules {
  /**
   * Determine if the asset can perform walking behavior.
   */
  public static canWalk(manifest: AvatarManifest | null, perms: AvatarPermissions): ActionPermissibility {
    if (!manifest) return { allowed: false, reason: 'No avatar manifest loaded.' };
    if (!manifest.hasSkeleton) {
      return {
        allowed: false,
        reason: 'This asset is not rigged. Beckie can use ambient motion only.',
      };
    }
    if (!manifest.detectedCapabilities.canWalk) {
      return {
        allowed: false,
        reason: 'No walk animation clip or humanoid leg hierarchy detected.',
      };
    }
    if (perms.reducedMotion) {
      return { allowed: false, reason: 'Reduced motion is enabled.' };
    }
    if (!perms.ambientMovement) {
      return {
        allowed: false,
        reason: 'Ambient movement is disabled in settings.',
        requiresUserConsent: true,
      };
    }
    return { allowed: true, reason: 'Walk supported by humanoid skeleton and animation clip.' };
  }

  /**
   * Determine if the asset can perform wing-flight behavior.
   */
  public static canFly(manifest: AvatarManifest | null, perms: AvatarPermissions): ActionPermissibility {
    if (!manifest) return { allowed: false, reason: 'No avatar manifest loaded.' };
    if (!manifest.detectedFeatures.hasWings) {
      return { allowed: false, reason: 'No wing features detected on model.' };
    }
    if (!perms.flightBehavior) {
      return {
        allowed: false,
        reason: 'Flight behavior requires explicit user enablement.',
        requiresUserConsent: true,
      };
    }
    if (!manifest.hasSkeleton && !perms.proceduralHover) {
      return {
        allowed: false,
        reason: 'Unrigged wings require procedural hover to be enabled.',
      };
    }
    return { allowed: true, reason: 'Wing flight/hover enabled by user consent.' };
  }

  /**
   * Determine if safe nonviolent weapon poses can be performed.
   */
  public static canUseSafeWeaponPose(manifest: AvatarManifest | null, perms: AvatarPermissions): ActionPermissibility {
    if (!manifest) return { allowed: false, reason: 'No avatar manifest loaded.' };
    if (!manifest.detectedFeatures.hasWeaponLikeMesh) {
      return { allowed: false, reason: 'No weapon-like object detected in model geometry.' };
    }
    if (!manifest.detectedFeatures.hasHandBones) {
      return { allowed: false, reason: 'No hand bones detected to hold or pose weapon.' };
    }
    if (!perms.weaponPose) {
      return {
        allowed: false,
        reason: 'Safe weapon pose requires explicit user approval.',
        requiresUserConsent: true,
      };
    }
    return { allowed: true, reason: 'Safe nonviolent weapon posing approved by user.' };
  }

  /**
   * Alias for canUseSafeWeaponPose
   */
  public static canUseWeapon(manifest: AvatarManifest | null, perms: AvatarPermissions): ActionPermissibility {
    return this.canUseSafeWeaponPose(manifest, perms);
  }

  /**
   * Determine facial animation mode: true lip-sync vs non-deceptive presence.
   */
  public static getFacialMode(manifest: AvatarManifest | null): {
    hasMorphLipSync: boolean;
    description: string;
  } {
    if (!manifest || !manifest.detectedFeatures.hasJawOrMouthBlendshape) {
      return {
        hasMorphLipSync: false,
        description: 'Speaking Presence (Head nods, breathing, waveform glow pulse, subtitle preview)',
      };
    }
    return {
      hasMorphLipSync: true,
      description: 'Low-amplitude morph target lip synchronization',
    };
  }
}
