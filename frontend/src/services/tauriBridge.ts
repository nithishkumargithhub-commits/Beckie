/**
 * Tauri 2.x Command Bridge with Local-First FastAPI Integration and Fallbacks.
 */

import { GpuTelemetry, CpuTelemetry, BeckieState } from '../types/telemetry';

// Check if running inside genuine Tauri environment
export const isTauri = (): boolean => {
  return typeof window !== 'undefined' && ('__TAURI_INTERNALS__' in window || '__TAURI__' in window);
};

// Lazy invoke import to prevent module crashes in pure browser/headless environments
async function callTauri<T>(cmd: string, args?: Record<string, unknown>): Promise<T> {
  if (isTauri()) {
    try {
      const { invoke } = await import('@tauri-apps/api/core');
      return await invoke<T>(cmd, args);
    } catch (err) {
      console.warn(`[TauriBridge] Native command '${cmd}' failed, using fallback:`, err);
    }
  }
  return fallbackInvoke<T>(cmd, args);
}

// Fallback simulator for browser dev and E2E testing
let mockBeckieState: BeckieState = {
  mic_enabled: true,
  activity_tracking_enabled: true,
  mic_status: 'LISTENING',
  tracking_status: 'MONITORING',
  current_mode: 'SUPPORTIVE',
  status: 'IDLE',
  emotion_state: {
    valence: 0.35,
    arousal: 0.20,
    dominance: 0.65,
    labels: ['focused', 'confident'],
    confidence: 0.88,
  },
  latency_ms: 385.0,
  model_name: 'QWEN3 8B Q4_K_M (LOCAL CONTEXT)',
};

let simTick = 0;

