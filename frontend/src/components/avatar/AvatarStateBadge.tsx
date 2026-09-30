/**
 * AvatarStateBadge.tsx – Real-Time Cybernetic Avatar FSM State Indicator
 */

import React from 'react';
import { useAvatarStore } from '../../stores/avatarStore';
import { AvatarFsmState } from '../../types/avatar';

const stateColors: Record<AvatarFsmState, { bg: string; text: string; border: string; glow: string }> = {
  HIDDEN: { bg: 'bg-black/60', text: 'text-gray-400', border: 'border-gray-600/40', glow: 'none' },
  SPAWNING: { bg: 'bg-[#1677FF]/20', text: 'text-[#00B8FF]', border: 'border-[#1677FF]', glow: '0 0 10px #00B8FF' },
  IDLE: { bg: 'bg-[#00B8FF]/15', text: 'text-[#00B8FF]', border: 'border-[#00B8FF]/50', glow: '0 0 10px rgba(0, 184, 255, 0.4)' },
  OBSERVING: { bg: 'bg-[#FF8A2A]/20', text: 'text-[#FFB300]', border: 'border-[#FF8A2A]/60', glow: '0 0 10px #FF8A2A' },
  WALKING: { bg: 'bg-[#00E676]/20', text: 'text-[#00E676]', border: 'border-[#00E676]/60', glow: '0 0 10px #00E676' },
  HOVERING: { bg: 'bg-[#7AA8FF]/20', text: 'text-[#7AA8FF]', border: 'border-[#1677FF]/60', glow: '0 0 10px #1677FF' },
  FLYING: { bg: 'bg-[#FF1744]/25', text: 'text-[#FF5252]', border: 'border-[#FF1744]', glow: '0 0 14px #FF1744' },
  GREETING: { bg: 'bg-[#00B8FF]/25', text: 'text-[#00B8FF]', border: 'border-[#00B8FF]', glow: '0 0 12px #00B8FF' },
  LISTENING: { bg: 'bg-[#00E676]/25', text: 'text-[#00E676]', border: 'border-[#00E676]', glow: '0 0 14px #00E676' },
  THINKING: { bg: 'bg-[#FF8A2A]/25', text: 'text-[#FFB300]', border: 'border-[#FF8A2A]', glow: '0 0 14px #FF8A2A' },
  SPEAKING: { bg: 'bg-[#1677FF]/30', text: 'text-[#00B8FF]', border: 'border-[#00B8FF]', glow: '0 0 16px #00B8FF' },
  GESTURING: { bg: 'bg-[#D946EF]/25', text: 'text-[#F0ABFC]', border: 'border-[#D946EF]', glow: '0 0 12px #D946EF' },
  SAFE_WEAPON_POSE: { bg: 'bg-[#FF1744]/25', text: 'text-[#FF5252]', border: 'border-[#FF1744]', glow: '0 0 12px #FF1744' },
  PAUSED: { bg: 'bg-[#FF1744]/30', text: 'text-[#FF1744]', border: 'border-[#FF1744]', glow: '0 0 10px #FF1744' },
  ERROR: { bg: 'bg-red-900/40', text: 'text-red-400', border: 'border-red-500', glow: '0 0 10px red' },
};

export const AvatarStateBadge: React.FC = () => {
  const { fsmState, permissions, setSettingsOpen, setInspectionOpen } = useAvatarStore();

  if (!permissions.enabled) {
    return (
      <button
        onClick={() => setSettingsOpen(true)}
        className="px-2 py-0.5 rounded-full text-[10px] font-mono tracking-wider bg-gray-900/60 text-gray-400 border border-gray-700/50 hover:border-gray-500 transition-all pointer-events-auto"
      >
        AVATAR: OFF
      </button>
    );
  }

  const c = stateColors[fsmState] || stateColors.IDLE;

  return (
    <div className="flex items-center gap-1.5 pointer-events-auto select-none">
      <button
        onClick={() => setSettingsOpen(true)}
        className={`px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold tracking-wider uppercase border transition-all duration-300 flex items-center gap-1.5 hover:scale-105 ${c.bg} ${c.text} ${c.border}`}
        style={{ boxShadow: c.glow }}
        title="Click to open Avatar Settings & Inspection"
      >
        <span className={`w-1.5 h-1.5 rounded-full ${fsmState === 'LISTENING' || fsmState === 'SPEAKING' ? 'animate-ping' : ''} bg-current`} />
        BECKIE: {fsmState}
      </button>

      <button
        onClick={() => setInspectionOpen(true)}
        className="px-1.5 py-0.5 rounded-md text-[9px] font-mono tracking-tight bg-black/40 text-[#7AA8FF] border border-[#1677FF]/40 hover:bg-[#1677FF]/20 hover:text-white transition-all"
        title="Inspect 3D Model Capabilities"
      >
        INSPECT
      </button>
    </div>
  );
};
