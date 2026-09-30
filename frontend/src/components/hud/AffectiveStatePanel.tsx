/**
 * AffectiveStatePanel.tsx – Zone 8: Bottom-Right Affective State Panel
 *
 * Implements:
 * - Position: right 24px, bottom 26px, width 285px
 * - Title: INFERRED AFFECTIVE STATE
 * - Disclaimer: "Inferred conversational affect • Local compute only" (not a medical diagnosis)
 * - Graceful fallback when emotion detection is disabled
 */

import React from 'react';
import { useJarvisStore } from '../../store/useJarvisStore';
import { Sparkles, HeartOff } from 'lucide-react';

export const AffectiveStatePanel: React.FC = () => {
  const { beckie, emotionEnabled, neutralMode } = useJarvisStore();

  const emotion = beckie.emotion_state;
  const isAvailable = emotionEnabled && !neutralMode && emotion !== null;

  return (
    <div
      style={{
        position: 'absolute',
        right: '24px',
        bottom: '26px',
        width: '285px',
        zIndex: 20,
      }}
      className="hud-panel rounded-2xl p-3.5 hud-glow pointer-events-auto select-none mono-val text-xs text-[#D7EEFF]"
    >
      {/* Header */}
      <div className="flex justify-between items-center mb-1.5 pb-1 border-b border-[#1677FF]/30">
        <div className="flex items-center gap-1.5">
          <Sparkles className="w-3.5 h-3.5 text-[#00B8FF] animate-pulse" />
          <h3 className="hud-title text-[11px] font-bold tracking-widest text-[#00B8FF] text-glow uppercase">
            INFERRED AFFECTIVE STATE
          </h3>
        </div>
        {isAvailable && (
          <span className="text-[9px] text-[#00B8FF] font-bold">
            {Math.round(emotion.confidence * 100)}% CONF
          </span>
        )}
      </div>

      {isAvailable ? (
        <div className="space-y-2">
          {/* Emotion Categorical Labels */}
          <div className="flex gap-1.5 flex-wrap">
            {emotion.labels.map((lbl) => (
              <span
                key={lbl}
                className="px-2 py-0.5 rounded bg-[#1677FF]/20 border border-[#00B8FF]/40 text-[#00B8FF] text-[9px] uppercase font-bold tracking-wider"
              >
                {lbl}
              </span>
            ))}
          </div>

          {/* VAD Coordinate Meters */}
          <div className="space-y-1">
            {/* Valence */}
            <div className="flex justify-between text-[9px]">
              <span className="opacity-75 text-[#6A92BA]">VALENCE (SENTIMENT)</span>
              <span className="font-bold text-[#D7EEFF]">{emotion.valence.toFixed(2)}</span>
            </div>
            <div className="w-full bg-[#030716] h-1.5 rounded-full overflow-hidden border border-[#1677FF]/30">
              <div
                className="bg-[#00B8FF] h-full transition-all duration-500 shadow-[0_0_8px_#00B8FF]"
                style={{
                  width: `${Math.max(0, Math.min(100, ((emotion.valence + 1) / 2) * 100))}%`,
                }}
              />
            </div>

            {/* Arousal */}
            <div className="flex justify-between text-[9px] pt-0.5">
              <span className="opacity-75 text-[#6A92BA]">AROUSAL (INTENSITY)</span>
              <span className="font-bold text-[#D7EEFF]">{emotion.arousal.toFixed(2)}</span>
            </div>
            <div className="w-full bg-[#030716] h-1.5 rounded-full overflow-hidden border border-[#1677FF]/30">
              <div
                className="bg-[#7AA8FF] h-full transition-all duration-500 shadow-[0_0_8px_#7AA8FF]"
                style={{
                  width: `${Math.max(0, Math.min(100, emotion.arousal * 100))}%`,
                }}
              />
            </div>
          </div>
        </div>
      ) : (
        <div className="py-2.5 flex items-center gap-2 text-gray-400">
          <HeartOff className="w-4 h-4 text-gray-500" />
          <div className="text-[10px] leading-tight">
            {neutralMode
              ? 'Neutral Mode Active (Zero affect adaptation)'
              : 'Emotion inference suspended by user preference'}
          </div>
        </div>
      )}

      {/* Mandatory Disclaimer Note */}
      <div className="mt-2.5 pt-1.5 border-t border-[#1677FF]/20 text-[8px] text-[#6A92BA] leading-tight">
        Inferred conversational affect · Local compute only · Not a clinical or psychological diagnosis.
      </div>
    </div>
  );
};
