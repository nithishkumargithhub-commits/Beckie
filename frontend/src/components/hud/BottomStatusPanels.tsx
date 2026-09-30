/**
 * BottomStatusPanels.tsx – Zone 7: Bottom-Left Privacy and Dialogue Status Modules
 *
 * Implements:
 * - Position: left 24px, bottom 26px
 * - Three separate status panels:
 *   1. MIC PRIVACY: OFF | LISTENING | PAUSED
 *   2. ACTIVITY TRACKING: OFF | MONITORING | PAUSED
 *   3. DIALOGUE MODE: NEUTRAL | SUPPORTIVE | DIRECT | CHALLENGE
 */

import React from 'react';
import { Mic, MicOff, Shield, ShieldOff, MessageSquare, AlertTriangle } from 'lucide-react';
import { useJarvisStore } from '../../store/useJarvisStore';

export const BottomStatusPanels: React.FC = () => {
  const { beckie, toggleMic, toggleActivityTracking } = useJarvisStore();

  const isPaused = beckie.status === 'PAUSED';

  // 1. Microphone Privacy Display Value
  const micValue = isPaused ? 'PAUSED' : !beckie.mic_enabled ? 'OFF' : 'LISTENING';
  let micColorClass = 'border-[#1677FF]/40 text-[#00B8FF] bg-[#1677FF]/10';
  if (micValue === 'PAUSED') {
    micColorClass = 'border-[#FF8A2A]/60 text-[#FF8A2A] bg-[#FF8A2A]/15';
  } else if (micValue === 'OFF') {
    micColorClass = 'border-[#FF314F]/60 text-[#FF314F] bg-[#FF314F]/15 text-glow-red';
  }

  // 2. Activity Tracking Display Value
  const trackingValue = isPaused
    ? 'PAUSED'
    : !beckie.activity_tracking_enabled
    ? 'OFF'
    : 'MONITORING';
  let trackingColorClass = 'border-[#1677FF]/40 text-[#7AA8FF] bg-[#1677FF]/10';
  if (trackingValue === 'PAUSED') {
    trackingColorClass = 'border-[#FF8A2A]/60 text-[#FF8A2A] bg-[#FF8A2A]/15';
  } else if (trackingValue === 'OFF') {
    trackingColorClass = 'border-gray-600 text-gray-400 bg-gray-900/60';
  }

  // 3. Dialogue Mode Value
  const dialogueMode = beckie.current_mode || 'SUPPORTIVE';

  return (
    <div
      style={{
        position: 'absolute',
        left: '24px',
        bottom: '26px',
        zIndex: 20,
      }}
      className="flex items-center gap-3 pointer-events-auto select-none"
    >
      {/* Panel 1: MIC PRIVACY */}
      <div
        onClick={toggleMic}
        title="Toggle Microphone Privacy"
        className={`px-4 py-2.5 rounded-xl hud-panel border transition-all cursor-pointer hover:scale-[1.02] ${micColorClass}`}
      >
        <div className="flex items-center gap-2 mb-0.5">
          {micValue === 'LISTENING' ? (
            <Mic className="w-3.5 h-3.5 text-[#00B8FF] animate-pulse" />
          ) : micValue === 'PAUSED' ? (
            <AlertTriangle className="w-3.5 h-3.5 text-[#FF8A2A]" />
          ) : (
            <MicOff className="w-3.5 h-3.5 text-[#FF314F]" />
          )}
          <span className="text-[10px] tracking-wider uppercase font-semibold text-[#D7EEFF] opacity-80">
            MIC PRIVACY
          </span>
        </div>
        <div className="hud-title text-sm font-extrabold tracking-wide">{micValue}</div>
      </div>

      {/* Panel 2: ACTIVITY TRACKING */}
      <div
        onClick={toggleActivityTracking}
        title="Toggle Activity Tracking"
        className={`px-4 py-2.5 rounded-xl hud-panel border transition-all cursor-pointer hover:scale-[1.02] ${trackingColorClass}`}
      >
        <div className="flex items-center gap-2 mb-0.5">
          {trackingValue === 'MONITORING' ? (
            <Shield className="w-3.5 h-3.5 text-[#00B8FF]" />
          ) : (
            <ShieldOff className="w-3.5 h-3.5 text-gray-400" />
          )}
          <span className="text-[10px] tracking-wider uppercase font-semibold text-[#D7EEFF] opacity-80">
            ACTIVITY TRACKING
          </span>
        </div>
        <div className="hud-title text-sm font-extrabold tracking-wide">{trackingValue}</div>
      </div>

      {/* Panel 3: DIALOGUE MODE */}
      <div className="px-4 py-2.5 rounded-xl hud-panel border border-[#1677FF]/40 bg-[#1677FF]/10 text-[#00B8FF]">
        <div className="flex items-center gap-2 mb-0.5">
          <MessageSquare className="w-3.5 h-3.5 text-[#00B8FF]" />
          <span className="text-[10px] tracking-wider uppercase font-semibold text-[#D7EEFF] opacity-80">
            DIALOGUE MODE
          </span>
        </div>
        <div className="hud-title text-sm font-extrabold tracking-wide">{dialogueMode}</div>
      </div>
    </div>
  );
};
