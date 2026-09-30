/**
 * CpuModule.tsx – Right Circular CPU Telemetry Module
 *
 * Title: CPU // INTEL CORE ULTRA 9 275HX
 * Implements 7-blade blue-white HolographicFan,
 * actual clock frequency, temperature alert halos,
 * dedicated CPU MODE badge and confidence/source indicator.
 */

import React from 'react';
import { CpuTelemetry } from '../../types/telemetry';
import { HolographicFan } from './HolographicFan';
import { getModeTheme } from '../../utils/themeUtils';

interface CpuModuleProps {
  telemetry: CpuTelemetry;
  isPaused?: boolean;
  reducedMotion?: boolean;
  onClick?: () => void;
}

export const CpuModule: React.FC<CpuModuleProps> = ({
  telemetry,
  isPaused = false,
  reducedMotion = false,
  onClick,
}) => {
  const {
    name,
    utilizationPct,
    temperatureC,
    frequencyMhz,
    fan,
    performanceMode,
    source,
  } = telemetry;

  const theme = getModeTheme(performanceMode?.mode);
  const util = utilizationPct != null ? Math.round(utilizationPct) : null;
  const temp = temperatureC != null ? Math.round(temperatureC) : null;
  const freqStr =
    frequencyMhz != null
      ? frequencyMhz >= 1000
        ? `${(frequencyMhz / 1000).toFixed(2)} GHz`
        : `${Math.round(frequencyMhz)} MHz`
      : 'N/A';

  // Alerts
  const isHighTemp = (temp ?? 0) > 75;
  const isCriticalTemp = (temp ?? 0) > 85;

  // Fan speed readout
  let fanDisplay = 'UNAVAILABLE';
  let fanUnit = '';
  if (fan.rpm != null) {
    fanDisplay = `${fan.rpm}`;
    fanUnit = 'RPM';
  } else if (fan.percent != null) {
    fanDisplay = `${Math.round(fan.percent)}`;
    fanUnit = '%';
  }

  // Source & confidence badge
  const sourceConfidence = `${(fan.source || source).toUpperCase()} / ${performanceMode.confidence.toUpperCase()}`;

  return (
    <div
      className={`hud-panel rounded-2xl p-3.5 pb-2.5 flex flex-col items-center justify-between w-[300px] h-[340px] relative transition-all duration-300 ${
        isCriticalTemp ? 'hud-glow-red' : 'hud-glow'
      }`}
      style={!isCriticalTemp ? {
        borderColor: theme.borderColor,
        boxShadow: `0 0 22px ${theme.glowColor}, inset 0 0 12px ${theme.glowColor.replace(/[\d\.]+\)$/, '0.12)')}`,
      } : undefined}
    >
      {/* Header Bar */}
      <div className="w-full flex items-center justify-between border-b pb-2" style={{ borderColor: `${theme.accentColor}44` }}>
        <div>
          <h2 className="hud-title text-sm tracking-wider text-[#D7EEFF] font-bold">
            CPU // {name || 'INTEL CORE ULTRA 9 275HX'}
          </h2>
          <div className="flex items-center gap-2 mt-0.5">
            <span
              className="text-[10px] font-mono px-1.5 py-0.2 rounded border font-bold tracking-tight"
              style={{
                borderColor: theme.borderColor,
                color: theme.accentBright,
                backgroundColor: `${theme.accentColor}22`,
                boxShadow: `0 0 8px ${theme.glowColor}`,
              }}
            >
              CPU MODE: {performanceMode.mode || 'UNAVAILABLE'}
            </span>
          </div>
        </div>

        {/* Utilization readout */}
        <div className="text-right">
          <span
            className={`mono-val text-xl font-bold ${
              isCriticalTemp
                ? 'text-[#FF1744] text-glow-red'
                : isHighTemp
                ? 'text-[#FF8A2A] text-glow-amber'
                : 'text-[#D7EEFF] text-glow'
            }`}
          >
            {util != null ? `${util}%` : 'N/A'}
          </span>
          <div className="text-[9px] text-[#6A92BA] uppercase tracking-wider">LOAD</div>
        </div>
      </div>

      {/* Center 7-Blade Holographic Fan */}
      <div className="relative my-auto">
        <HolographicFan
          label="CPU FAN"
          bladeCount={7}
          rpm={fan.rpm}
          percent={fan.percent}
          utilizationPct={utilizationPct}
          temperatureC={temperatureC}
          performanceMode={performanceMode.mode}
          isAvailable={fan.available}
          unavailableReason={fan.unavailableReason}
          colorProfile="cpu"
          isPaused={isPaused}
          reducedMotion={reducedMotion}
          onClick={onClick}
        />

        {/* Frequency Badge Overlay */}
        <div className="absolute top-2 left-2 text-left pointer-events-none">
          <div className="text-[9px] text-[#6A92BA]">FREQ</div>
          <div className="mono-val text-xs text-[#00B8FF] font-semibold">
            {freqStr}
          </div>
        </div>

        {/* Temperature Badge Overlay */}
        <div className="absolute top-2 right-2 text-right pointer-events-none">
          <div
            className={`mono-val text-sm font-bold ${
              isCriticalTemp
                ? 'text-[#FF1744]'
                : isHighTemp
                ? 'text-[#FF8A2A]'
                : 'text-[#D7EEFF]'
            }`}
          >
            {temp != null ? `${temp}°C` : 'N/A'}
          </div>
          <div className="text-[8px] text-[#6A92BA]">TEMP</div>
        </div>
      </div>

      {/* Footer Status Bar with Strict Sensor Reason */}
      <div className="w-full flex items-center justify-between border-t border-[#1677FF]/30 pt-1.5 text-[10px] font-mono">
        <div className="flex flex-col">
          <span className="text-[#6A92BA]">
            FAN SPEED:{' '}
            <span
              className={
                fan.available
                  ? 'text-[#00B8FF] font-bold'
                  : 'text-[#FF8A2A] font-semibold'
              }
            >
              {fanDisplay} {fanUnit}
            </span>
          </span>
          {!fan.available && (
            <span className="text-[8px] text-[#6A92BA] tracking-tight">
              {fan.unavailableReason || 'OEM SENSOR NOT EXPOSED'}
            </span>
          )}
        </div>

        <div className="text-right flex flex-col">
          <span className="text-[#6A92BA] text-[9px]">SOURCE</span>
          <span className="text-[#00B8FF] text-[9px]">{sourceConfidence}</span>
        </div>
      </div>
    </div>
  );
};
