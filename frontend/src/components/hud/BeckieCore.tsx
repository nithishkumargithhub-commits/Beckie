/**
 * BeckieCore.tsx – Central 3D AI Visualization Core
 *
 * Implements:
 * - Rotating outer wireframe ring with radial degree markers
 * - Inner geometric rotating Beckie reactor core (3D icosahedron/diamond projection)
 * - Horizontal scanning laser beam with glowing trail
 * - Status states: IDLE, LISTENING, THINKING, SPEAKING, PAUSED, ERROR
 * - Model status, latency, and assistant mode readouts
 * - Responsive sizing (width: 360px, height: 360px)
 */

import React, { useEffect, useRef } from 'react';
import { BeckieCoreStatus, DialogueMode } from '../../types/telemetry';

interface BeckieCoreProps {
  status: BeckieCoreStatus;
  mode: DialogueMode;
  latencyMs: number | null;
  modelName: string;
  reducedMotion?: boolean;
}

export const BeckieCore: React.FC<BeckieCoreProps> = ({
  status,
  mode,
  latencyMs,
  modelName,
  reducedMotion = false,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const scanYRef = useRef(0);
  const scanDirRef = useRef(1);
  const angleRef = useRef(0);
  const pulseRef = useRef(0);

  const isPaused = status === 'PAUSED';
  const isError = status === 'ERROR';

  // State-based accent colors
  let coreColor = '#00B8FF';
  if (status === 'THINKING') coreColor = '#1677FF';
  else if (status === 'SPEAKING') coreColor = '#7AA8FF';
  else if (status === 'LISTENING') coreColor = '#D7EEFF';
  else if (isPaused) coreColor = '#FF8A2A';
  else if (isError) coreColor = '#FF1744';

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animId: number;

    const render = () => {
      const width = canvas.width;
      const height = canvas.height;
      const cx = width / 2;
      const cy = height / 2;
      const r = Math.min(cx, cy) - 14;

      if (!reducedMotion && !isPaused) {
        angleRef.current += status === 'THINKING' ? 0.04 : 0.015;
        pulseRef.current += status === 'SPEAKING' ? 0.08 : 0.03;

        // Horizontal scan beam movement
        scanYRef.current += scanDirRef.current * 1.6;
        if (scanYRef.current > r * 0.75) scanDirRef.current = -1;
        if (scanYRef.current < -r * 0.75) scanDirRef.current = 1;
      }

      ctx.clearRect(0, 0, width, height);

      // 1. Outer Concentric Wireframe Rings
      ctx.save();
      ctx.strokeStyle = coreColor;
      ctx.lineWidth = 1;
      ctx.globalAlpha = 0.3;

      // Outer ring
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.stroke();

      // Dashed second ring
      ctx.setLineDash([4, 6]);
      ctx.beginPath();
      ctx.arc(cx, cy, r * 0.88, 0, Math.PI * 2);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.restore();

      // 2. Rotating Segmented Calipers / Outer Markers
      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate(angleRef.current * 0.5);
      ctx.strokeStyle = coreColor;
      ctx.lineWidth = 2;
      ctx.globalAlpha = 0.7;

      for (let i = 0; i < 4; i++) {
        ctx.rotate((Math.PI / 2));
        ctx.beginPath();
        ctx.arc(0, 0, r, -0.25, 0.25);
        ctx.stroke();

        // Tick mark
        ctx.beginPath();
        ctx.moveTo(r - 8, 0);
        ctx.lineTo(r + 2, 0);
        ctx.stroke();
      }
      ctx.restore();

      // 3. Counter-rotating Inner Compass Ticks
      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate(-angleRef.current * 0.7);
      ctx.strokeStyle = coreColor;
      ctx.globalAlpha = 0.35;
      ctx.lineWidth = 1;

      for (let i = 0; i < 16; i++) {
        const theta = (i / 16) * Math.PI * 2;
        const x1 = Math.cos(theta) * (r * 0.82);
        const y1 = Math.sin(theta) * (r * 0.82);
        const x2 = Math.cos(theta) * (r * 0.88);
        const y2 = Math.sin(theta) * (r * 0.88);
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.stroke();
      }
      ctx.restore();

      // 4. Central Geometric Core Projection (3D Octahedron / Diamond Wireframe)
      ctx.save();
      ctx.translate(cx, cy);

      const breathingScale = 1.0 + Math.sin(pulseRef.current) * (status === 'SPEAKING' ? 0.08 : 0.035);
      const coreR = r * 0.42 * breathingScale;

      ctx.rotate(angleRef.current);

      // Diamond nodes
      const points = [
        { x: 0, y: -coreR },
        { x: coreR * 0.86, y: -coreR * 0.25 },
        { x: coreR * 0.86, y: coreR * 0.5 },
        { x: 0, y: coreR * 0.9 },
        { x: -coreR * 0.86, y: coreR * 0.5 },
        { x: -coreR * 0.86, y: -coreR * 0.25 },
      ];

      // Draw facet lines
      ctx.strokeStyle = coreColor;
      ctx.lineWidth = 1.5;
      ctx.shadowColor = coreColor;
      ctx.shadowBlur = 12;
      ctx.globalAlpha = 0.85;

      ctx.beginPath();
      points.forEach((pt, idx) => {
        if (idx === 0) ctx.moveTo(pt.x, pt.y);
        else ctx.lineTo(pt.x, pt.y);
      });
      ctx.closePath();
      ctx.stroke();

      // Internal cross struts to center
      ctx.lineWidth = 1;
      ctx.globalAlpha = 0.4;
      points.forEach((pt) => {
        ctx.beginPath();
        ctx.moveTo(0, 0);
        ctx.lineTo(pt.x, pt.y);
        ctx.stroke();
      });

      // Center glowing reactor dot
      ctx.beginPath();
      ctx.arc(0, 0, 7, 0, Math.PI * 2);
      ctx.fillStyle = coreColor;
      ctx.shadowBlur = 16;
      ctx.fill();

      ctx.restore();

      // 5. Horizontal Holographic Scanning Laser Beam
      if (!isPaused) {
        ctx.save();
        ctx.translate(cx, cy);
        const beamY = scanYRef.current;
        const beamWidth = Math.sqrt(Math.max(0, r * r * 0.7 - beamY * beamY));

        const beamGrad = ctx.createLinearGradient(-beamWidth, beamY, beamWidth, beamY);
        beamGrad.addColorStop(0, 'rgba(0, 240, 255, 0)');
        beamGrad.addColorStop(0.5, coreColor);
        beamGrad.addColorStop(1, 'rgba(0, 240, 255, 0)');

        ctx.strokeStyle = beamGrad;
        ctx.lineWidth = 2;
        ctx.shadowColor = coreColor;
        ctx.shadowBlur = 8;
        ctx.beginPath();
        ctx.moveTo(-beamWidth, beamY);
        ctx.lineTo(beamWidth, beamY);
        ctx.stroke();
        ctx.restore();
      }

      animId = requestAnimationFrame(render);
    };

    render();

    return () => {
      cancelAnimationFrame(animId);
    };
  }, [status, coreColor, isPaused, reducedMotion]);

  return (
    <div className="relative w-[360px] h-[360px] hud-panel rounded-3xl p-5 flex flex-col justify-between items-center hud-glow select-none pointer-events-auto">
      {/* Top Core Title and State Badge */}
      <div className="w-full flex justify-between items-center z-10">
        <div>
          <h2 className="hud-title text-sm font-extrabold tracking-widest text-[#00B8FF] text-glow">
            BECKIE CORE
          </h2>
          <span className="text-[10px] text-[#7AA8FF] mono-val uppercase block">
            CENTRAL AI REACTOR
          </span>
        </div>
        <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#1677FF]/10 border border-[#00B8FF]/40">
          <span
            className="w-2 h-2 rounded-full animate-pulse"
            style={{ backgroundColor: coreColor, boxShadow: `0 0 8px ${coreColor}` }}
          />
          <span className="hud-title text-xs font-bold text-glow" style={{ color: coreColor }}>
            {status}
          </span>
        </div>
      </div>

      {/* Main Center Canvas AI Visualization */}
      <div className="relative flex-1 flex items-center justify-center my-1 w-full">
        <canvas
          ref={canvasRef}
          width={240}
          height={240}
          className="w-[240px] h-[240px] pointer-events-none"
        />
      </div>

      {/* Bottom Metadata Badges */}
      <div className="w-full z-10 pt-2 border-t border-[#1677FF]/30 grid grid-cols-3 gap-2 text-center text-[10px] mono-val">
        <div className="bg-[#030716]/80 p-1.5 rounded border border-[#1677FF]/30">
          <span className="text-[#6A92BA] block text-[9px]">MODEL</span>
          <span className="text-[#00B8FF] font-semibold truncate block">
            {modelName.split(' ')[0] || 'QWEN3'}
          </span>
        </div>

        <div className="bg-[#030716]/80 p-1.5 rounded border border-[#1677FF]/30">
          <span className="text-[#6A92BA] block text-[9px]">LATENCY</span>
          <span className="text-[#00B8FF] font-bold">
            {latencyMs !== null ? `${Math.round(latencyMs)}ms` : 'N/A'}
          </span>
        </div>

        <div className="bg-[#030716]/80 p-1.5 rounded border border-[#1677FF]/30">
          <span className="text-[#6A92BA] block text-[9px]">MODE</span>
          <span className="text-[#7AA8FF] font-semibold">{mode}</span>
        </div>
      </div>
    </div>
  );
};

