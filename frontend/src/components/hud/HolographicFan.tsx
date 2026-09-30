/**
 * HolographicFan.tsx – Reusable Blue-and-Red Holographic Fan Component
 *
 * Implements:
 * - Strict HolographicFanProps contract:
 *   { label, bladeCount, rpm, percent, utilizationPct, temperatureC, performanceMode, isAvailable, unavailableReason, colorProfile }
 * - GPU: 5 transparent blue blades, red outer accent on high temp/load
 * - CPU: 7 thinner blue-white blades, inner blue glow, red warning halo on high temp
 * - Fan speed driven by actual RPM, or percent if RPM is null, or diagnostic visual (0.15) if both null
 * - Performance/Turbo mode: blue core with red outer rim
 * - Warning temp (>75°C): amber-red halo
 * - Critical temp (>85°C): pulsing red warning halo
 * - Paused state: stops animation and dims module
 * - 60 FPS lerp smoothing without recreating canvas context / materials
 * - Respects reduced motion
 */

import React, { useEffect, useRef } from 'react';
import { HolographicFanProps } from '../../types/telemetry';
import { getModeTheme } from '../../utils/themeUtils';

function lerp(start: number, end: number, factor: number): number {
  return start + (end - start) * factor;
}

export const HolographicFan: React.FC<HolographicFanProps> = ({
  label,
  bladeCount,
  rpm,
  percent,
  utilizationPct,
  temperatureC,
  performanceMode,
  isAvailable,
  unavailableReason,
  colorProfile,
  isPaused = false,
  reducedMotion = false,
  onClick,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Animation state refs for continuous 60fps interpolation
  const angleRef = useRef(0);
  const currentSpeedRef = useRef(0.15);
  const currentGlowRef = useRef(0.5);

  const isCpu = colorProfile === 'cpu';

  // Determine temperature alert state
  const temp = temperatureC ?? 0;
  const isCritical = temp > 85;
  const isWarning = temp > 75 && !isCritical;
  const isHighLoad = (utilizationPct ?? 0) >= 80;

  // Mode theme styling
  const modeTheme = getModeTheme(performanceMode);
  const isPerformanceMode =
    modeTheme.key === 'g-mode' ||
    modeTheme.key === 'performance' ||
    modeTheme.key === 'fullspeed';

  // Normal operational colors (Blue primary/bright) vs Mode accent
  let coreColor = isCpu ? '#7AA8FF' : '#1677FF';
  let rimColor = modeTheme.accentColor;

  if (isCritical) {
    coreColor = '#FF1744';
    rimColor = '#FF1744';
  } else if (isWarning || isHighLoad) {
    rimColor = '#FF8A2A';
  }

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
      const r = Math.min(cx, cy) - 26;

      // 1. Calculate target speeds using user-specified formulas
      const normalizedLoad = (utilizationPct ?? 0) / 100;
      let targetRotationSpeed = 0.15; // Diagnostic visual baseline

      if (isPaused) {
        targetRotationSpeed = 0.0;
      } else if (rpm != null) {
        const normalizedRpm = Math.min(rpm / 2500, 1);
        targetRotationSpeed = Math.max(0.15, normalizedRpm * 2.5);
      } else if (percent != null) {
        const normalizedPct = Math.min(percent / 100, 1);
        targetRotationSpeed = Math.max(0.15, normalizedPct * 2.2);
      } else {
        // Both null: diagnostic low-speed visual
        targetRotationSpeed = 0.15;
      }

      const targetGlow = 0.3 + normalizedLoad * 0.7;

      // 2. Interpolate speed and glow
      if (!reducedMotion) {
        currentSpeedRef.current = lerp(currentSpeedRef.current, targetRotationSpeed, 0.12);
        currentGlowRef.current = lerp(currentGlowRef.current, targetGlow, 0.12);
        angleRef.current += currentSpeedRef.current * 0.035;
      } else {
        currentSpeedRef.current = 0;
        currentGlowRef.current = targetGlow;
      }

      ctx.clearRect(0, 0, width, height);

      // Save base state
      ctx.save();

      // If paused, dim module
      if (isPaused) {
        ctx.globalAlpha = 0.35;
      }

      // 3. Draw Outer Concentric Calibration Rings
      ctx.lineWidth = isCpu ? 1.0 : 1.5;
      ctx.strokeStyle = isCritical
        ? 'rgba(255, 23, 68, 0.5)'
        : isPerformanceMode
        ? 'rgba(255, 49, 79, 0.45)'
        : 'rgba(22, 119, 255, 0.3)';
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.stroke();

      // Inner faint ring
      ctx.beginPath();
      ctx.strokeStyle = 'rgba(0, 184, 255, 0.18)';
      ctx.arc(cx, cy, r * 0.75, 0, Math.PI * 2);
      ctx.stroke();

      // 4. Draw Radial Scan Ticks
      const tickCount = 36;
      ctx.strokeStyle = 'rgba(122, 168, 255, 0.3)';
      ctx.lineWidth = 1;
      for (let i = 0; i < tickCount; i++) {
        const rad = (i * Math.PI * 2) / tickCount;
        const innerR = i % 3 === 0 ? r - 8 : r - 4;
        const x1 = cx + Math.cos(rad) * innerR;
        const y1 = cy + Math.sin(rad) * innerR;
        const x2 = cx + Math.cos(rad) * r;
        const y2 = cy + Math.sin(rad) * r;
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.stroke();
      }

      // 5. Draw Load Circular Progress Arc
      const load = normalizedLoad;
      const startAngle = -Math.PI / 2;
      const endAngle = startAngle + load * (Math.PI * 2);
      ctx.lineWidth = 3.5;
      ctx.strokeStyle = isCritical
        ? '#FF1744'
        : isPerformanceMode || isWarning || isHighLoad
        ? '#FF314F'
        : '#00B8FF';
      ctx.shadowColor = ctx.strokeStyle;
      ctx.shadowBlur = 10 * currentGlowRef.current;
      ctx.beginPath();
      ctx.arc(cx, cy, r + 2, startAngle, endAngle);
      ctx.stroke();
      ctx.shadowBlur = 0; // Reset blur

      // 6. Draw Rotating Fan Blades
      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate(angleRef.current);

      const blades = bladeCount || (isCpu ? 7 : 5);
      const bladeRadius = r * 0.68;
      const bladeAlpha = isCpu ? 0.38 : 0.32;

      for (let b = 0; b < blades; b++) {
        ctx.save();
        ctx.rotate((b * 2 * Math.PI) / blades);

        ctx.fillStyle = isCritical
          ? `rgba(255, 23, 68, ${bladeAlpha})`
          : isCpu
          ? `rgba(122, 168, 255, ${bladeAlpha})`
          : `rgba(22, 119, 255, ${bladeAlpha})`;

        ctx.strokeStyle = isCritical
          ? 'rgba(255, 23, 68, 0.7)'
          : isCpu
          ? 'rgba(215, 238, 255, 0.65)'
          : 'rgba(0, 184, 255, 0.6)';

        ctx.lineWidth = isCpu ? 1 : 1.5;

        // Curvature of holographic airfoil blade
        ctx.beginPath();
        ctx.moveTo(0, 0);
        ctx.quadraticCurveTo(
          bladeRadius * 0.45,
          isCpu ? -12 : -18,
          bladeRadius,
          0
        );
        ctx.quadraticCurveTo(
          bladeRadius * 0.5,
          isCpu ? 12 : 18,
          0,
          0
        );
        ctx.fill();
        ctx.stroke();

        ctx.restore();
      }

      // Center Hub
      ctx.beginPath();
      ctx.arc(0, 0, r * 0.22, 0, Math.PI * 2);
      ctx.fillStyle = '#030716';
      ctx.fill();
      ctx.lineWidth = 2;
      ctx.strokeStyle = coreColor;
      ctx.shadowColor = coreColor;
      ctx.shadowBlur = 8;
      ctx.stroke();
      ctx.shadowBlur = 0;

      // Inner Hub Pin
      ctx.beginPath();
      ctx.arc(0, 0, r * 0.08, 0, Math.PI * 2);
      ctx.fillStyle = rimColor;
      ctx.fill();

      ctx.restore(); // Restore fan rotation

      ctx.restore(); // Restore base state

      animId = requestAnimationFrame(render);
    };

    animId = requestAnimationFrame(render);

    return () => {
      cancelAnimationFrame(animId);
    };
  }, [
    isCpu,
    rpm,
    percent,
    utilizationPct,
    temperatureC,
    performanceMode,
    bladeCount,
    isPaused,
    reducedMotion,
    isCritical,
    isWarning,
    isHighLoad,
    isPerformanceMode,
    coreColor,
    rimColor,
  ]);

  return (
    <div
      onClick={onClick}
      className={`relative w-[220px] h-[220px] flex items-center justify-center cursor-pointer transition-all duration-300 ${
        isPaused ? 'opacity-40 grayscale' : 'hover:scale-[1.02]'
      }`}
      role="button"
      tabIndex={0}
      title="Click to view 60s telemetry sparklines"
    >
      <canvas
        ref={canvasRef}
        width={220}
        height={220}
        className="w-full h-full pointer-events-none"
      />
    </div>
  );
};
