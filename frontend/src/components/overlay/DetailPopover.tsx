/**
 * DetailPopover.tsx – 60-Second Telemetry Sparkline Popover
 *
 * Displays high-frequency historical telemetry sparkline for the selected metric.
 */

import React from 'react';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip } from 'recharts';
import { useJarvisStore } from '../../store/useJarvisStore';
import { X, Activity } from 'lucide-react';

export const DetailPopover: React.FC = () => {
  const { selectedMetric, setSelectedMetric, history, gpu, cpu } = useJarvisStore();

  if (!selectedMetric) return null;

  const isGpu = selectedMetric === 'gpu';
  const target = isGpu ? gpu : cpu;
  const title = isGpu ? 'NVIDIA GeForce RTX 5070 Ti Telemetry' : 'Intel Core Ultra 9 Telemetry';

  const fanStr =
    target.fan.rpm != null
      ? `${target.fan.rpm} RPM`
      : target.fan.percent != null
      ? `${Math.round(target.fan.percent)}%`
      : 'UNAVAILABLE';

  const subtitle = `${target.utilizationPct ?? 'N/A'}% Load | ${
    target.temperatureC ?? 'N/A'
  }°C | Fan: ${fanStr} | Mode: ${target.performanceMode.mode || 'UNAVAILABLE'}`;

  return (
    <div className="fixed inset-0 z-40 bg-black/70 backdrop-blur-md flex items-center justify-center p-4">
      <div className="relative w-full max-w-2xl hud-panel hud-glow rounded-2xl p-6 text-[#D7EEFF] animate-in fade-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="flex justify-between items-center pb-4 border-b border-[#1677FF]/30 mb-4">
          <div className="flex items-center gap-2">
            <Activity className="w-5 h-5 text-[#00B8FF] animate-pulse" />
            <div>
              <h3 className="hud-title text-base font-bold text-[#00B8FF] text-glow">{title}</h3>
              <p className="text-xs text-[#7AA8FF] mono-val">{subtitle}</p>
            </div>
          </div>
          <button
            onClick={() => setSelectedMetric(null)}
            className="p-1.5 rounded-lg border border-[#1677FF]/40 hover:bg-[#1677FF]/20 text-[#00B8FF] transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* 60s Sparkline Chart */}
        <div className="h-64 w-full pt-2">
          <div className="text-xs uppercase tracking-wider mono-val text-[#6A92BA] mb-2">
            60-Second Real-Time Telemetry Stream
          </div>
          {history.length > 1 ? (
            <ResponsiveContainer width="100%" height="90%">
              <LineChart data={history} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                <XAxis
                  dataKey="timeStr"
                  stroke="#1677FF"
                  opacity={0.6}
                  tick={{ fontSize: 10 }}
                  tickLine={false}
                />
                <YAxis
                  stroke="#1677FF"
                  opacity={0.6}
                  domain={[0, 100]}
                  tick={{ fontSize: 10 }}
                  tickLine={false}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#030716',
                    borderColor: '#1677FF',
                    borderRadius: '8px',
                    fontSize: '11px',
                    fontFamily: 'monospace',
                  }}
                  itemStyle={{ color: '#00B8FF' }}
                />
                <Line
                  type="monotone"
                  dataKey={isGpu ? 'gpuUtil' : 'cpuUtil'}
                  name="Utilization %"
                  stroke="#00B8FF"
                  strokeWidth={2.5}
                  dot={false}
                  isAnimationActive={false}
                />
                <Line
                  type="monotone"
                  dataKey={isGpu ? 'gpuTemp' : 'cpuTemp'}
                  name="Temperature (°C)"
                  stroke="#FF314F"
                  strokeWidth={1.5}
                  strokeDasharray="4 4"
                  dot={false}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-full flex items-center justify-center text-xs opacity-50 mono-val text-[#6A92BA]">
              Gathering high-frequency telemetry samples...
            </div>
          )}
        </div>

        {/* Footer Statistics */}
        <div className="grid grid-cols-3 gap-3 pt-4 border-t border-[#1677FF]/30 mt-4 mono-val text-xs">
          <div className="bg-[#030716]/80 p-2 rounded border border-[#1677FF]/30">
            <span className="opacity-60 block text-[10px] text-[#6A92BA]">SAMPLING INTERVAL</span>
            <span className="text-[#00B8FF] font-bold">1,000 ms</span>
          </div>
          <div className="bg-[#030716]/80 p-2 rounded border border-[#1677FF]/30">
            <span className="opacity-60 block text-[10px] text-[#6A92BA]">HISTORICAL WINDOW</span>
            <span className="text-[#00B8FF] font-bold">{history.length} / 60 SEC</span>
          </div>
          <div className="bg-[#030716]/80 p-2 rounded border border-[#1677FF]/30">
            <span className="opacity-60 block text-[10px] text-[#6A92BA]">CONFIDENCE / SOURCE</span>
            <span className="text-[#7AA8FF] font-bold uppercase truncate block">
              {target.performanceMode.confidence} / {target.source}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
