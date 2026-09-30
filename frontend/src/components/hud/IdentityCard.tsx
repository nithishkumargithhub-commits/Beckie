/**
 * IdentityCard.tsx – Zone 1: Top-Left Branding & Status Capsule
 *
 * Implements:
 * - BECKIE // HUD 3D branding
 * - YOUR ALL-TIME COMPANION subtitle
 * - Non-overlapping connection/status capsule
 * - Fixed layout constraints: left 24px, top 18px, width 330px
 */

import React from 'react';
import { Radio } from 'lucide-react';
import { useJarvisStore } from '../../store/useJarvisStore';
import { AvatarStateBadge } from '../avatar/AvatarStateBadge';

export const IdentityCard: React.FC = () => {
  const { beckie } = useJarvisStore();
  const isPaused = beckie.status === 'PAUSED';

  return (
    <div
      style={{
        position: 'absolute',
        left: '24px',
        top: '18px',
        width: '330px',
        zIndex: 20,
      }}
      className="hud-panel rounded-2xl p-3.5 hud-glow pointer-events-auto select-none"
    >
      <div className="flex items-center gap-3">
        {/* Hologram Monogram Badge */}
        <div className="w-10 h-10 rounded-xl bg-[#1677FF]/15 border border-[#00B8FF]/60 flex items-center justify-center font-extrabold text-[#00B8FF] text-xl shadow-[0_0_12px_rgba(0,184,255,0.35)] shrink-0">
          B
        </div>

        <div className="flex-1 min-w-0">
          {/* Main Title */}
          <h1 className="hud-title text-sm font-black tracking-widest text-[#00B8FF] text-glow leading-none truncate">
            BECKIE // HUD 3D
          </h1>

          {/* Subtitle with readable uppercase spacing */}
          <div className="text-[10px] tracking-[0.16em] uppercase text-[#7AA8FF] font-bold mt-1 leading-tight truncate">
            YOUR ALL-TIME COMPANION
          </div>

          {/* Non-overlapping Connection Status Capsule & Avatar Badge */}
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#030716] border border-[#1677FF]/40 w-fit">
              <span className="relative flex h-2 w-2">
                <span
                  className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
                    isPaused ? 'bg-[#FF8A2A]' : 'bg-[#00B8FF]'
                  }`}
                />
                <span
                  className={`relative inline-flex rounded-full h-2 w-2 ${
                    isPaused ? 'bg-[#FF8A2A]' : 'bg-[#00B8FF]'
                  }`}
                />
              </span>
              <span className="text-[9px] mono-val uppercase tracking-wider text-[#D7EEFF] font-semibold">
                {isPaused ? 'TELEMETRY PAUSED' : 'ONLINE // 1s SYNC'}
              </span>
            </div>
            <AvatarStateBadge />
          </div>
        </div>
      </div>
    </div>
  );
};
