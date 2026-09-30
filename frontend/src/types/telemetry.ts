/**
 * Type-safe interfaces for BECKIE 3D HUD Telemetry and Assistant State.
 *
 * Implements strict local-first contracts:
 * - TelemetrySource
 * - FanMetric
 * - PerformanceModeMetric
 * - GpuTelemetry
 * - CpuTelemetry
 */

export type TelemetrySource =
  | "nvml"
  | "libre_hardware_monitor"
  | "windows_wmi"
  | "oem_adapter"
  | "unavailable";

export interface FanMetric {
  rpm: number | null;
  percent: number | null;
  available: boolean;
  source: TelemetrySource;
  unavailableReason: string | null;
  sampledAt: string;
}

export interface PerformanceModeMetric {
  mode: string | null;
  confidence: "exact" | "partial" | "unknown";
  source: TelemetrySource;
  rawValue: string | null;
  unavailableReason: string | null;
  sampledAt: string;
}

export interface GpuTelemetry {
  name: string | null;
  utilizationPct: number | null;
  vramUsedMb: number | null;
  vramTotalMb: number | null;
  temperatureC: number | null;
  fan: FanMetric;
  performanceMode: PerformanceModeMetric;
  powerWatts: number | null;
  source: TelemetrySource;
}

export interface CpuTelemetry {
  name: string | null;
  utilizationPct: number | null;
  temperatureC: number | null;
  frequencyMhz: number | null;
  fan: FanMetric;
  performanceMode: PerformanceModeMetric;
  source: TelemetrySource;
}

export interface HolographicFanProps {
  label: string;
  bladeCount: number;
  rpm: number | null;
  percent: number | null;
  utilizationPct: number | null;
  temperatureC: number | null;
  performanceMode: string | null;
  isAvailable: boolean;
  unavailableReason: string | null;
  colorProfile: "gpu" | "cpu";
  // Optional extension props for interaction & accessibility
  isPaused?: boolean;
  reducedMotion?: boolean;
  onClick?: () => void;
}

export type BeckieCoreStatus =
  | 'IDLE'
  | 'LISTENING'
  | 'THINKING'
  | 'SPEAKING'
  | 'PAUSED'
  | 'ERROR';

export type DialogueMode = 'NEUTRAL' | 'SUPPORTIVE' | 'DIRECT' | 'CHALLENGE';

export type MicPrivacyStatus = 'OFF' | 'LISTENING' | 'PAUSED';

export type ActivityTrackingStatus = 'OFF' | 'MONITORING' | 'PAUSED';

export interface EmotionStateDto {
  valence: number;
  arousal: number;
  dominance: number;
  labels: string[];
  confidence: number;
}

export interface BeckieState {
  mic_enabled: boolean;
  activity_tracking_enabled: boolean;
  mic_status: MicPrivacyStatus;
  tracking_status: ActivityTrackingStatus;
  current_mode: DialogueMode;
  status: BeckieCoreStatus;
  emotion_state: EmotionStateDto | null;
  latency_ms: number | null;
  model_name: string;
}

export interface TelemetryPoint {
  timestamp: number;
  timeStr: string;
  gpuUtil: number | null;
  cpuUtil: number | null;
  gpuTemp: number | null;
  cpuTemp: number | null;
  vramUsed: number | null;
}

// Backward-compatibility aliases for legacy callers
export type GpuMetrics = GpuTelemetry;
export type CpuMetrics = CpuTelemetry;
export type JarvisState = BeckieState;

export interface CalendarEvent {
  id: string;
  summary: string;
  start: string;
  end?: string;
  location?: string;
  htmlLink?: string;
}

export interface GoogleTask {
  id: string;
  title: string;
  notes?: string;
  status: 'needsAction' | 'completed';
  completed: boolean;
  due?: string;
}

export interface SpotifyTrack {
  is_active: boolean;
  is_playing: boolean;
  title?: string;
  artist?: string;
  album?: string;
  album_art?: string;
  progress_ms?: number;
  duration_ms?: number;
  requires_auth?: boolean;
  connected?: boolean;
  error?: string;
}


export interface WeekDayEvent {
  id?: string;
  summary: string;
  start?: string;
  end?: string;
  time_str?: string;
  location?: string;
  htmlLink?: string;
}

export interface WeekDayAgenda {
  date: string;
  day_name: string;
  day_short: string;
  day_num: string;
  month_short: string;
  display_date: string;
  is_today: boolean;
  events: WeekDayEvent[];
}

export interface SpotifyPlaylist {
  id: string;
  name: string;
  curator: string;
  uri: string;
  track_count: number;
  tag: string;
  image?: string;
}

export interface SpotifyTopArtist {
  name: string;
  genres: string[];
  image?: string;
  uri?: string;
}

export interface SpotifyTopTrack {
  name: string;
  artist: string;
  uri?: string;
  album?: string;
}

export interface SpotifyRecentTrack {
  name: string;
  artist: string;
  uri?: string;
  played_at?: string;
}

export interface SpotifyPreferences {
  favorite_genres: string[];
  visualizer_style: string;
  sound_profile: string;
  top_artists?: SpotifyTopArtist[];
  top_tracks?: SpotifyTopTrack[];
  recently_played?: SpotifyRecentTrack[];
  needs_scope_grant?: boolean;
}



