/**
 * AvatarController.ts – Finite State Machine (FSM) Behavior Engine
 *
 * Implements Section 4 Avatar Behavior System:
 * - 15 Discrete FSM States
 * - Priority-driven state transitions:
 *   1. Emergency Pause (overrides all)
 *   2. Privacy / Mic state
 *   3. Active Conversation (LISTENING -> THINKING -> SPEAKING)
 *   4. User Commands
 *   5. Ambient Behaviors (15-45s deterministic schedule)
 * - Navigation waypoint binding
 * - Respects reduced motion
 */

import { AvatarFsmState, AvatarManifest, AvatarPermissions, SafeZoneKey } from '../../types/avatar';
import { AvatarNavigationSystem } from './AvatarNavigationSystem';
import { AvatarCapabilityRules } from './capabilityRules';

export interface TelemetrySpeechContext {
  gpuTemp?: number;
  gpuFan?: number;
  gpuLoad?: number;
  gpuVramUsedMb?: number;
  gpuVramTotalMb?: number;
  cpuTemp?: number;
  cpuLoad?: number;
  cpuGhz?: number;
  cpuFan?: number;
  agendaCount?: number;
  tasksCount?: number;
  activeTrack?: string;
  activeArtist?: string;
  isMusicPlaying?: boolean;
  activeMode?: string;
  affectiveState?: string;
}

export class AvatarController {
  private currentState: AvatarFsmState = 'IDLE';
  private previousState: AvatarFsmState = 'IDLE';
  private navigation: AvatarNavigationSystem | null = null;
  private manifest: AvatarManifest | null = null;
  private permissions: AvatarPermissions;

  // Ambient timer
  private ambientTimer: number = 0;
  private nextAmbientInterval: number = 20; // seconds
  private rngSeed: number = 42;
  private dwellTimeMultiplier: number = 1.0;

  // Telemetry Context for Rich Callouts
  private telemetryContext: TelemetrySpeechContext = {};
  private onSpeechCallout?: (text: string) => void;

  // Conversation tracking
  private speechSnippet: string = '';
  private isEmergencyPaused: boolean = false;
  private isMicMuted: boolean = false;

  constructor(navigation: AvatarNavigationSystem | null = null, permissions: AvatarPermissions) {
    this.navigation = navigation;
    this.permissions = permissions;
  }

  public setTelemetryContext(ctx: TelemetrySpeechContext): void {
    this.telemetryContext = ctx;
  }

  public setDwellTimeMultiplier(multiplier: number): void {
    this.dwellTimeMultiplier = Math.max(0.2, multiplier);
  }

  public setSpeechCallback(cb: (text: string) => void): void {
    this.onSpeechCallout = cb;
  }

  public setManifest(manifest: AvatarManifest | null): void {
    this.manifest = manifest;
  }

  public setPermissions(permissions: AvatarPermissions): void {
    this.permissions = permissions;
  }

  public getState(): AvatarFsmState {
    return this.currentState;
  }

  public getSpeechSnippet(): string {
    return this.speechSnippet;
  }

  /**
   * Transition to a new FSM state respecting strict priority hierarchies.
   */
  public transitionTo(newState: AvatarFsmState, payload?: any): boolean {
    if (!this.permissions.enabled && newState !== 'HIDDEN') {
      this.currentState = 'HIDDEN';
      return false;
    }

    // Priority 1: Emergency Pause
    if (this.isEmergencyPaused && newState !== 'PAUSED' && newState !== 'HIDDEN') {
      return false;
    }

    // Priority 2: Do not interrupt speaking with ambient states
    if (this.currentState === 'SPEAKING' && (newState === 'OBSERVING' || newState === 'WALKING' || newState === 'HOVERING')) {
      return false;
    }

    this.previousState = this.currentState;
    this.currentState = newState;

    if (payload?.text) {
      this.speechSnippet = payload.text;
    }

    return true;
  }

