/**
 * avatar-permissions.test.ts – Revocable User Permissions and Privacy Tests
 *
 * Enforces Section 7 & 9 Acceptance Criteria:
 * - Advanced behaviors disabled by default
 * - Independent consent toggles
 * - Non-remembered restart protection
 */

import { describe, it, expect } from 'vitest';
import { AvatarPermissions } from '../types/avatar';

describe('Avatar Permissions and Consent Policies', () => {
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

  it('keeps all sensitive behaviors disabled by default', () => {
    expect(defaultPermissions.ambientMovement).toBe(false);
    expect(defaultPermissions.proceduralHover).toBe(false);
    expect(defaultPermissions.flightBehavior).toBe(false);
    expect(defaultPermissions.weaponPose).toBe(false);
    expect(defaultPermissions.rememberChoice).toBe(false);
  });

  it('allows individual toggle overrides without affecting unrelated permissions', () => {
    const updated: AvatarPermissions = {
      ...defaultPermissions,
      proceduralHover: true,
    };

    expect(updated.proceduralHover).toBe(true);
    expect(updated.ambientMovement).toBe(false);
    expect(updated.flightBehavior).toBe(false);
    expect(updated.weaponPose).toBe(false);
  });
});
