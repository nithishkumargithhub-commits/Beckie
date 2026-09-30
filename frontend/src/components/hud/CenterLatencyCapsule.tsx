/**
 * CenterLatencyCapsule.tsx – Zone 2: Top-Center System-Time and Latency Capsule
 *
 * Implements:
 * - Horizontally centered, top 20px, width 260px
 * - Live system time readout
 * - Color-coded LLM response latency (<1s green, 1-2s yellow, >2s red)
 * - Local model name badge
 */

import React, { useState, useEffect } from 'react';
import { useJarvisStore } from '../../store/useJarvisStore';

export const CenterLatencyCapsule: React.FC = () => {
  const { beckie } = useJarvisStore();
  const [timeStr, setTimeStr] = useState('');

  useEffect(() => {
    const update = () => {
      const now = new Date();
      setTimeStr(now.toTimeString().substring(0, 8));
    };
    update();
    const timer = setInterval(update, 1000);
    return () => clearInterval(timer);
  }, []);

  const latency = beckie.latency_ms ?? 0;
  let latencyColor = 'text-[#00B8FF] border-[#1677FF]/50';
  if (latency > 2000) {
    latencyColor = 'text-[#FF1744] border-[#FF1744]/50 text-glow-red';
  } else if (latency > 1000) {
    latencyColor = 'text-[#FF8A2A] border-[#FF8A2A]/50 text-glow-amber';
  }

  return (
    <div
      style={{
        position: 'absolute',
        left: '50%',
        transform: 'translateX(-50%)',
        top: '20px',
        width: '260px',
        zIndex: 20,
      }}
      className="flex flex-col items-center pointer-events-auto select-none"
    >
      {/* Top Floating Time Capsule */}
      <div className="px-4 py-1 rounded-full hud-panel border border-[#1677FF]/40 text-[11px] mono-val text-[#7AA8FF] tracking-widest mb-1.5 shadow-[0_0_10px_rgba(22,119,255,0.25)]">
        SYS_TIME: <span className="font-bold text-[#00B8FF] text-glow">{timeStr}</span>
      </div>

      {/* Latency Meter */}
      <div
        className={`w-full py-1.5 px-3 rounded-xl hud-panel border text-center transition-all ${latencyColor}`}
      >
        <div className="text-[9px] tracking-widest uppercase opacity-75">
          LLM INFERENCE LATENCY
        </div>
        <div className="mono-val text-xl font-black leading-tight">
          {beckie.latency_ms !== null ? `${Math.round(beckie.latency_ms)} ms` : 'N/A'}
        </div>
        <div className="text-[8px] tracking-wider mono-val text-[#6A92BA] mt-0.5 truncate">
          {beckie.model_name || 'QWEN3 8B Q4_K_M'}
        </div>
      </div>
    </div>
  );
};
