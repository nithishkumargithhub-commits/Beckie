/**
 * TopCenterModeDisplay.tsx – Dedicated Top-Center Alienware Mode Command Box
 *
 * Implements:
 * - Prominent futuristic HUD box at top center of dashboard
 * - Displays active Alienware Operating Mode (G-Mode, Performance, Balanced, Quiet, Cool, Full Speed)
 * - Live fan speeds (CPU & GPU RPM + capacity bars)
 * - Live System Time and LLM Inference Latency
 * - Mode preview & Hardware Sync controls
 * - Theme-reactive cybernetic glow and chamfered HUD architecture
 */

import React, { useState, useEffect } from 'react';
import { useJarvisStore } from '../../store/useJarvisStore';
import { getModeTheme, ALL_MODES, OperatingModeKey } from '../../utils/themeUtils';

interface TopCenterModeDisplayProps {
  activeModeOverride?: string | null;
  onSelectMode?: (mode: string | null) => void;
}

export const TopCenterModeDisplay: React.FC<TopCenterModeDisplayProps> = ({
  activeModeOverride,
  onSelectMode,
}) => {
  const { cpu, gpu, beckie } = useJarvisStore();
  const [timeStr, setTimeStr] = useState('');
  const [showSwitcher, setShowSwitcher] = useState(false);

  // System time ticker
  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setTimeStr(now.toTimeString().substring(0, 8));
    };
    updateTime();
    const timer = setInterval(updateTime, 1000);
    return () => clearInterval(timer);
  }, []);

  // Determine current active mode (hardware live vs interactive preview)
  const hardwareMode = cpu.performanceMode?.mode || gpu.performanceMode?.mode || 'Balanced';
  const effectiveMode = activeModeOverride || hardwareMode;
  const theme = getModeTheme(effectiveMode);
  const isHardwareSynced = !activeModeOverride || activeModeOverride.toLowerCase() === hardwareMode.toLowerCase();

  // Fans telemetry
  const cpuRpm = cpu.fan?.rpm ?? (theme.fanSpeedPct === 100 ? 5400 : theme.fanSpeedRpm);
  const gpuRpm = gpu.fan?.rpm ?? (theme.fanSpeedPct === 100 ? 5400 : theme.fanSpeedRpm);
  const cpuPct = cpu.fan?.percent ?? theme.fanSpeedPct;
  const gpuPct = gpu.fan?.percent ?? theme.fanSpeedPct;

  // Latency styling
  const latency = beckie.latency_ms ?? 0;
  let latencyColor = 'text-[#00B8FF]';
  if (latency > 2000) latencyColor = 'text-[#FF1744]';
  else if (latency > 1000) latencyColor = 'text-[#FF8A2A]';

  return (
    <div
      style={{
        position: 'absolute',
        left: '50%',
        transform: 'translateX(-50%)',
        top: '14px',
        zIndex: 25,
      }}
      className="flex flex-col items-center pointer-events-auto select-none w-[94vw] max-w-[560px]"
    >
      {/* Main Holographic Cockpit Box */}
      <div
        className="w-full rounded-2xl p-3 px-4 relative transition-all duration-500 backdrop-blur-xl"
        style={{
          backgroundColor: theme.bgTint,
          border: `1.5px solid ${theme.borderColor}`,
          boxShadow: `0 0 28px ${theme.glowColor}, inset 0 0 16px ${theme.glowColor.replace(/[\d\.]+\)$/, '0.15)')}`,
        }}
      >
        {/* Decorative Sci-Fi Corner Brackets */}
        <div
          className="absolute -top-[2px] -left-[2px] w-3 h-3 border-t-2 border-l-2 pointer-events-none"
          style={{ borderColor: theme.accentBright }}
        />
        <div
          className="absolute -top-[2px] -right-[2px] w-3 h-3 border-t-2 border-r-2 pointer-events-none"
          style={{ borderColor: theme.accentBright }}
        />
        <div
          className="absolute -bottom-[2px] -left-[2px] w-3 h-3 border-b-2 border-l-2 pointer-events-none"
          style={{ borderColor: theme.accentBright }}
        />
        <div
          className="absolute -bottom-[2px] -right-[2px] w-3 h-3 border-b-2 border-r-2 pointer-events-none"
          style={{ borderColor: theme.accentBright }}
        />

        {/* TOP STATUS TICKER BAR */}
        <div className="flex items-center justify-between border-b pb-1.5 mb-2" style={{ borderColor: `${theme.accentColor}33` }}>
          {/* Hardware Telemetry Source Badge */}
          <div className="flex items-center gap-2">
            <span className="relative flex h-2 w-2">
              <span
                className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75"
                style={{ backgroundColor: theme.accentColor }}
              />
              <span
                className="relative inline-flex rounded-full h-2 w-2"
                style={{ backgroundColor: theme.accentBright }}
              />
            </span>
            <span className="text-[10px] mono-val font-semibold tracking-wider text-[#A0C4E8] uppercase">
              AWCC 6.X // {isHardwareSynced ? 'LIVE HARDWARE SYNC' : 'PREVIEW OVERRIDE'}
            </span>
            <span
              className="text-[9px] px-1.5 py-0.5 rounded font-mono font-bold tracking-tight"
              style={{
                backgroundColor: `${theme.accentColor}26`,
                color: theme.accentBright,
                border: `1px solid ${theme.accentColor}55`,
              }}
            >
              {theme.badgeText}
            </span>
          </div>

          {/* Clock & Latency Readout */}
          <div className="flex items-center gap-3 text-[10px] mono-val text-[#8AB4D8]">
            <div>
              SYS_TIME: <span className="text-[#D7EEFF] font-bold">{timeStr}</span>
            </div>
            <div className="border-l border-white/10 pl-2">
              LLM: <span className={`font-bold ${latencyColor}`}>{Math.round(latency)} ms</span>
            </div>
          </div>
        </div>

        {/* HERO MODE DISPLAY ROW */}
        <div className="flex items-center justify-between gap-3 my-1">
          <div className="flex items-center gap-3">
            {/* Pulsing Mode Holographic Icon */}
            <div
              className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0 transition-transform duration-300 shadow-md"
              style={{
                backgroundColor: `${theme.accentColor}22`,
                border: `1.5px solid ${theme.accentBright}`,
                boxShadow: `0 0 14px ${theme.glowColor}`,
              }}
            >
              {theme.iconType === 'flame' && (
                <svg className="w-6 h-6 animate-pulse" viewBox="0 0 24 24" fill={theme.accentBright}>
                  <path d="M12 23c6.075 0 8-4.5 8-8.5 0-3.5-2.5-6.5-4.5-8.5 0 2-1 3.5-2.5 3.5-1.5 0-2-1.5-2-3 0-2.5 1.5-4.5 2-5.5C11.5 1 9.5 2.5 8 5 6 8.5 4 11 4 14.5c0 4 2 8.5 8 8.5z"/>
                </svg>
              )}
              {theme.iconType === 'rocket' && (
                <svg className="w-6 h-6" viewBox="0 0 24 24" fill={theme.accentBright}>
                  <path d="M13.13 2.21a2 2 0 0 0-2.26 0L4.2 6.55a2 2 0 0 0-.95 1.7V17a2 2 0 0 0 1 1.73l6.67 4.1a2 2 0 0 0 2.16 0L19.75 18.7a2 2 0 0 0 1-1.7V8.25a2 2 0 0 0-.95-1.7z"/>
                </svg>
              )}
              {theme.iconType === 'shield' && (
                <svg className="w-6 h-6" viewBox="0 0 24 24" fill={theme.accentBright}>
                  <path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm0 10.99h7c-.53 4.12-3.28 7.79-7 8.94V12H5V6.3l7-3.11v8.8z"/>
                </svg>
              )}
              {theme.iconType === 'leaf' && (
                <svg className="w-6 h-6" viewBox="0 0 24 24" fill={theme.accentBright}>
                  <path d="M17 8C8 10 5.9 16.17 3.82 21.34l1.89.66l.95-2.3c.48.17.98.3 1.34.3C19 20 22 3 22 3c-1 2-8 2.25-13 3.25S2 11.5 2 13.5s1.75 3.75 1.75 3.75C7 8 17 8 17 8z"/>
                </svg>
              )}
              {theme.iconType === 'snowflake' && (
                <svg className="w-6 h-6 animate-spin" style={{ animationDuration: '14s' }} viewBox="0 0 24 24" fill={theme.accentBright}>
                  <path d="M22 11h-4.17l2.58-2.59-1.42-1.41L15.41 10.6 13 8.17V4h3V2h-3a2 2 0 0 0-2 2v4.17L8.59 7 7.18 8.41 9.77 11H5.59L3 8.41 1.59 9.83 4.17 12.4 1.59 15 3 16.41 5.59 13.8h4.18l-2.59 2.59 1.41 1.41L11 15.41V19.6H8v2h3a2 2 0 0 0 2-2v-4.17l2.41 2.41 1.41-1.41L14.23 13.8H18.4l2.59 2.59 1.41-1.41L19.83 12.4 22.4 9.83 21 8.41 18.41 11H22z"/>
                </svg>
              )}
              {theme.iconType === 'gauge' && (
                <svg className="w-6 h-6" viewBox="0 0 24 24" fill={theme.accentBright}>
                  <path d="M12 2a10 10 0 0 0-10 10c0 4.14 2.52 7.7 6.13 9.24l1.15-1.92A8 8 0 1 1 20 12c0 1.25-.29 2.43-.8 3.5l1.83 1.09A9.97 9.97 0 0 0 22 12A10 10 0 0 0 12 2zm-1 5v6.59l4.54 2.73.79-1.32L12.5 12.7V7h-1.5z"/>
                </svg>
              )}
            </div>

            {/* Mode Name and Description */}
            <div>
              <div
                className="hud-title text-base sm:text-lg font-black tracking-widest leading-none drop-shadow"
                style={{
                  color: theme.accentBright,
                  textShadow: `0 0 12px ${theme.glowColor}`,
                }}
              >
                {theme.label}
              </div>
              <div className="text-[10px] text-[#A6C8E8] tracking-wider font-mono mt-1">
                {theme.subLabel}
              </div>
            </div>
          </div>

          {/* Mode Switcher Toggle Button */}
          <button
            onClick={() => setShowSwitcher(!showSwitcher)}
            className="px-2.5 py-1 rounded-lg text-[10px] font-mono font-bold tracking-wider uppercase border transition-all shrink-0 hover:scale-105 active:scale-95"
            style={{
              borderColor: `${theme.accentColor}88`,
              backgroundColor: `${theme.accentColor}26`,
              color: theme.accentBright,
              boxShadow: `0 0 10px ${theme.glowColor}`,
            }}
          >
            {showSwitcher ? 'CLOSE MODES' : 'CHANGE MODE ▾'}
          </button>
        </div>

        {/* HARDWARE FANS MINI-TELEMETRY STRIP */}
        <div
          className="grid grid-cols-2 gap-2 mt-2 pt-2 border-t text-[11px] font-mono"
          style={{ borderColor: `${theme.accentColor}33` }}
        >
          {/* CPU Fan Readout */}
          <div className="flex flex-col">
            <div className="flex items-center justify-between text-[#8AB4D8] mb-0.5">
              <span>CPU COOLER</span>
              <span className="font-bold text-[#E0F2FE]">{cpuRpm} RPM ({Math.round(cpuPct)}%)</span>
            </div>
            <div className="w-full h-1.5 bg-black/40 rounded-full overflow-hidden border border-white/10">
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{
                  width: `${Math.min(100, Math.max(5, cpuPct))}%`,
                  backgroundColor: theme.accentBright,
                  boxShadow: `0 0 8px ${theme.accentColor}`,
                }}
              />
            </div>
          </div>

          {/* GPU Fan Readout */}
          <div className="flex flex-col">
            <div className="flex items-center justify-between text-[#8AB4D8] mb-0.5">
              <span>GPU COOLER</span>
              <span className="font-bold text-[#E0F2FE]">{gpuRpm} RPM ({Math.round(gpuPct)}%)</span>
            </div>
            <div className="w-full h-1.5 bg-black/40 rounded-full overflow-hidden border border-white/10">
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{
                  width: `${Math.min(100, Math.max(5, gpuPct))}%`,
                  backgroundColor: theme.accentBright,
                  boxShadow: `0 0 8px ${theme.accentColor}`,
                }}
              />
            </div>
          </div>
        </div>

        {/* EXPANDABLE MODE SELECTOR CHIPS */}
        {showSwitcher && (
          <div
            className="mt-2.5 pt-2 border-t flex flex-wrap items-center justify-center gap-1.5 animate-fadeIn"
            style={{ borderColor: `${theme.accentColor}33` }}
          >
            {ALL_MODES.map((m) => {
              const isActive = effectiveMode.toLowerCase().includes(m.key) ||
                (m.key === 'g-mode' && (effectiveMode.toLowerCase().includes('g-mode') || effectiveMode.toLowerCase().includes('high performance')));
              const itemTheme = getModeTheme(m.key);

              return (
                <button
                  key={m.key}
                  onClick={() => {
                    if (onSelectMode) onSelectMode(m.key);
                  }}
                  className={`px-2.5 py-1 rounded-md text-[10px] font-mono tracking-wider transition-all duration-200 font-bold border ${
                    isActive
                      ? 'scale-105 shadow-md'
                      : 'opacity-70 hover:opacity-100 hover:scale-102'
                  }`}
                  style={{
                    backgroundColor: isActive ? itemTheme.accentColor : 'rgba(10, 20, 45, 0.6)',
                    color: isActive ? '#FFFFFF' : itemTheme.accentBright,
                    borderColor: itemTheme.borderColor,
                    boxShadow: isActive ? `0 0 12px ${itemTheme.glowColor}` : 'none',
                  }}
                >
                  {m.name}
                </button>
              );
            })}

            {/* Sync Hardware Reset Button */}
            {!isHardwareSynced && (
              <button
                onClick={() => {
                  if (onSelectMode) onSelectMode(null);
                }}
                className="px-2.5 py-1 rounded-md text-[10px] font-mono tracking-wider font-bold bg-[#1677FF] text-white border border-[#00B8FF] shadow-[0_0_10px_rgba(0,184,255,0.5)] hover:scale-105"
              >
                ↺ SYNC AWCC HW
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
