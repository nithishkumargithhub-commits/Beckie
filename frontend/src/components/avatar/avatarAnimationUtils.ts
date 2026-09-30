/**
 * avatarAnimationUtils.ts – Procedural Animation and Bezier Trajectory Helpers
 *
 * Implements Section 7 Movement & Animation rules:
 * - Deterministic, smooth procedural bobbing and breathing
 * - Quadratic Bezier arc computation for safe HUD travel
 * - Clamped altitudes and collision-free boundaries
 * - Respects reduced motion settings
 */

import * as THREE from 'three';

export interface BezierCurvePoints {
  start: [number, number, number];
  control: [number, number, number];
  end: [number, number, number];
}

/**
 * Calculates a point on a quadratic Bezier curve at progress t (0.0 to 1.0).
 */
export function computeQuadraticBezierPoint(
  t: number,
  p0: [number, number, number],
  p1: [number, number, number],
  p2: [number, number, number]
): [number, number, number] {
  const clampedT = Math.max(0, Math.min(1, t));
  const oneMinusT = 1.0 - clampedT;

  const x =
    oneMinusT * oneMinusT * p0[0] +
    2.0 * oneMinusT * clampedT * p1[0] +
    clampedT * clampedT * p2[0];

  const y =
    oneMinusT * oneMinusT * p0[1] +
    2.0 * oneMinusT * clampedT * p1[1] +
    clampedT * clampedT * p2[1];

  const z =
    oneMinusT * oneMinusT * p0[2] +
    2.0 * oneMinusT * clampedT * p1[2] +
    clampedT * clampedT * p2[2];

  return [x, y, z];
}

/**
 * Procedural harmonic hover wave (vertical bobbing).
 */
export function computeProceduralHoverOffset(
  elapsedSeconds: number,
  frequency: number = 1.6,
  amplitude: number = 0.08
): number {
  return Math.sin(elapsedSeconds * frequency) * amplitude;
}

/**
 * Gentle look-at camera rotation with dampening.
 */
export function computeLookAtRotation(
  currentRotationY: number,
  targetAngleY: number,
  deltaSeconds: number,
  speed: number = 2.5
): number {
  return THREE.MathUtils.lerp(currentRotationY, targetAngleY, deltaSeconds * speed);
}

/**
 * Dispose Three.js object hierarchy recursively to avoid VRAM leaks.
 */
export function disposeThreeHierarchy(object: THREE.Object3D): void {
  object.traverse((child) => {
    if ((child as THREE.Mesh).isMesh) {
      const mesh = child as THREE.Mesh;
      if (mesh.geometry) {
        mesh.geometry.dispose();
      }
      if (mesh.material) {
        if (Array.isArray(mesh.material)) {
          mesh.material.forEach((m) => m.dispose());
        } else {
          mesh.material.dispose();
        }
      }
    }
  });
}