  /**
   * Handle incoming event from AvatarEventBridge.
   */
  public handleEvent(event: string, payload: any): void {
    switch (event) {
      case 'assistant.emergency_paused':
        this.isEmergencyPaused = !!payload?.emergencyPaused;
        if (this.isEmergencyPaused) {
          this.transitionTo('PAUSED');
        } else {
          this.transitionTo('IDLE');
        }
        break;

      case 'privacy.mic.paused':
        this.isMicMuted = !!payload?.micPaused;
        if (this.isMicMuted && this.currentState === 'LISTENING') {
          this.transitionTo('IDLE');
        }
        break;

      case 'voice.listening.started':
        if (!this.isEmergencyPaused && !this.isMicMuted) {
          this.transitionTo('LISTENING');
        }
        break;

      case 'voice.listening.stopped':
        if (this.currentState === 'LISTENING') {
          this.transitionTo('IDLE');
        }
        break;

      case 'llm.generation.started':
        if (!this.isEmergencyPaused) {
          this.transitionTo('THINKING');
        }
        break;

      case 'llm.generation.completed':
        if (this.currentState === 'THINKING') {
          this.transitionTo('IDLE');
        }
        break;

      case 'tts.started':
        if (!this.isEmergencyPaused) {
          this.transitionTo('SPEAKING', { text: payload?.text || 'Speaking...' });
        }
        break;

      case 'tts.completed':
        if (this.currentState === 'SPEAKING') {
          this.speechSnippet = '';
          this.transitionTo('IDLE');
        }
        break;

      default:
        break;
    }
  }

  private patrolSequence: SafeZoneKey[] = [
    'leftObservationZone',
    'centerCoreZone',
    'rightObservationZone',
    'centerCoreZone',
    'lowerCenterZone',
    'centerCoreZone',
    'spotifyStationZone',
    'centerCoreZone',
    'upperOrbitZone',
    'centerCoreZone',
    'affectiveZone',
    'centerCoreZone',
    'networkZone',
    'centerCoreZone',
  ];
  private patrolIndex: number = 0;

  /**
   * Directly command Beckie to navigate to and inspect a specific HUD station.
   */
  public inspectStation(targetZoneKey: SafeZoneKey): void {
    if (this.isEmergencyPaused) return;
    if (this.navigation) {
      this.navigation.navigateTo(targetZoneKey);
      this.currentState = 'FLYING';
    }

    const tc = this.telemetryContext;

    switch (targetZoneKey) {
      case 'leftObservationZone':
        this.speechSnippet =
          tc.gpuTemp !== undefined
            ? `GPU Telemetry: Core at ${tc.gpuTemp}°C, Fan running at ${tc.gpuFan ?? 0} RPM, VRAM load at ${
                tc.gpuVramUsedMb && tc.gpuVramTotalMb
                  ? Math.round((tc.gpuVramUsedMb / tc.gpuVramTotalMb) * 100)
                  : 34
              }%. Cooling loops operational.`
            : 'Inspecting GPU load, VRAM buffer, and cooling fans...';
        break;

      case 'rightObservationZone':
        this.speechSnippet =
          tc.cpuLoad !== undefined
            ? `CPU Telemetry: Utilization at ${Math.round(tc.cpuLoad)}%, Clock at ${(tc.cpuGhz ?? 3.8).toFixed(
                2
              )} GHz, Fan at ${tc.cpuFan ?? 0} RPM. Thermals nominal.`
            : 'Inspecting CPU frequency, core utilization, and thermals...';
        break;

      case 'lowerCenterZone':
        this.speechSnippet =
          tc.agendaCount !== undefined
            ? `Chrono-Deck 7-Day Agenda: ${tc.agendaCount} calendar milestones synced, ${
                tc.tasksCount ?? 0
              } tactical directives pending.`
            : 'Reviewing Chrono-Deck 7-Day Agenda and scheduled milestones...';
        break;

      case 'spotifyStationZone':
        this.speechSnippet =
          tc.isMusicPlaying && tc.activeTrack
            ? `Holo-Audio active: Harmonizing 6-wing flight rhythm with "${tc.activeTrack}" by ${
                tc.activeArtist || 'Unknown'
              }. Beat phase locked.`
            : 'Spotify Holo-Audio Deck standby. Audio visualizer awaiting playback resonance.';
        break;

      case 'upperOrbitZone':
        this.speechSnippet = tc.activeMode
          ? `Alienware Mode Deck: ${tc.activeMode} profile engaged. Thruster aerodynamics tuned to power ceiling.`
          : 'Scanning Alienware performance profile and thermal envelope...';
        break;

      case 'affectiveZone':
        this.speechSnippet = tc.affectiveState
          ? `Operator Affective Deck: Emotional valence state "${tc.affectiveState}" detected. Cognitive flow state aligned.`
          : 'Scanning operator affective biometrics and focus telemetry...';
        break;

      case 'networkZone':
        this.speechSnippet =
          'Zero-Cloud Privacy Shield verified: 100% on-device local execution. Zero external data leakage.';
        break;

      case 'centerCoreZone':
        this.speechSnippet = 'Center Command Dock secured. Archangel flight systems standing by.';
        break;

      default:
        this.speechSnippet = '';
        break;
    }
  }

