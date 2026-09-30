/**
 * GlobalControls.tsx – Zone 3: Top-Right Global Control Buttons
 *
 * Implements:
 * - Fixed layout: right 24px, top 18px, width 330px
 * - Buttons: [ LOGS ] [ SETTINGS ] [ EMERGENCY PAUSE ]
 * - Visually distinct Emergency Pause button with red tactical glow
 * - Flex layout with gaps, minimum widths, and zero collision with other elements
 */

import React from 'react';
import { Terminal, Sliders, AlertOctagon, Play, CalendarCheck, Music } from 'lucide-react';
import { useJarvisStore } from '../../store/useJarvisStore';

export const GlobalControls: React.FC = () => {
  const {
    setSettingsOpen,
    setLogsOpen,
    emergencyPause,
    resumeFromPause,
    beckie,
    calendarOpen,
    setCalendarOpen,
    spotifyOpen,
    setSpotifyOpen,
    spotify
  } = useJarvisStore();
  const isPaused = beckie.status === 'PAUSED';

  return (
    <div
      style={{
        position: 'absolute',
        right: '24px',
        top: '18px',
        zIndex: 20,
      }}
      className="flex items-center justify-end gap-2 pointer-events-auto select-none"
    >
      {/* Calendar & Tasks Button */}
      <button
        onClick={() => setCalendarOpen(!calendarOpen)}
        title="Google Calendar & Tasks Agenda"
        className={`px-3 py-2 rounded-xl hud-panel border text-xs font-bold mono-val flex items-center justify-center gap-1.5 transition-all shadow-[0_0_10px_rgba(22,119,255,0.2)] ${
          calendarOpen
            ? 'border-[#00B8FF] bg-[#1677FF]/30 text-[#00B8FF]'
            : 'border-[#1677FF]/40 hover:border-[#00B8FF] hover:bg-[#1677FF]/15 text-[#D7EEFF]'
        }`}
      >
        <CalendarCheck className="w-3.5 h-3.5 text-[#00B8FF]" />
        <span>AGENDA</span>
      </button>

      {/* Spotify Button */}
      <button
        onClick={() => setSpotifyOpen(!spotifyOpen)}
        title="Spotify Holographic Mini-Player"
        className={`px-3 py-2 rounded-xl hud-panel border text-xs font-bold mono-val flex items-center justify-center gap-1.5 transition-all shadow-[0_0_10px_rgba(22,119,255,0.2)] ${
          spotifyOpen || spotify.is_playing
            ? 'border-[#00B8FF] bg-[#1677FF]/30 text-[#00B8FF]'
            : 'border-[#1677FF]/40 hover:border-[#00B8FF] hover:bg-[#1677FF]/15 text-[#D7EEFF]'
        }`}
      >
        <Music className={`w-3.5 h-3.5 ${spotify.is_playing ? 'text-[#00B8FF] animate-pulse' : 'text-[#6A92BA]'}`} />
        <span>MUSIC</span>
      </button>

      {/* Logs Button */}
      <button
        onClick={() => setLogsOpen(true)}
        className="px-3 py-2 rounded-xl hud-panel border border-[#1677FF]/40 hover:border-[#00B8FF] hover:bg-[#1677FF]/15 text-xs font-bold mono-val text-[#D7EEFF] flex items-center justify-center gap-1.5 transition-all shadow-[0_0_10px_rgba(22,119,255,0.2)]"
      >
        <Terminal className="w-3.5 h-3.5 text-[#00B8FF]" />
        <span>LOGS</span>
      </button>

      {/* Settings Button */}
      <button
        onClick={() => setSettingsOpen(true)}
        className="px-3 py-2 rounded-xl hud-panel border border-[#1677FF]/40 hover:border-[#00B8FF] hover:bg-[#1677FF]/15 text-xs font-bold mono-val text-[#D7EEFF] flex items-center justify-center gap-1.5 transition-all shadow-[0_0_10px_rgba(22,119,255,0.2)]"
      >
        <Sliders className="w-3.5 h-3.5 text-[#00B8FF]" />
        <span>SETTINGS</span>
      </button>

      {/* Emergency Pause / Resume Button */}
      {isPaused ? (
        <button
          onClick={resumeFromPause}
          title="Resume Beckie Assistant"
          className="min-w-[125px] px-3 py-2 rounded-xl border border-[#00B8FF]/70 bg-[#00B8FF]/15 hover:bg-[#00B8FF]/25 text-[#00B8FF] text-xs font-bold mono-val flex items-center justify-center gap-1.5 transition-all shadow-[0_0_14px_rgba(0,184,255,0.35)] animate-pulse"
        >
          <Play className="w-3.5 h-3.5" />
          <span>RESUME</span>
        </button>
      ) : (
        <button
          onClick={emergencyPause}
          title="Emergency Pause (Halt All Microphones & Tracking)"
          className="min-w-[125px] px-3 py-2 rounded-xl border border-[#FF314F]/80 bg-[#FF314F]/20 hover:bg-[#FF314F]/35 text-[#FF314F] text-xs font-bold mono-val flex items-center justify-center gap-1.5 transition-all shadow-[0_0_14px_rgba(255,49,79,0.45)]"
        >
          <AlertOctagon className="w-3.5 h-3.5 animate-pulse" />
          <span>PAUSE ALL</span>
        </button>
      )}
    </div>
  );
};
