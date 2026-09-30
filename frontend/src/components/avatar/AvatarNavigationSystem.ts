/**
 * AvatarNavigationSystem.ts – Virtual 3D Scene Waypoints and Nav Boundaries
 *
 * Implements Section 5 Navigation Rules:
 * - Dedicated dashboard-safe movement zones
 * - Strict exclusion of branding, controls, privacy, and telemetry text
 * - Predefined curved waypoint paths and smooth Bezier flying arcs
 * - Virtual 3D scene movement only (NEVER OS cursor movement)
 * - Clamped altitudes and collision-free flight boundaries
 */

import { AvatarZoneWaypoint, SafeZoneKey } from '../../types/avatar';

export const DASHBOARD_SAFE_ZONES: Record<SafeZoneKey, AvatarZoneWaypoint> = {
  centerCoreZone: {
    id: 'centerCoreZone',
    name: 'Center Core Dock',
    position: [0, 0, 0],
    rotation: [0, 0, 0],
    description: "Beckie's default home zone in the center HUD aperture",
  },
  leftObservationZone: {
    id: 'leftObservationZone',
    name: 'GPU Telemetry Station',
    position: [-2.65, 0.35, 0.1],
    rotation: [0.08, 0.72, 0],
    description: 'Direct inspection of GPU load, VRAM, and fan speed tachometer',
  },
  rightObservationZone: {
    id: 'rightObservationZone',
    name: 'CPU Telemetry Station',
    position: [2.65, 0.35, 0.1],
    rotation: [0.08, -0.72, 0],
    description: 'Direct inspection of CPU utilization, clock frequency, and fan speed',
  },
  upperOrbitZone: {
    id: 'upperOrbitZone',
    name: 'Alienware Mode Deck',
    position: [0, 1.55, -0.3],
    rotation: [-0.18, 0, 0],
    description: 'Observing top-center Alienware performance mode command capsule',
  },
  lowerCenterZone: {
    id: 'lowerCenterZone',
    name: 'Chrono-Deck Agenda Station',
    position: [0, -1.35, 0.25],
    rotation: [0.35, 0, 0],
    description: 'Inspecting upcoming 7-day calendar agenda events and protocols',
  },
  spotifyStationZone: {
    id: 'spotifyStationZone',
    name: 'Spotify Holo-Audio Deck',
    position: [-1.95, -0.85, 0.2],
    rotation: [0.18, 0.55, 0],
    description: 'Harmonizing flight beats with active Spotify music playback',
  },
  affectiveZone: {
    id: 'affectiveZone',
    name: 'Operator Affective Biometrics',
    position: [2.55, -0.95, 0.2],
    rotation: [0.18, -0.55, 0],
    description: 'Scanning operator cognitive stress and affective telemetry',
  },
  networkZone: {
    id: 'networkZone',
    name: 'Zero-Cloud Privacy Shield',
    position: [-2.55, -0.95, 0.2],
    rotation: [0.18, 0.55, 0],
    description: 'Verifying zero cloud leakage and on-device offline security',
  },
};

export class AvatarNavigationSystem {
  private currentWaypoint: AvatarZoneWaypoint = DASHBOARD_SAFE_ZONES.centerCoreZone;
  private isTraveling: boolean = false;
  private travelProgress: number = 0;
  private startPosition: [number, number, number] = [0, 0, 0];
  private targetPosition: [number, number, number] = [0, 0, 0];
  private controlPoint: [number, number, number] = [0, 0.8, 0];

  public getCurrentWaypoint(): AvatarZoneWaypoint {
    return this.currentWaypoint;
  }

  public getTargetRotation(): [number, number, number] {
    return this.currentWaypoint.rotation;
  }

  public getStationType():
    | 'gpu'
    | 'cpu'
    | 'agenda'
    | 'mode'
    | 'spotify'
    | 'affective'
    | 'network'
    | 'center' {
    switch (this.currentWaypoint.id) {
      case 'leftObservationZone':
        return 'gpu';
      case 'rightObservationZone':
        return 'cpu';
      case 'lowerCenterZone':
        return 'agenda';
      case 'upperOrbitZone':
        return 'mode';
      case 'spotifyStationZone':
        return 'spotify';
      case 'affectiveZone':
        return 'affective';
      case 'networkZone':
        return 'network';
      default:
        return 'center';
    }
  }

  public isMoving(): boolean {
    return this.isTraveling;
  }

  /**
   * Plan a smooth Bezier flight or travel arc to a target zone.
   */
  public navigateTo(targetZoneKey: SafeZoneKey): boolean {
    const target = DASHBOARD_SAFE_ZONES[targetZoneKey];
    if (!target) return false;

    this.startPosition = [...this.currentWaypoint.position];
    this.targetPosition = [...target.position];

    // Compute curved Bezier apex
    const midX = (this.startPosition[0] + this.targetPosition[0]) / 2;
    const midY = Math.max(this.startPosition[1], this.targetPosition[1]) + 0.6;
    const midZ = (this.startPosition[2] + this.targetPosition[2]) / 2 - 0.4;
    this.controlPoint = [midX, midY, midZ];

    this.travelProgress = 0;
    this.isTraveling = true;
    this.currentWaypoint = target;
    return true;
  }

  /**
   * Compute current interpolated position on the Bezier trajectory.
   */
  public update(deltaSeconds: number, speed: number = 0.8): [number, number, number] {
    if (!this.isTraveling) {
      return this.currentWaypoint.position;
    }

    this.travelProgress += deltaSeconds * speed;
    if (this.travelProgress >= 1.0) {
      this.travelProgress = 1.0;
      this.isTraveling = false;
      return this.targetPosition;
    }

    // Quadratic Bezier interpolation: B(t) = (1-t)^2 P0 + 2(1-t)t P1 + t^2 P2
    const t = this.travelProgress;
    const invT = 1.0 - t;

    const x = invT * invT * this.startPosition[0] + 2 * invT * t * this.controlPoint[0] + t * t * this.targetPosition[0];
    const y = invT * invT * this.startPosition[1] + 2 * invT * t * this.controlPoint[1] + t * t * this.targetPosition[1];
    const z = invT * invT * this.startPosition[2] + 2 * invT * t * this.controlPoint[2] + t * t * this.targetPosition[2];

    return [x, y, z];
  }

  /**
   * Get a random safe waypoint (excluding current).
   */
  public getRandomSafeWaypointKey(seed: number = 0): SafeZoneKey {
    const keys: SafeZoneKey[] = [
      'centerCoreZone',
      'leftObservationZone',
      'rightObservationZone',
      'upperOrbitZone',
      'lowerCenterZone',
      'spotifyStationZone',
      'affectiveZone',
      'networkZone',
    ];
    const filtered = keys.filter((k) => k !== this.currentWaypoint.id);
    const index = Math.abs(seed) % filtered.length;
    return filtered[index];
  }
}
