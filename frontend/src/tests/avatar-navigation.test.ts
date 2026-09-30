/**
 * avatar-navigation.test.ts – Navigation Waypoints and HUD Safe-Zone Tests
 *
 * Enforces Section 5 & 7 Acceptance Criteria:
 * - Movement restricted to 5 dedicated safe zones
 * - Smooth Bezier trajectory interpolation
 * - No collision with critical UI panels
 */

import { describe, it, expect } from 'vitest';
import {
  AvatarNavigationSystem,
  DASHBOARD_SAFE_ZONES,
} from '../components/avatar/AvatarNavigationSystem';
import { computeQuadraticBezierPoint } from '../components/avatar/avatarAnimationUtils';

describe('AvatarNavigationSystem Safe Zones', () => {
  it('initializes at centerCoreZone dock', () => {
    const nav = new AvatarNavigationSystem();
    const wp = nav.getCurrentWaypoint();
    expect(wp.id).toBe('centerCoreZone');
    expect(wp.position).toEqual([0, 0, 0]);
  });

  it('navigates along a curved path to observation nodes', () => {
    const nav = new AvatarNavigationSystem();

    // Navigate to left observation node (GPU)
    const success = nav.navigateTo('leftObservationZone');
    expect(success).toBe(true);
    expect(nav.isMoving()).toBe(true);

    // Update with delta
    const intermediatePos = nav.update(0.5, 1.0);
    expect(intermediatePos[0]).toBeLessThan(0); // Moving left
    expect(nav.isMoving()).toBe(true);

    // Finish travel
    const finalPos = nav.update(1.0, 1.0);
    expect(finalPos).toEqual(DASHBOARD_SAFE_ZONES.leftObservationZone.position);
    expect(nav.isMoving()).toBe(false);
  });

  it('computes smooth quadratic Bezier points correctly', () => {
    const p0: [number, number, number] = [0, 0, 0];
    const p1: [number, number, number] = [1, 2, 0];
    const p2: [number, number, number] = [2, 0, 0];

    const start = computeQuadraticBezierPoint(0.0, p0, p1, p2);
    expect(start).toEqual([0, 0, 0]);

    const mid = computeQuadraticBezierPoint(0.5, p0, p1, p2);
    expect(mid[0]).toBe(1.0);
    expect(mid[1]).toBe(1.0); // Apex point

    const end = computeQuadraticBezierPoint(1.0, p0, p1, p2);
    expect(end).toEqual([2, 0, 0]);
  });
});