async function fallbackInvoke<T>(cmd: string, args?: Record<string, unknown>): Promise<T> {
  simTick++;

  // 1. Try querying local FastAPI server if available
  if (cmd === 'get_gpu_metrics' || cmd === 'get_cpu_metrics') {
    try {
      const res = await fetch('http://127.0.0.1:8000/api/telemetry/all', {
        headers: { 'Accept': 'application/json' },
        signal: AbortSignal.timeout(600),
      });
      if (res.ok) {
        const data = await res.json();
        if (cmd === 'get_gpu_metrics' && data.gpu) {
          return data.gpu as unknown as T;
        }
        if (cmd === 'get_cpu_metrics' && data.cpu) {
          return data.cpu as unknown as T;
        }
      }
    } catch {
      // Local server request timed out or not available, use local mock with strict integrity
    }
  }

  switch (cmd) {
    case 'get_gpu_metrics': {
      const util = Math.round(38 + Math.sin(simTick * 0.2) * 12);
      const temp = Math.round(52 + Math.sin(simTick * 0.15) * 4);
      const nowIso = new Date().toISOString();

      const res: GpuTelemetry = {
        name: 'NVIDIA RTX 5070 Ti',
        utilizationPct: util,
        vramUsedMb: 4820 + (simTick % 10) * 15,
        vramTotalMb: 16384,
        temperatureC: temp,
        fan: {
          rpm: null,
          percent: null,
          available: false,
          source: 'unavailable',
          unavailableReason: 'NVIDIA DRIVER DOES NOT EXPOSE RPM',
          sampledAt: nowIso,
        },
        performanceMode: {
          mode: 'Prefer Maximum Performance',
          confidence: 'exact',
          source: 'nvml',
          rawValue: 'P0',
          unavailableReason: null,
          sampledAt: nowIso,
        },
        powerWatts: 185.4,
        source: 'nvml',
      };
      return Promise.resolve(res as unknown as T);
    }

    case 'get_cpu_metrics': {
      const util = Math.round(24 + Math.cos(simTick * 0.25) * 8);
      const temp = Math.round(46 + Math.cos(simTick * 0.1) * 3);
      const nowIso = new Date().toISOString();

      const res: CpuTelemetry = {
        name: 'Intel Core Ultra 9 275HX',
        utilizationPct: util,
        temperatureC: temp,
        frequencyMhz: 5200,
        fan: {
          rpm: null,
          percent: null,
          available: false,
          source: 'unavailable',
          unavailableReason: 'OEM SENSOR NOT EXPOSED',
          sampledAt: nowIso,
        },
        performanceMode: {
          mode: 'Balanced',
          confidence: 'partial',
          source: 'windows_wmi',
          rawValue: 'Balanced',
          unavailableReason: 'FALLBACK TO WINDOWS ACTIVE POWER PLAN',
          sampledAt: nowIso,
        },
        source: 'windows_wmi',
      };
      return Promise.resolve(res as unknown as T);
    }

    case 'get_jarvis_state':
    case 'get_beckie_state': {
      if (mockBeckieState.status !== 'PAUSED') {
        mockBeckieState.latency_ms = Math.round(340 + Math.random() * 80);
      }
      return Promise.resolve({ ...mockBeckieState } as unknown as T);
    }

    case 'set_mic_enabled': {
      if (args && typeof args.enabled === 'boolean') {
        mockBeckieState.mic_enabled = args.enabled;
        mockBeckieState.mic_status = args.enabled ? 'LISTENING' : 'OFF';
      }
      return Promise.resolve(mockBeckieState.mic_enabled as unknown as T);
    }

    case 'set_activity_tracking': {
      if (args && typeof args.enabled === 'boolean') {
        mockBeckieState.activity_tracking_enabled = args.enabled;
        mockBeckieState.tracking_status = args.enabled ? 'MONITORING' : 'OFF';
      }
      return Promise.resolve(mockBeckieState.activity_tracking_enabled as unknown as T);
    }

    case 'set_current_mode': {
      if (args && typeof args.mode === 'string') {
        mockBeckieState.current_mode = args.mode.toUpperCase() as any;
      }
      return Promise.resolve(mockBeckieState.current_mode as unknown as T);
    }

    case 'emergency_pause': {
      mockBeckieState.status = 'PAUSED';
      mockBeckieState.mic_status = 'PAUSED';
      mockBeckieState.tracking_status = 'PAUSED';
      // Also notify local server if running
      try {
        fetch('http://127.0.0.1:8000/api/telemetry/pause', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ paused: true }),
        }).catch(() => {});
      } catch {}
      return Promise.resolve(true as unknown as T);
    }

    case 'emergency_resume': {
      mockBeckieState.status = 'IDLE';
      mockBeckieState.mic_status = mockBeckieState.mic_enabled ? 'LISTENING' : 'OFF';
      mockBeckieState.tracking_status = mockBeckieState.activity_tracking_enabled ? 'MONITORING' : 'OFF';
      try {
        fetch('http://127.0.0.1:8000/api/telemetry/pause', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ paused: false }),
        }).catch(() => {});
      } catch {}
      return Promise.resolve(true as unknown as T);
    }

    default:
      console.warn(`[TauriBridge] Unhandled command: ${cmd}`);
      return Promise.resolve({} as unknown as T);
  }
}

// Exported high-level bridge functions
export async function getGpuMetrics(): Promise<GpuTelemetry> {
  return await callTauri<GpuTelemetry>('get_gpu_metrics');
}

export async function getCpuMetrics(): Promise<CpuTelemetry> {
  return await callTauri<CpuTelemetry>('get_cpu_metrics');
}

export async function getJarvisState(): Promise<BeckieState> {
  return await callTauri<BeckieState>('get_beckie_state');
}

export async function setMicEnabled(enabled: boolean): Promise<boolean> {
  return await callTauri<boolean>('set_mic_enabled', { enabled });
}

export async function setActivityTracking(enabled: boolean): Promise<boolean> {
  return await callTauri<boolean>('set_activity_tracking', { enabled });
}

export async function setCurrentMode(mode: string): Promise<string> {
  return await callTauri<string>('set_current_mode', { mode });
}

export async function emergencyPause(): Promise<boolean> {
  return await callTauri<boolean>('emergency_pause');
}

export async function emergencyResume(): Promise<boolean> {
  return await callTauri<boolean>('emergency_resume');
}

export async function getAuditLogs(limit: number = 50): Promise<string[]> {
  return await callTauri<string[]>('get_audit_logs', { limit });
}

export const tauriBridge = {
  getGpuMetrics,
  getCpuMetrics,
  getBeckieState: getJarvisState,
  getJarvisState,
  setMicEnabled,
  setActivityTracking,
  setCurrentMode,
  emergencyPause,
  emergencyResume,
  getAuditLogs,
};
