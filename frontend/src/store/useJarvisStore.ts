/**
 * Zustand Store for BECKIE 3D HUD Telemetry, Reactive State, and Control Panels.
 */

import { create } from 'zustand';
import {
  GpuTelemetry,
  CpuTelemetry,
  BeckieState,
  TelemetryPoint,
  DialogueMode,
} from '../types/telemetry';
import { tauriBridge } from '../services/tauriBridge';

interface BeckieStoreState {
  // Telemetry values
  gpu: GpuTelemetry;
  cpu: CpuTelemetry;
  beckie: BeckieState;
  jarvis: BeckieState; // Alias for backward compatibility
  history: TelemetryPoint[];
  logs: string[];

  // Toggles and UI overlays
  settingsOpen: boolean;
  logsOpen: boolean;
  selectedMetric: 'gpu' | 'cpu' | 'vram' | null;
  emotionEnabled: boolean;
  neutralMode: boolean;
  reducedMotion: boolean;
  isPolling: boolean;

  // Calendar & Tasks
  calendarOpen: boolean;
  calendarEvents: import('../types/telemetry').CalendarEvent[];
  weekAgenda: import('../types/telemetry').WeekDayAgenda[];
  weekLoading: boolean;
  tasks: import('../types/telemetry').GoogleTask[];
  calendarLoading: boolean;
  setCalendarOpen: (open: boolean) => void;
  fetchCalendarEvents: () => Promise<void>;
  fetchWeekAgenda: () => Promise<void>;
  fetchTasks: () => Promise<void>;
  createCalendarEvent: (title: string, datetime_str?: string) => Promise<boolean>;
  createTask: (title: string, notes?: string) => Promise<boolean>;
  toggleTask: (task_id: string, currentCompleted: boolean) => Promise<boolean>;

  // Spotify
  spotifyOpen: boolean;
  spotify: import('../types/telemetry').SpotifyTrack;
  spotifyLoading: boolean;
  spotifyAuthUrl: string;
  playlists: import('../types/telemetry').SpotifyPlaylist[];
  preferences: import('../types/telemetry').SpotifyPreferences | null;
  setSpotifyOpen: (open: boolean) => void;
  fetchSpotify: () => Promise<void>;
  fetchSpotifyAuthUrl: () => Promise<string>;
  exchangeSpotifyCode: (codeOrUrl: string) => Promise<{ success: boolean; message: string }>;
  controlSpotify: (action: string, query?: string) => Promise<void>;
  playSpotifyTrack: (query: string) => Promise<boolean>;
  launchSpotifyApp: () => Promise<boolean>;
  fetchPlaylists: () => Promise<void>;
  fetchPreferences: () => Promise<void>;
  addCustomPlaylist: (name: string, uriOrUrl: string) => Promise<boolean>;



  // Actions
  pollTelemetry: () => Promise<void>;
  toggleMic: () => Promise<void>;
  toggleActivityTracking: () => Promise<void>;
  setMode: (mode: DialogueMode | string) => Promise<void>;
  toggleEmotionEnabled: () => Promise<void>;
  toggleNeutralMode: () => Promise<void>;
  toggleReducedMotion: () => void;
  emergencyPause: () => Promise<void>;
  resumeFromPause: () => Promise<void>;
  setSettingsOpen: (open: boolean) => void;
  setLogsOpen: (open: boolean) => void;
  setSelectedMetric: (metric: 'gpu' | 'cpu' | 'vram' | null) => void;
  refreshLogs: () => Promise<void>;
  clearEmotionHistory: () => Promise<void>;
  activeModeOverride: string | null;
  setActiveModeOverride: (mode: string | null) => void;
}

const initialBeckieState: BeckieState = {
  mic_enabled: true,
  activity_tracking_enabled: true,
  mic_status: 'LISTENING',
  tracking_status: 'MONITORING',
  current_mode: 'SUPPORTIVE',
  status: 'IDLE',
  emotion_state: {
    valence: 0.25,
    arousal: 0.15,
    dominance: 0.60,
    labels: ['focused', 'confident'],
    confidence: 0.92,
  },
  latency_ms: 342.0,
  model_name: 'QWEN3 8B Q4_K_M (LOCAL CONTEXT)',
};

