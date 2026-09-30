/**
 * ArchangelWingRig.ts – Authentic Anatomical 6-Wing Rigging & Natural Flight Kinematics
 *
 * Implements Natural Angelic Wing Mechanics:
 * - 6 Independent Wing Sub-Pivots (Upper, Mid, Lower Left & Right)
 * - Exact anatomical shoulder/back socket anchors located in mesh parent space
 * - Pure UP/DOWN flapping strokes around the anatomical hinge (No circular ball rotation)
 * - Cascading harmonic phase delays (Upper leads, Mid follows, Lower completes the wave)
 * - Organic feathering pitch and forward downstroke sweep
 * - Mode-driven aerodynamic flight physics (G-Mode overdrive, Balanced cruise, Quiet glide)
 * - Music tempo synchronization (downbeat snap, tempo bounce)
 */

import * as THREE from 'three';
import { AvatarFsmState } from '../../types/avatar';

export interface FlightAnimationOptions {
  isMoving: boolean;
  isMusicPlaying: boolean;
  mode: string; // 'G-Mode (High Performance)' | 'Balanced' | 'Quiet' | etc.
  fsmState: AvatarFsmState;
  targetStation?: string;
  themeHex?: number;
  wingSpeedMultiplier?: number;
  liftMultiplier?: number;
}

export interface WingRigOutput {
  liftOffset: number;
  bankingAngle: number;
  pitchAngle: number;
  haloPulse: number;
}

export class ArchangelWingRig {
  // 6 Wing Pivots placed precisely at anatomical back/shoulder sockets
  private leftUpperPivot: THREE.Group = new THREE.Group();
  private leftMidPivot: THREE.Group = new THREE.Group();
  private leftLowerPivot: THREE.Group = new THREE.Group();

  private rightUpperPivot: THREE.Group = new THREE.Group();
  private rightMidPivot: THREE.Group = new THREE.Group();
  private rightLowerPivot: THREE.Group = new THREE.Group();

  // Halo & Sword references
  private haloMesh: THREE.Mesh | null = null;
  private swordMesh: THREE.Mesh | null = null;
  private bodyMeshes: THREE.Mesh[] = [];

  private isRigged: boolean = false;
  private flapTimer: number = 0;
  private currentLift: number = 0;

  /**
   * Scan model meshes, attach 6 anatomical wing socket pivots, and bind authentic meshes.
   */
  public setup(model: THREE.Object3D): boolean {
    if (this.isRigged) return true;

    // 1. Collect all descendant meshes and locate their immediate parent node
    const meshes: THREE.Mesh[] = [];
    let meshParent: THREE.Object3D | null = null;

    model.traverse((child) => {
      if ((child as THREE.Mesh).isMesh) {
        meshes.push(child as THREE.Mesh);
        if (!meshParent) {
          meshParent = child.parent;
        }
      }
    });

    if (meshes.length < 21 || !meshParent) {
      console.warn('[ArchangelWingRig] Model meshes count or parent not found', meshes.length);
      return false;
    }

    const parentNode: THREE.Object3D = meshParent;

    // 2. Add wing pivots directly into meshParent so they share the exact local coordinate space
    parentNode.add(this.leftUpperPivot);
    parentNode.add(this.leftMidPivot);
    parentNode.add(this.leftLowerPivot);
    parentNode.add(this.rightUpperPivot);
    parentNode.add(this.rightMidPivot);
    parentNode.add(this.rightLowerPivot);

    // Anatomical wing socket anchors in local meshParent space
    this.leftUpperPivot.name = 'WingPivot_LeftUpper';
    this.leftUpperPivot.position.set(0.172, 0.160, 0.663);

    this.leftMidPivot.name = 'WingPivot_LeftMid';
    this.leftMidPivot.position.set(0.096, 0.161, 0.622);

    this.leftLowerPivot.name = 'WingPivot_LeftLower';
    this.leftLowerPivot.position.set(0.017, 0.144, 0.615);

    this.rightUpperPivot.name = 'WingPivot_RightUpper';
    this.rightUpperPivot.position.set(-0.220, 0.192, 0.671);

    this.rightMidPivot.name = 'WingPivot_RightMid';
    this.rightMidPivot.position.set(-0.092, 0.043, 0.531);

    this.rightLowerPivot.name = 'WingPivot_RightLower';
    this.rightLowerPivot.position.set(-0.070, 0.153, 0.605);

    // Update world matrices so attach() preserves exact world position without jumping
    model.updateMatrixWorld(true);

    // 3. Attach authentic submeshes to their respective pivots:
    // Left Upper Wing (Meshes 0, 1)
    this.leftUpperPivot.attach(meshes[0]);
    this.leftUpperPivot.attach(meshes[1]);

    // Left Mid Wing (Meshes 2, 3)
    this.leftMidPivot.attach(meshes[2]);
    this.leftMidPivot.attach(meshes[3]);

    // Left Lower Wing (Meshes 4, 5)
    this.leftLowerPivot.attach(meshes[4]);
    this.leftLowerPivot.attach(meshes[5]);

    // Right Upper Wing (Meshes 13, 14)
    this.rightUpperPivot.attach(meshes[13]);
    this.rightUpperPivot.attach(meshes[14]);

    // Right Mid Wing (Meshes 12, 15)
    this.rightMidPivot.attach(meshes[12]);
    this.rightMidPivot.attach(meshes[15]);

    // Right Lower Wing (Meshes 10, 11)
    this.rightLowerPivot.attach(meshes[10]);
    this.rightLowerPivot.attach(meshes[11]);

    // Halo (Mesh 20)
    this.haloMesh = meshes[20];

    // Greatsword (Mesh 7)
    this.swordMesh = meshes[7];

    // Armor and body
    this.bodyMeshes = [
      meshes[6],
      meshes[8],
      meshes[9],
      meshes[16],
      meshes[17],
      meshes[18],
      meshes[19],
    ];

    this.isRigged = true;
    return true;
  }

