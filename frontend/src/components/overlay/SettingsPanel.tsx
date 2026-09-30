/**
 * SettingsPanel.tsx – Tactical Control & Privacy Settings Drawer
 *
 * Implements:
 * - Mic privacy toggle
 * - Activity tracking toggle
 * - Emotion understanding toggle
 * - Neutral mode toggle
 * - Reduced motion accessibility toggle
 * - Dialogue mode selector (NEUTRAL / SUPPORTIVE / DIRECT / CHALLENGE)
 * - Emergency Pause button (stops mic, tracking, integrations)
 */

import React from 'react';
import { useJarvisStore } from '../../store/useJarvisStore';
import {
  X,
  Mic,
  MicOff,
  Shield,
  ShieldOff,
  Heart,
  EyeOff,
  AlertOctagon,
  Trash2,
  Sliders,
  Play,
  Sparkles,
} from 'lucide-react';
import { DialogueMode } from '../../types/telemetry';

export const SettingsPanel: React.FC = () => {
  const {
    settingsOpen,
    setSettingsOpen,
    beckie,
    toggleMic,
    toggleActivityTracking,
    setMode,
    emotionEnabled,
    toggleEmotionEnabled,
    neutralMode,
    toggleNeutralMode,
    reducedMotion,
    toggleReducedMotion,
    clearEmotionHistory,
    emergencyPause,
    resumeFromPause,
  } = useJarvisStore();

  if (!settingsOpen) return null;

  const isPaused = beckie.status === 'PAUSED';

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      {/* Backdrop */}
      <div
        onClick={() => setSettingsOpen(false)}
        className="absolute inset-0 bg-black/70 backdrop-blur-xs animate-in fade-in"
      />

      {/* Drawer */}
      <div className="relative w-full max-w-md h-full hud-panel border-l border-[#1677FF]/40 p-6 flex flex-col justify-between overflow-y-auto animate-in slide-in-from-right duration-300 select-none">
        <div>
          {/* Drawer Header */}
          <div className="flex justify-between items-center pb-4 border-b border-[#1677FF]/30 mb-5">
            <div>
              <h2 className="hud-title text-base font-extrabold text-[#00B8FF] text-glow">
                TACTICAL SETTINGS
              </h2>
              <p className="text-[10px] text-[#7AA8FF] mono-val uppercase tracking-wider">
                BECKIE CORE SOVEREIGN CONTROLS
              </p>
            </div>
            <button
              onClick={() => setSettingsOpen(false)}
              className="p-1.5 rounded-lg border border-[#1677FF]/40 hover:bg-[#1677FF]/20 text-[#00B8FF] transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Privacy & Hardware Toggles */}
          <div className="space-y-3.5">
            {/* Microphone Privacy */}
            <div className="p-3 rounded-xl bg-[#030716]/80 border border-[#1677FF]/30 flex items-center justify-between">
              <div className="flex items-center gap-3">
                {beckie.mic_enabled ? (
                  <Mic className="w-5 h-5 text-[#00B8FF]" />
                ) : (
                  <MicOff className="w-5 h-5 text-[#FF314F]" />
                )}
                <div>
                  <div className="font-semibold text-xs text-[#D7EEFF]">Microphone Privacy</div>
                  <div className="text-[10px] text-[#6A92BA]">
                    {beckie.mic_enabled ? 'Voice listener active' : 'Microphone hardware muted'}
                  </div>
                </div>
              </div>
              <button
                onClick={toggleMic}
                className={`px-3 py-1 rounded-lg text-xs font-bold mono-val transition-all ${
                  beckie.mic_enabled
                    ? 'bg-[#1677FF]/20 text-[#00B8FF] border border-[#00B8FF]/50'
                    : 'bg-[#FF314F]/20 text-[#FF314F] border border-[#FF314F]/60'
                }`}
              >
                {beckie.mic_enabled ? 'ACTIVE' : 'MUTED'}
              </button>
            </div>

            {/* Activity Tracking */}
            <div className="p-3 rounded-xl bg-[#030716]/80 border border-[#1677FF]/30 flex items-center justify-between">
              <div className="flex items-center gap-3">
                {beckie.activity_tracking_enabled ? (
                  <Shield className="w-5 h-5 text-[#00B8FF]" />
                ) : (
                  <ShieldOff className="w-5 h-5 text-gray-500" />
                )}
                <div>
                  <div className="font-semibold text-xs text-[#D7EEFF]">Activity Tracking</div>
                  <div className="text-[10px] text-[#6A92BA]">
                    {beckie.activity_tracking_enabled ? 'Approved apps only' : 'Tracking suspended'}
                  </div>
                </div>
              </div>
              <button
                onClick={toggleActivityTracking}
                className={`px-3 py-1 rounded-lg text-xs font-bold mono-val transition-all ${
                  beckie.activity_tracking_enabled
                    ? 'bg-[#1677FF]/20 text-[#00B8FF] border border-[#00B8FF]/50'
                    : 'bg-gray-800 text-gray-400 border border-gray-700'
                }`}
              >
                {beckie.activity_tracking_enabled ? 'ENABLED' : 'PAUSED'}
              </button>
            </div>

            {/* Emotion Features Toggle */}
            <div className="p-3 rounded-xl bg-[#030716]/80 border border-[#1677FF]/30 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Heart className={`w-5 h-5 ${emotionEnabled ? 'text-[#00B8FF]' : 'text-gray-500'}`} />
                <div>
                  <div className="font-semibold text-xs text-[#D7EEFF]">Emotion Understanding</div>
                  <div className="text-[10px] text-[#6A92BA]">Infer valence & arousal locally</div>
                </div>
              </div>
              <button
                onClick={toggleEmotionEnabled}
                className={`px-3 py-1 rounded-lg text-xs font-bold mono-val transition-all ${
                  emotionEnabled
                    ? 'bg-[#1677FF]/20 text-[#00B8FF] border border-[#00B8FF]/50'
                    : 'bg-gray-800 text-gray-400 border border-gray-700'
                }`}
              >
                {emotionEnabled ? 'ON' : 'OFF'}
              </button>
            </div>

            {/* Neutral Mode */}
            <div className="p-3 rounded-xl bg-[#030716]/80 border border-[#1677FF]/30 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <EyeOff className={`w-5 h-5 ${neutralMode ? 'text-[#FF8A2A]' : 'text-gray-500'}`} />
                <div>
                  <div className="font-semibold text-xs text-[#D7EEFF]">Neutral Mode</div>
                  <div className="text-[10px] text-[#6A92BA]">Disable adaptive dialogue responses</div>
                </div>
              </div>
              <button
                onClick={toggleNeutralMode}
                className={`px-3 py-1 rounded-lg text-xs font-bold mono-val transition-all ${
                  neutralMode
                    ? 'bg-[#FF8A2A]/20 text-[#FF8A2A] border border-[#FF8A2A]/60'
                    : 'bg-gray-800 text-gray-400 border border-gray-700'
                }`}
              >
                {neutralMode ? 'LOCKED' : 'DYNAMIC'}
              </button>
            </div>

            {/* Reduced Motion Accessibility */}
            <div className="p-3 rounded-xl bg-[#030716]/80 border border-[#1677FF]/30 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Sliders className={`w-5 h-5 ${reducedMotion ? 'text-[#00B8FF]' : 'text-[#6A92BA]'}`} />
                <div>
                  <div className="font-semibold text-xs text-[#D7EEFF]">Reduced Motion</div>
                  <div className="text-[10px] text-[#6A92BA]">Pause rotating fan & particle animations</div>
                </div>
              </div>
              <button
                onClick={toggleReducedMotion}
                className={`px-3 py-1 rounded-lg text-xs font-bold mono-val transition-all ${
                  reducedMotion
                    ? 'bg-[#1677FF]/20 text-[#00B8FF] border border-[#00B8FF]/50'
                    : 'bg-gray-800 text-gray-400 border border-gray-700'
                }`}
              >
                {reducedMotion ? 'ENABLED' : 'DISABLED'}
              </button>
            </div>

            {/* Dialogue Mode Selector */}
            <div className="p-3 rounded-xl bg-[#030716]/80 border border-[#1677FF]/30">
              <div className="font-semibold text-xs text-[#D7EEFF] mb-2 flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-[#00B8FF]" />
                Dialogue Mode Selection
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                {(['NEUTRAL', 'SUPPORTIVE', 'DIRECT', 'CHALLENGE'] as DialogueMode[]).map((m) => (
                  <button
                    key={m}
                    onClick={() => setMode(m)}
                    className={`py-1.5 px-2 rounded-lg border text-center transition-all ${
                      beckie.current_mode === m
                        ? 'border-[#00B8FF] bg-[#1677FF]/30 text-[#00B8FF] font-bold shadow-[0_0_8px_rgba(0,184,255,0.3)]'
                        : 'border-[#1677FF]/30 bg-[#030716]/50 text-[#6A92BA] hover:border-[#1677FF]'
                    }`}
                  >
                    {m}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Bottom Actions: Clear History & Emergency Pause */}
        <div className="space-y-3 pt-5 border-t border-[#1677FF]/30 mt-6">
          <button
            onClick={clearEmotionHistory}
            className="w-full py-2.5 rounded-xl border border-[#FF314F]/40 hover:bg-[#FF314F]/10 text-[#FF314F] text-xs font-bold mono-val flex items-center justify-center gap-2 transition-all"
          >
            <Trash2 className="w-4 h-4" />
            CLEAR EMOTION & INFERENCE HISTORY
          </button>

          {isPaused ? (
            <button
              onClick={resumeFromPause}
              className="w-full py-3 rounded-xl border border-[#00B8FF]/70 bg-[#00B8FF]/20 hover:bg-[#00B8FF]/30 text-[#00B8FF] text-xs font-black mono-val tracking-wider flex items-center justify-center gap-2 transition-all shadow-[0_0_15px_rgba(0,184,255,0.4)] animate-pulse"
            >
              <Play className="w-4 h-4" />
              RESUME BECKIE OPERATIONS
            </button>
          ) : (
            <button
              onClick={emergencyPause}
              className="w-full py-3 rounded-xl border border-[#FF314F]/80 bg-[#FF314F]/20 hover:bg-[#FF314F]/30 text-[#FF314F] text-xs font-black mono-val tracking-wider flex items-center justify-center gap-2 transition-all shadow-[0_0_15px_rgba(255,49,79,0.5)]"
            >
              <AlertOctagon className="w-4 h-4 animate-pulse" />
              EMERGENCY PAUSE (HALT ALL TELEMETRY)
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