export const useJarvisStore = create<BeckieStoreState>((set, get) => ({
  gpu: {
    name: 'NVIDIA RTX 5070 Ti',
    utilizationPct: 38,
    vramUsedMb: 4820,
    vramTotalMb: 16384,
    temperatureC: 52,
    fan: {
      rpm: null,
      percent: null,
      available: false,
      source: 'unavailable',
      unavailableReason: 'NVIDIA DRIVER DOES NOT EXPOSE RPM',
      sampledAt: new Date().toISOString(),
    },
    performanceMode: {
      mode: 'Prefer Maximum Performance',
      confidence: 'exact',
      source: 'nvml',
      rawValue: 'P0',
      unavailableReason: null,
      sampledAt: new Date().toISOString(),
    },
    powerWatts: 185.0,
    source: 'nvml',
  },
  cpu: {
    name: 'Intel Core Ultra 9 275HX',
    utilizationPct: 24,
    temperatureC: 46,
    frequencyMhz: 5200,
    fan: {
      rpm: null,
      percent: null,
      available: false,
      source: 'unavailable',
      unavailableReason: 'OEM SENSOR NOT EXPOSED',
      sampledAt: new Date().toISOString(),
    },
    performanceMode: {
      mode: 'Balanced',
      confidence: 'partial',
      source: 'windows_wmi',
      rawValue: 'Balanced',
      unavailableReason: 'FALLBACK TO WINDOWS ACTIVE POWER PLAN',
      sampledAt: new Date().toISOString(),
    },
    source: 'windows_wmi',
  },
  beckie: initialBeckieState,
  jarvis: initialBeckieState,
  history: [],
  logs: [],

  settingsOpen: false,
  logsOpen: false,
  selectedMetric: null,
  emotionEnabled: true,
  neutralMode: false,
  reducedMotion: false,
  isPolling: false,
  activeModeOverride: null,
  setActiveModeOverride: (mode: string | null) => set({ activeModeOverride: mode }),

  pollTelemetry: async () => {
    const currentBeckie = get().beckie;
    // When paused, stop polling telemetry updates
    if (currentBeckie.status === 'PAUSED') {
      return;
    }

    try {
      const [gpu, cpu, liveState] = await Promise.all([
        tauriBridge.getGpuMetrics(),
        tauriBridge.getCpuMetrics(),
        tauriBridge.getBeckieState(),
      ]);

      const now = Date.now();
      const timeStr = new Date(now).toTimeString().substring(0, 8);

      const newPoint: TelemetryPoint = {
        timestamp: now,
        timeStr,
        gpuUtil: gpu.utilizationPct,
        cpuUtil: cpu.utilizationPct,
        gpuTemp: gpu.temperatureC,
        cpuTemp: cpu.temperatureC,
        vramUsed: gpu.vramUsedMb,
      };

      const updatedBeckie: BeckieState = {
        ...currentBeckie,
        ...liveState,
        mic_status: !liveState.mic_enabled ? 'OFF' : 'LISTENING',
        tracking_status: !liveState.activity_tracking_enabled ? 'OFF' : 'MONITORING',
        status: 'IDLE',
      };

      set((state) => {
        const updatedHistory = [...state.history, newPoint].slice(-60);
        return {
          gpu,
          cpu,
          beckie: updatedBeckie,
          jarvis: updatedBeckie,
          history: updatedHistory,
        };
      });
    } catch (err) {
      console.error('[TelemetryStore] Polling error:', err);
    }
  },

  toggleMic: async () => {
    const next = !get().beckie.mic_enabled;
    const res = await tauriBridge.setMicEnabled(next);
    const updated: BeckieState = {
      ...get().beckie,
      mic_enabled: res,
      mic_status: res ? 'LISTENING' : 'OFF',
    };
    set({ beckie: updated, jarvis: updated });
  },

  toggleActivityTracking: async () => {
    const next = !get().beckie.activity_tracking_enabled;
    const res = await tauriBridge.setActivityTracking(next);
    const updated: BeckieState = {
      ...get().beckie,
      activity_tracking_enabled: res,
      tracking_status: res ? 'MONITORING' : 'OFF',
    };
    set({ beckie: updated, jarvis: updated });
  },

  setMode: async (mode: DialogueMode | string) => {
    const upperMode = mode.toUpperCase() as DialogueMode;
    const res = await tauriBridge.setCurrentMode(upperMode);
    const updated: BeckieState = {
      ...get().beckie,
      current_mode: res as DialogueMode,
    };
    set({ beckie: updated, jarvis: updated });
  },

  toggleEmotionEnabled: async () => {
    const next = !get().emotionEnabled;
    try {
      await fetch('http://127.0.0.1:8000/api/emotion/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ emotion_enabled: next }),
      });
    } catch (_) {}
    set({ emotionEnabled: next });
  },

  toggleNeutralMode: async () => {
    const next = !get().neutralMode;
    try {
      await fetch('http://127.0.0.1:8000/api/emotion/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ neutral_mode: next }),
      });
    } catch (_) {}
    const updatedMode: DialogueMode = next ? 'NEUTRAL' : 'SUPPORTIVE';
    const updated: BeckieState = {
      ...get().beckie,
      current_mode: updatedMode,
    };
    set({ neutralMode: next, beckie: updated, jarvis: updated });
  },

  toggleReducedMotion: () => {
    set((state) => ({ reducedMotion: !state.reducedMotion }));
  },

  emergencyPause: async () => {
    await tauriBridge.emergencyPause();
    const updated: BeckieState = {
      ...get().beckie,
      mic_enabled: false,
      activity_tracking_enabled: false,
      mic_status: 'PAUSED',
      tracking_status: 'PAUSED',
      status: 'PAUSED',
    };
    set({ beckie: updated, jarvis: updated });
  },

  resumeFromPause: async () => {
    await tauriBridge.setMicEnabled(true);
    await tauriBridge.setActivityTracking(true);
    const updated: BeckieState = {
      ...get().beckie,
      mic_enabled: true,
      activity_tracking_enabled: true,
      mic_status: 'LISTENING',
      tracking_status: 'MONITORING',
      status: 'IDLE',
    };
    set({ beckie: updated, jarvis: updated });
  },

  setSettingsOpen: (open) => set({ settingsOpen: open }),
  setLogsOpen: (open) => set({ logsOpen: open }),
  setSelectedMetric: (metric) => set({ selectedMetric: metric }),

  refreshLogs: async () => {
    try {
      const logs = await tauriBridge.getAuditLogs();
      set({ logs });
    } catch (err) {
      console.warn('Failed to load logs:', err);
    }
  },

  clearEmotionHistory: async () => {
    try {
      await fetch('http://127.0.0.1:8000/api/emotion/clear', { method: 'POST' });
    } catch (_) {}
  },

  // Calendar & Tasks Implementation
  calendarOpen: false,
  calendarEvents: [],
  weekAgenda: [],
  weekLoading: false,
  tasks: [],
  calendarLoading: false,
  setCalendarOpen: (open) => {
    set({ calendarOpen: open });
    if (open) {
      get().fetchCalendarEvents();
      get().fetchWeekAgenda();
      get().fetchTasks();
    }
  },
  fetchCalendarEvents: async () => {
    try {
      set({ calendarLoading: true });
      const res = await fetch('http://127.0.0.1:8000/api/calendar/events');
      if (res.ok) {
        const data = await res.json();
        set({ calendarEvents: data.events || [] });
      }
    } catch (e) {
      console.warn('Failed to fetch calendar events:', e);
    } finally {
      set({ calendarLoading: false });
    }
  },
  fetchWeekAgenda: async () => {
    try {
      set({ weekLoading: true });
      const res = await fetch('http://127.0.0.1:8000/api/calendar/week');
      if (res.ok) {
        const data = await res.json();
        set({ weekAgenda: data.week_agenda || [] });
      }
    } catch (e) {
      console.warn('Failed to fetch week agenda:', e);
    } finally {
      set({ weekLoading: false });
    }
  },
  fetchTasks: async () => {
    try {
      const res = await fetch('http://127.0.0.1:8000/api/tasks');
      if (res.ok) {
        const data = await res.json();
        set({ tasks: data.tasks || [] });
      }
    } catch (e) {
      console.warn('Failed to fetch tasks:', e);
    }
  },
  createCalendarEvent: async (title, datetime_str) => {
    try {
      const res = await fetch('http://127.0.0.1:8000/api/calendar/events', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, datetime_str }),
      });
      if (res.ok) {
        await get().fetchCalendarEvents();
        await get().fetchWeekAgenda();
        return true;
      }
    } catch (e) {
      console.error(e);
    }
    return false;
  },
  createTask: async (title, notes) => {
    try {
      const res = await fetch('http://127.0.0.1:8000/api/tasks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, notes }),
      });
      if (res.ok) {
        await get().fetchTasks();
        return true;
      }
    } catch (e) {
      console.error(e);
    }
    return false;
  },
  toggleTask: async (task_id, currentCompleted) => {
    try {
      set((state) => ({
        tasks: state.tasks.map((t) =>
          t.id === task_id ? { ...t, completed: !currentCompleted, status: !currentCompleted ? 'completed' : 'needsAction' } : t
        ),
      }));
      const res = await fetch('http://127.0.0.1:8000/api/tasks/toggle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task_id, completed: !currentCompleted }),
      });
      if (!res.ok) {
        await get().fetchTasks();
        return false;
      }
      return true;
    } catch (e) {
      await get().fetchTasks();
      return false;
    }
  },

  // Spotify Implementation
  spotifyOpen: false,
  spotify: {
    is_active: false,
    is_playing: false,
  },
  spotifyLoading: false,
  spotifyAuthUrl: '',
  setSpotifyOpen: (open) => {
    set({ spotifyOpen: open });
    if (open) {
      get().fetchSpotify();
      get().fetchSpotifyAuthUrl();
    }
  },
  fetchSpotifyAuthUrl: async () => {
    try {
      const res = await fetch('http://127.0.0.1:8000/api/spotify/auth-url');
      if (res.ok) {
        const data = await res.json();
        if (data.auth_url) {
          set({ spotifyAuthUrl: data.auth_url });
          return data.auth_url;
        }
      }
    } catch (e) {
      console.warn('Failed to fetch Spotify auth URL:', e);
    }
    return '';
  },
  exchangeSpotifyCode: async (codeOrUrl: string) => {
    try {
      const res = await fetch('http://127.0.0.1:8000/api/spotify/exchange', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code_or_url: codeOrUrl }),
      });
      const data = await res.json();
      if (data.success) {
        await get().fetchSpotify();
      }
      return { success: !!data.success, message: data.message || '' };
    } catch (e: any) {
      return { success: false, message: e.message || 'Network error' };
    }
  },
  fetchSpotify: async () => {
    try {
      const res = await fetch('http://127.0.0.1:8000/api/spotify/current');
      if (res.ok) {
        const data = await res.json();
        set({ spotify: data.track || { is_active: false, is_playing: false } });
      }
    } catch (e) {
      // offline fallback
    }
  },
  controlSpotify: async (action, query) => {
    try {
      await fetch('http://127.0.0.1:8000/api/spotify/control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, query }),
      });
      setTimeout(() => {
        get().fetchSpotify();
      }, 400);
    } catch (e) {
      console.error(e);
    }
  },
  playSpotifyTrack: async (query: string) => {
    try {
      const res = await fetch('http://127.0.0.1:8000/api/spotify/play', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query }),
      });
      setTimeout(() => {
        get().fetchSpotify();
      }, 600);
      return res.ok;
    } catch (e) {
      console.error(e);
      return false;
    }
  },
  launchSpotifyApp: async () => {
    try {
      const res = await fetch('http://127.0.0.1:8000/api/spotify/launch', {
        method: 'POST',
      });
      setTimeout(() => {
        get().fetchSpotify();
      }, 1000);
      return res.ok;
    } catch (e) {
      console.error(e);
      return false;
    }
  },
  playlists: [],
  preferences: null,
  fetchPlaylists: async () => {
    try {
      const res = await fetch('http://127.0.0.1:8000/api/spotify/playlists');
      if (res.ok) {
        const data = await res.json();
        set({ playlists: data.playlists || [] });
      }
    } catch (e) {
      console.warn('Failed to fetch playlists:', e);
    }
  },
  fetchPreferences: async () => {
    try {
      const res = await fetch('http://127.0.0.1:8000/api/spotify/preferences');
      if (res.ok) {
        const data = await res.json();
        set({ preferences: data.preferences || null });
      }
    } catch (e) {
      console.warn('Failed to fetch preferences:', e);
    }
  },
  addCustomPlaylist: async (name: string, uriOrUrl: string) => {
    try {
      const res = await fetch('http://127.0.0.1:8000/api/spotify/playlists', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, uri_or_url: uriOrUrl }),
      });
      if (res.ok) {
        await get().fetchPlaylists();
        return true;
      }
    } catch (e) {
      console.error(e);
    }
    return false;
  },
}));



export const useBeckieStore = useJarvisStore;

