/**
 * TopNav.tsx – Tactical Top Bar with Quick Actions and Status
 */

import React, { useState, useEffect } from 'react';
import { useJarvisStore } from '../../store/useJarvisStore';
import { Sliders, Terminal, AlertOctagon, Radio } from 'lucide-react';

export const TopNav: React.FC = () => {
  const { setSettingsOpen, setLogsOpen, emergencyPause } = useJarvisStore();
  const [timeStr, setTimeStr] = useState<string>('');

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setTimeStr(now.toTimeString().substring(0, 8));
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="absolute top-0 left-0 right-0 z-20 flex justify-between items-center px-6 py-4 pointer-events-none">
      {/* Brand Title */}
      <div className="flex items-center gap-3 pointer-events-auto">
        <div className="w-9 h-9 rounded-lg hud-panel hud-glow flex items-center justify-center text-[#00f0ff] font-extrabold text-lg">
          J
        </div>
        <div>
          <h1 className="hud-title text-sm font-extrabold tracking-widest text-[#00f0ff] text-glow flex items-center gap-2">
            JARVIS // HUD 3D
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-[#00ff88]/15 border border-[#00ff88]/40 text-[9px] text-[#00ff88] font-mono">
              <Radio className="w-2.5 h-2.5 animate-pulse" />
              1s SYNC
            </span>
          </h1>
          <p className="text-[10px] text-[#00f0ff]/60 mono-val">
            AUTONOMOUS TACTICAL INTELLIGENCE
          </p>
        </div>
      </div>

      {/* Center Clock */}
      <div className="pointer-events-auto px-4 py-1.5 rounded-full hud-panel border border-[#00f0ff]/30 text-xs mono-val text-[#00f0ff] tracking-widest">
        SYS_TIME: <span className="font-bold text-glow">{timeStr}</span>
      </div>

      {/* Right Controls */}
      <div className="flex items-center gap-2.5 pointer-events-auto">
        <button
          onClick={() => setLogsOpen(true)}
          className="px-3.5 py-2 rounded-lg hud-panel border border-[#00f0ff]/40 hover:border-[#00f0ff] hover:bg-[#00f0ff]/10 text-xs font-semibold mono-val text-[#00f0ff] flex items-center gap-2 transition-all"
        >
          <Terminal className="w-4 h-4" />
          <span>LOGS</span>
        </button>

        <button
          onClick={() => setSettingsOpen(true)}
          className="px-3.5 py-2 rounded-lg hud-panel border border-[#00f0ff]/40 hover:border-[#00f0ff] hover:bg-[#00f0ff]/10 text-xs font-semibold mono-val text-[#00f0ff] flex items-center gap-2 transition-all"
        >
          <Sliders className="w-4 h-4" />
          <span>SETTINGS</span>
        </button>

        <button
          onClick={emergencyPause}
          title="Emergency Pause (Halt All)"
          className="p-2 rounded-lg border border-[#ff3355]/60 bg-[#ff3355]/15 hover:bg-[#ff3355]/30 text-[#ff3355] transition-all transform hover:scale-105"
        >
          <AlertOctagon className="w-4 h-4" />
        </button>
      </div>
    </header>
  );
};