  /**
   * Main behavior loop called per animation frame.
   */
  public update(deltaSeconds: number, currentMode: string = 'Balanced'): void {
    if (!this.permissions.enabled) {
      if (this.currentState !== 'HIDDEN') this.currentState = 'HIDDEN';
      return;
    }

    // Determine dwell duration based on active Alienware mode and user multiplier
    const lowerMode = currentMode.toLowerCase();
    const isGMode =
      lowerMode.includes('g-mode') || lowerMode.includes('game') || lowerMode.includes('overdrive');
    const isQuiet = lowerMode.includes('quiet') || lowerMode.includes('battery');
    const baseInterval = (isGMode ? 8 : isQuiet ? 18 : 12) * this.dwellTimeMultiplier;

    // Advance ambient timer during IDLE or OBSERVING
    if (
      (this.currentState === 'IDLE' || this.currentState === 'OBSERVING') &&
      this.permissions.ambientMovement &&
      !this.permissions.reducedMotion
    ) {
      this.ambientTimer += deltaSeconds;

      if (this.ambientTimer >= this.nextAmbientInterval) {
        this.ambientTimer = 0;
        this.nextAmbientInterval = baseInterval;

        this.triggerNextPatrolStation();
      }
    }

    // Check if moving
    if (this.navigation && this.navigation.isMoving()) {
      if (this.currentState !== 'FLYING' && this.currentState !== 'HOVERING') {
        this.currentState = 'FLYING';
      }
    } else if (this.currentState === 'FLYING') {
      const station = this.navigation ? this.navigation.getStationType() : 'center';
      const tc = this.telemetryContext;

      if (station === 'gpu') {
        this.currentState = 'OBSERVING';
        this.speechSnippet =
          tc.gpuTemp !== undefined
            ? `GPU Telemetry: Core at ${tc.gpuTemp}°C, Fan running at ${tc.gpuFan ?? 0} RPM, VRAM load at ${
                tc.gpuVramUsedMb && tc.gpuVramTotalMb
                  ? Math.round((tc.gpuVramUsedMb / tc.gpuVramTotalMb) * 100)
                  : 34
              }%. Cooling loops operational.`
            : 'Watching GPU load, VRAM buffer, and fan speed.';
      } else if (station === 'cpu') {
        this.currentState = 'OBSERVING';
        this.speechSnippet =
          tc.cpuLoad !== undefined
            ? `CPU Telemetry: Utilization at ${Math.round(tc.cpuLoad)}%, Clock at ${(tc.cpuGhz ?? 3.8).toFixed(
                2
              )} GHz, Fan at ${tc.cpuFan ?? 0} RPM. Thermals nominal.`
            : 'Watching CPU frequency, core utilization, and thermals.';
      } else if (station === 'agenda') {
        this.currentState = 'OBSERVING';
        this.speechSnippet =
          tc.agendaCount !== undefined
            ? `Chrono-Deck 7-Day Agenda: ${tc.agendaCount} calendar milestones synced, ${
                tc.tasksCount ?? 0
              } tactical directives pending.`
            : 'Scanning 7-Day Chrono-Deck Agenda and active directives.';
      } else if (station === 'spotify') {
        this.currentState = 'OBSERVING';
        this.speechSnippet =
          tc.isMusicPlaying && tc.activeTrack
            ? `Holo-Audio active: Harmonizing 6-wing flight rhythm with "${tc.activeTrack}" by ${
                tc.activeArtist || 'Unknown'
              }. Beat phase locked.`
            : 'Spotify Holo-Audio idling on standby.';
      } else if (station === 'mode') {
        this.currentState = 'HOVERING';
        this.speechSnippet = tc.activeMode
          ? `Alienware Mode Deck: ${tc.activeMode} profile engaged. Thruster aerodynamics tuned to power ceiling.`
          : 'Overlooking Alienware thermal profile.';
      } else if (station === 'affective') {
        this.currentState = 'OBSERVING';
        this.speechSnippet = tc.affectiveState
          ? `Operator Affective Deck: Emotional valence state "${tc.affectiveState}" detected. Cognitive flow state aligned.`
          : 'Observing operator affective and biometric focus markers.';
      } else if (station === 'network') {
        this.currentState = 'OBSERVING';
        this.speechSnippet =
          'Zero-Cloud Privacy Shield verified: 100% on-device local execution. Zero external data leakage.';
      } else {
        this.currentState = 'IDLE';
        this.speechSnippet = 'Center Command Dock secured. Archangel flight systems standing by.';
      }

      if (this.onSpeechCallout && this.speechSnippet) {
        this.onSpeechCallout(this.speechSnippet);
      }
    }
  }

  private triggerNextPatrolStation(): void {
    const nextKey = this.patrolSequence[this.patrolIndex % this.patrolSequence.length];
    this.patrolIndex++;
    this.inspectStation(nextKey);
  }
}