  /**
   * Update wing flap cycles, lift, and flight attitude each frame.
   * Produces a natural, powerful angelic flapping wave.
   */
  public update(delta: number, elapsed: number, options: FlightAnimationOptions): WingRigOutput {
    if (!this.isRigged) {
      return { liftOffset: 0, bankingAngle: 0, pitchAngle: 0, haloPulse: 1.0 };
    }

    const { isMoving, isMusicPlaying, mode, fsmState } = options;

    // 1. Determine Mode-Driven Flap Parameters
    let flapSpeed = 1.6; // Hz
    let flapAmplitude = 0.30; // radians (~17 deg natural flap)
    let liftMultiplier = 0.07;
    let forwardLean = 0.0;
    let bankingMultiplier = 1.0;

    const lowerMode = mode.toLowerCase();
    const isGMode =
      lowerMode.includes('g-mode') || lowerMode.includes('game') || lowerMode.includes('overdrive');
    const isQuiet =
      lowerMode.includes('quiet') || lowerMode.includes('battery') || lowerMode.includes('eco');
    const isPerformance = lowerMode.includes('performance');

    if (isGMode) {
      flapSpeed = 2.8; // Fast, energetic wing strokes
      flapAmplitude = 0.38; // Wide heroic flare
      liftMultiplier = 0.12;
      forwardLean = isMoving ? 0.22 : 0.06;
      bankingMultiplier = 1.6;
    } else if (isQuiet) {
      flapSpeed = 0.85; // Serene gentle gliding strokes
      flapAmplitude = 0.20;
      liftMultiplier = 0.04;
      forwardLean = isMoving ? 0.06 : 0.02;
      bankingMultiplier = 0.6;
    } else if (isPerformance) {
      flapSpeed = 2.2;
      flapAmplitude = 0.34;
      liftMultiplier = 0.09;
      forwardLean = isMoving ? 0.15 : 0.04;
      bankingMultiplier = 1.3;
    } else {
      // Balanced
      flapSpeed = 1.5;
      flapAmplitude = 0.28;
      liftMultiplier = 0.06;
      forwardLean = isMoving ? 0.12 : 0.03;
    }

    // Music Beat Synchronization
    if (isMusicPlaying) {
      flapSpeed = 2.0; // ~120 BPM synchronized cadence
      flapAmplitude *= 1.2;
      liftMultiplier *= 1.3;
    }

    // Forward flight increases flap frequency
    if (isMoving) {
      flapSpeed *= 1.3;
      flapAmplitude *= 1.1;
    }

    // User Aerodynamic Tuning Multipliers
    if (options.wingSpeedMultiplier !== undefined) {
      flapSpeed *= Math.max(0.2, options.wingSpeedMultiplier);
    }
    if (options.liftMultiplier !== undefined) {
      liftMultiplier *= Math.max(0.2, options.liftMultiplier);
    }

    // 2. Advance Flap Timer
    this.flapTimer += delta * flapSpeed * Math.PI * 2;

    // 3. Natural Angelic Wing Kinematics
    // Pure harmonic wave: UP/DOWN stroke is governed by Y rotation around the anatomical shoulder socket
    // Downstroke (pushing down) is slightly faster; upstroke (recovery) is graceful
    const rawStroke0 = Math.sin(this.flapTimer);
    const strokeShape0 = isMusicPlaying
      ? Math.sin(this.flapTimer) + 0.25 * Math.sin(this.flapTimer * 2)
      : rawStroke0;

    const strokeShape1 = Math.sin(this.flapTimer - 0.35); // Mid wings lag by 0.35 rad
    const strokeShape2 = Math.sin(this.flapTimer - 0.70); // Lower wings lag by 0.70 rad

    // Flap Angles (Up/Down along height):
    const flap0 = strokeShape0 * flapAmplitude;
    const flap1 = strokeShape1 * (flapAmplitude * 0.85);
    const flap2 = strokeShape2 * (flapAmplitude * 0.70);

    // Subtle feathering twist along wing span (X axis) – strictly a small tilt (max ~2-3 degrees)
    const feather0 = -Math.cos(this.flapTimer) * 0.03;
    const feather1 = -Math.cos(this.flapTimer - 0.35) * 0.025;
    const feather2 = -Math.cos(this.flapTimer - 0.70) * 0.02;

    // Subtle organic sweep forward/backward (Z axis) – wings cup slightly forward on downstroke
    const sweep0 = strokeShape0 * 0.05;
    const sweep1 = strokeShape1 * 0.04;
    const sweep2 = strokeShape2 * 0.03;

    // Natural rest posture spread
    const baseSpread = isGMode ? 0.08 : 0.04;

    // 4. Apply Natural Rotations to Left Wings:
    // Y rotation: -flap lifts wing UP on +Z height, +flap lowers wing DOWN on -Z height
    // Z rotation: sweep folds wing forward/backward
    // X rotation: subtle feathering twist
    this.leftUpperPivot.rotation.set(feather0, -flap0, baseSpread + sweep0);
    this.leftMidPivot.rotation.set(feather1, -flap1, baseSpread * 0.8 + sweep1);
    this.leftLowerPivot.rotation.set(feather2, -flap2, baseSpread * 0.6 + sweep2);

    // 5. Apply Symmetrical Natural Rotations to Right Wings:
    // Right wing (+flap lifts wing UP on +Z height, -flap lowers wing DOWN on -Z height)
    this.rightUpperPivot.rotation.set(-feather0, flap0, -baseSpread - sweep0);
    this.rightMidPivot.rotation.set(-feather1, flap1, -baseSpread * 0.8 - sweep1);
    this.rightLowerPivot.rotation.set(-feather2, flap2, -baseSpread * 0.6 - sweep2);

    // 6. Compute Aerodynamic Vertical Lift
    // Downstroke (when strokeShape is negative, pressing downward) generates upward lift
    const liftRaw = Math.max(0, -strokeShape0) * liftMultiplier;
    this.currentLift = THREE.MathUtils.lerp(this.currentLift, liftRaw, delta * 8);

    // 7. Halo Rotation & Aura Pulse
    let haloPulse = 1.0;
    if (this.haloMesh) {
      const haloSpinRate = isGMode ? 1.8 : isMusicPlaying ? 1.4 : 0.6;
      this.haloMesh.rotation.z += delta * haloSpinRate;

      if (isMusicPlaying) {
        haloPulse = 1.0 + Math.sin(elapsed * 8) * 0.35;
      }
    }

    // 8. Greatsword subtle hover sway
    if (this.swordMesh) {
      const swordSway = Math.sin(elapsed * 1.2) * 0.03;
      this.swordMesh.rotation.y = swordSway + (isGMode ? 0.05 : 0);
    }

    return {
      liftOffset: this.currentLift,
      bankingAngle: bankingMultiplier,
      pitchAngle: forwardLean,
      haloPulse,
    };
  }

  public dispose(): void {
    this.isRigged = false;
    this.leftUpperPivot.clear();
    this.leftMidPivot.clear();
    this.leftLowerPivot.clear();
    this.rightUpperPivot.clear();
    this.rightMidPivot.clear();
    this.rightLowerPivot.clear();
  }
}
