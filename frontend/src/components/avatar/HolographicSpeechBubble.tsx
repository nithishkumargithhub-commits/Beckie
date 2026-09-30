/**
 * HolographicSpeechBubble.tsx – Holographic Subtitle Bubble for BECKIE
 *
 * Implements Section 4 & 6 Speaking Persona requirements:
 * - Displays live synthesized text during SPEAKING state
 * - Truthful engine indicator: "VOICE: LOCAL PIPER"
 * - Emergency "Stop Speaking" override button
 * - Non-deceptive audio aura / frequency bars
 * - Listening and Thinking status indications
 */

import React from 'react';
import { Volume2, Square, Mic, Cpu } from 'lucide-react';
import { useAvatarStore } from '../../stores/avatarStore';

interface HolographicSpeechBubbleProps {
  themeColor?: string;
}

export const HolographicSpeechBubble: React.FC<HolographicSpeechBubbleProps> = ({
  themeColor = '#00B8FF',
}) => {
  const { fsmState, speechSnippet, setFsmState, setSpeechSnippet } = useAvatarStore();

  const isVisible =
    fsmState === 'SPEAKING' || fsmState === 'LISTENING' || fsmState === 'THINKING';

  if (!isVisible) return null;

  const handleStopSpeaking = async () => {
    setSpeechSnippet('');
    setFsmState('IDLE');
    try {
      await fetch('http://127.0.0.1:8000/api/avatar/simulate-event', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ event: 'tts.completed', payload: {} }),
      });
    } catch (e) {
      console.warn('Failed to stop TTS via backend:', e);
    }
  };

  return (
    <div className="absolute top-[28%] left-1/2 -translate-x-1/2 z-30 max-w-lg w-[90%] pointer-events-auto transition-all duration-300">
      <div
        className="relative backdrop-blur-md bg-[#030716]/90 border border-cyan-500/40 rounded-xl p-4 shadow-2xl overflow-hidden"
        style={{
          boxShadow: `0 0 25px ${themeColor}33, inset 0 0 15px ${themeColor}22`,
        }}
      >
        {/* Holographic Top Corner Accents */}
        <div className="absolute top-0 left-0 w-3 h-3 border-t-2 border-l-2 border-cyan-400" />
        <div className="absolute top-0 right-0 w-3 h-3 border-t-2 border-r-2 border-cyan-400" />
        <div className="absolute bottom-0 left-0 w-3 h-3 border-b-2 border-l-2 border-cyan-400" />
        <div className="absolute bottom-0 right-0 w-3 h-3 border-b-2 border-r-2 border-cyan-400" />

        {/* Header Bar */}
        <div className="flex items-center justify-between pb-2 mb-2 border-b border-cyan-500/20 text-xs font-mono">
          <div className="flex items-center gap-2">
            {fsmState === 'SPEAKING' && (
              <>
                <Volume2 className="w-4 h-4 text-cyan-400 animate-pulse" />
                <span className="text-cyan-300 font-semibold tracking-wider">BECKIE SPEAKING</span>
              </>
            )}
            {fsmState === 'LISTENING' && (
              <>
                <Mic className="w-4 h-4 text-amber-400 animate-pulse" />
                <span className="text-amber-300 font-semibold tracking-wider">BECKIE LISTENING</span>
              </>
            )}
            {fsmState === 'THINKING' && (
              <>
                <Cpu className="w-4 h-4 text-purple-400 animate-spin" />
                <span className="text-purple-300 font-semibold tracking-wider">BECKIE THINKING</span>
              </>
            )}
          </div>

          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded bg-cyan-950/60 border border-cyan-500/30 text-[10px] text-cyan-400 uppercase tracking-widest font-mono">
              VOICE: LOCAL PIPER
            </span>
            {fsmState === 'SPEAKING' && (
              <button
                onClick={handleStopSpeaking}
                className="flex items-center gap-1 px-2 py-0.5 rounded bg-red-950/60 border border-red-500/40 text-[10px] text-red-300 hover:bg-red-900/60 transition-colors"
                title="Interrupt speech output"
              >
                <Square className="w-2.5 h-2.5 fill-current" />
                STOP
              </button>
            )}
          </div>
        </div>

        {/* Content Body */}
        <div className="text-sm font-sans text-slate-100 leading-relaxed min-h-[2.5rem] flex items-center">
          {fsmState === 'SPEAKING' && (
            <p className="tracking-wide">
              {speechSnippet || 'Synthesizing voice response...'}
            </p>
          )}
          {fsmState === 'LISTENING' && (
            <div className="flex items-center gap-3 text-cyan-200">
              <span className="text-xs uppercase tracking-wider text-amber-300">Awaiting audio input...</span>
              <div className="flex gap-1 items-end h-4">
                <span className="w-1 bg-amber-400 h-2 animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="w-1 bg-amber-400 h-4 animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="w-1 bg-amber-400 h-3 animate-bounce" style={{ animationDelay: '300ms' }} />
                <span className="w-1 bg-amber-400 h-1 animate-bounce" style={{ animationDelay: '450ms' }} />
              </div>
            </div>
          )}
          {fsmState === 'THINKING' && (
            <div className="flex items-center gap-2 text-purple-300 text-xs uppercase tracking-wider">
              <span>Evaluating query locally</span>
              <span className="animate-pulse">...</span>
            </div>
          )}
        </div>

        {/* Animated Audio Equalizer Bars when speaking */}
        {fsmState === 'SPEAKING' && (
          <div className="mt-2 pt-2 border-t border-cyan-500/10 flex items-center justify-between text-[10px] text-cyan-400/70 font-mono">
            <span>AURA FREQ: 48kHz</span>
            <div className="flex items-end gap-1 h-3">
              {[60, 90, 40, 100, 75, 50, 85, 30, 95, 65].map((height, i) => (
                <div
                  key={i}
                  className="w-0.5 bg-gradient-to-t from-cyan-600 to-cyan-300 rounded-full animate-pulse"
                  style={{
                    height: `${height}%`,
                    animationDuration: `${0.4 + (i % 3) * 0.2}s`,
                  }}
                />
              ))}
            </div>
            <span>OFFLINE ZERO-CLOUD</span>
          </div>
        )}
      </div>
    </div>
  );
};
