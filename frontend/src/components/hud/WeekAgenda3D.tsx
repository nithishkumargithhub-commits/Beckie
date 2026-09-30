/**
 * WeekAgenda3D.tsx – BECKIE 3D Holographic 7-Day Agenda Platform
 *
 * Implements:
 * - Direct 3D perspective holographic command deck on the main dashboard
 * - 7 dynamic day pillars (Today + 6 upcoming days) with depth layering
 * - Real-time sync with Google Calendar API (live events, times, locations)
 * - Interactive 3D mouse parallax tilt (rotateX, rotateY, translateZ)
 * - Blue-and-Red holographic sci-fi aesthetic with neon glow and hover lift
 */

import React, { useEffect, useState, useRef } from 'react';
import {
  CalendarDays,
  Clock,
  MapPin,
  RefreshCw,
  Plus,
  ChevronUp,
  ChevronDown,
  Sparkles,
  ExternalLink
} from 'lucide-react';
import { useJarvisStore } from '../../store/useJarvisStore';
import { WeekDayAgenda, WeekDayEvent } from '../../types/telemetry';

export const WeekAgenda3D: React.FC = () => {
  const {
    weekAgenda,
    weekLoading,
    fetchWeekAgenda,
    setCalendarOpen,
  } = useJarvisStore();

  const [isCollapsed, setIsCollapsed] = useState(false);
  const [selectedDayIndex, setSelectedDayIndex] = useState<number>(0);
  const [tilt, setTilt] = useState({ x: 0, y: 0 });
  const deckRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchWeekAgenda();
    const interval = setInterval(() => {
      fetchWeekAgenda();
    }, 30000); // 30-second background sync
    return () => clearInterval(interval);
  }, [fetchWeekAgenda]);

  // Handle interactive 3D mouse parallax
  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!deckRef.current || isCollapsed) return;
    const rect = deckRef.current.getBoundingClientRect();
    const xRel = (e.clientX - rect.left) / rect.width - 0.5; // -0.5 to 0.5
    const yRel = (e.clientY - rect.top) / rect.height - 0.5;
    setTilt({
      x: -yRel * 10, // rotateX degrees
      y: xRel * 14,  // rotateY degrees
    });
  };

  const handleMouseLeave = () => {
    setTilt({ x: 0, y: 0 });
  };

  const totalEvents = weekAgenda.reduce(
    (acc, day) => acc + (day.events?.length || 0),
    0
  );

  return (
    <div
      ref={deckRef}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      style={{
        position: 'absolute',
        left: '50%',
        bottom: '22px',
        transform: 'translateX(-50%)',
        zIndex: 25,
        width: 'min(760px, calc(100vw - 680px))',
        perspective: '1200px',
      }}
      className="pointer-events-auto select-none transition-all duration-300"
    >
      {/* 3D Tilted Command Deck Container */}
      <div
        style={{
          transformStyle: 'preserve-3d',
          transform: isCollapsed
            ? 'rotateX(0deg)'
            : `rotateX(${10 + tilt.x}deg) rotateY(${tilt.y}deg)`,
          transition: 'transform 0.15s cubic-bezier(0.2, 0.8, 0.2, 1)',
        }}
        className="rounded-2xl bg-[#061028]/85 border border-[#1677FF]/40 backdrop-blur-xl shadow-[0_12px_40px_rgba(0,184,255,0.22)] overflow-hidden"
      >
        {/* Holographic Header Bar */}
        <div className="flex items-center justify-between px-3.5 py-2 border-b border-[#1677FF]/30 bg-[#0a1840]/70">
          <div className="flex items-center gap-2">
            <CalendarDays className="w-3.5 h-3.5 text-[#00B8FF] animate-pulse" />
            <span className="hud-title text-[11px] font-bold tracking-wider text-[#D7EEFF]">
              CHRONO-DECK // 7-DAY AGENDA
            </span>
            <span className="px-2 py-0.5 rounded-full bg-[#1677FF]/20 border border-[#00B8FF]/40 text-[#00B8FF] text-[9px] font-mono font-bold tracking-wide">
              {totalEvents} {totalEvents === 1 ? 'PROTOCOL' : 'PROTOCOLS'}
            </span>
          </div>

          <div className="flex items-center gap-1">
            <button
              onClick={() => fetchWeekAgenda()}
              title="Sync Google Calendar"
              className="p-1 rounded text-[#6A92BA] hover:text-[#00B8FF] hover:bg-[#1677FF]/20 transition-all"
            >
              <RefreshCw
                className={`w-3 h-3 ${weekLoading ? 'animate-spin text-[#00B8FF]' : ''}`}
              />
            </button>

            <button
              onClick={() => setCalendarOpen(true)}
              title="Open Calendar Manager"
              className="flex items-center gap-1 px-2 py-0.5 rounded bg-[#1677FF]/20 hover:bg-[#1677FF]/40 border border-[#1677FF]/40 text-[#D7EEFF] hover:text-[#00B8FF] text-[10px] font-mono transition-all"
            >
              <Plus className="w-3 h-3 text-[#00B8FF]" />
              <span>EVENT</span>
            </button>

            <button
              onClick={() => setIsCollapsed(!isCollapsed)}
              title={isCollapsed ? 'Expand 3D Deck' : 'Collapse 3D Deck'}
              className="p-1 rounded text-[#6A92BA] hover:text-[#D7EEFF] hover:bg-[#1677FF]/20 transition-all"
            >
              {isCollapsed ? (
                <ChevronUp className="w-3.5 h-3.5" />
              ) : (
                <ChevronDown className="w-3.5 h-3.5" />
              )}
            </button>
          </div>
        </div>

        {/* 3D Pillars Row */}
        {!isCollapsed && (
          <div
            style={{
              transformStyle: 'preserve-3d',
            }}
            className="p-3 grid grid-cols-7 gap-2 bg-gradient-to-b from-[#030716]/60 to-[#061028]/90"
          >
            {weekAgenda.map((day: WeekDayAgenda, idx: number) => {
              const hasEvents = (day.events?.length || 0) > 0;
              const isSelected = selectedDayIndex === idx;

              return (
                <div
                  key={day.date}
                  onClick={() => setSelectedDayIndex(idx)}
                  style={{
                    transformStyle: 'preserve-3d',
                    transform: isSelected
                      ? 'translateZ(26px) translateY(-4px)'
                      : 'translateZ(10px)',
                    transition: 'all 0.25s cubic-bezier(0.2, 0.8, 0.2, 1)',
                  }}
                  className={`group relative rounded-xl p-2 cursor-pointer transition-all duration-200 border flex flex-col justify-between min-h-[110px] ${
                    day.is_today
                      ? 'bg-gradient-to-b from-[#1677FF]/25 to-[#061028]/90 border-[#00B8FF] shadow-[0_0_18px_rgba(0,184,255,0.35)]'
                      : isSelected
                      ? 'bg-[#1677FF]/20 border-[#1677FF] shadow-[0_0_15px_rgba(22,119,255,0.25)]'
                      : 'bg-[#030716]/75 border-[#1677FF]/25 hover:border-[#00B8FF]/60 hover:bg-[#1677FF]/15 hover:shadow-[0_0_14px_rgba(0,184,255,0.2)]'
                  }`}
                >
                  {/* Today Badge */}
                  {day.is_today && (
                    <div className="absolute -top-2 left-1/2 -translate-x-1/2 px-1.5 py-0.2 rounded-full bg-[#00B8FF] text-[#030716] font-mono text-[8px] font-black tracking-widest uppercase shadow-[0_0_8px_#00B8FF]">
                      TODAY
                    </div>
                  )}

                  {/* Day Header */}
                  <div className="text-center pt-0.5">
                    <div
                      className={`text-[10px] font-mono font-bold tracking-wider ${
                        day.is_today
                          ? 'text-[#00B8FF]'
                          : 'text-[#6A92BA] group-hover:text-[#D7EEFF]'
                      }`}
                    >
                      {day.day_short}
                    </div>
                    <div
                      className={`text-sm font-extrabold font-mono leading-none my-0.5 ${
                        day.is_today ? 'text-[#D7EEFF] text-glow' : 'text-[#D7EEFF]'
                      }`}
                    >
                      {day.day_num}
                    </div>
                    <div className="text-[8px] font-mono text-[#6A92BA] uppercase">
                      {day.month_short}
                    </div>
                  </div>

                  {/* Events Section in 3D Card */}
                  <div className="mt-1.5 flex-1 flex flex-col justify-center">
                    {hasEvents ? (
                      <div className="space-y-1">
                        {day.events.slice(0, 2).map((ev: WeekDayEvent, evIdx: number) => (
                          <div
                            key={ev.id || evIdx}
                            title={`${ev.summary} (${ev.time_str || 'All Day'})${ev.location ? ' @ ' + ev.location : ''}`}
                            className="p-1 rounded bg-[#00B8FF]/15 border border-[#00B8FF]/40 text-left shadow-[0_0_8px_rgba(0,184,255,0.25)] transition-all hover:bg-[#00B8FF]/30"
                          >
                            <div className="text-[9px] font-bold text-[#D7EEFF] truncate tracking-tight">
                              {ev.summary}
                            </div>
                            <div className="flex items-center gap-0.5 text-[8px] font-mono text-[#00B8FF]">
                              <Clock className="w-2.5 h-2.5 flex-shrink-0" />
                              <span className="truncate">{ev.time_str || 'All Day'}</span>
                            </div>
                          </div>
                        ))}
                        {day.events.length > 2 && (
                          <div className="text-[8px] font-mono text-center text-[#6A92BA]">
                            +{day.events.length - 2} more
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className="text-center py-2 opacity-35 group-hover:opacity-60 transition-opacity">
                        <div className="w-1.5 h-1.5 rounded-full bg-[#1677FF] mx-auto mb-1" />
                        <span className="text-[8px] font-mono text-[#6A92BA] block">
                          CLEAR
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Bottom Indicator Pill */}
                  <div className="pt-1 border-t border-[#1677FF]/15 flex items-center justify-center">
                    {hasEvents ? (
                      <span className="w-1.5 h-1.5 rounded-full bg-[#00B8FF] animate-ping" />
                    ) : (
                      <span className="w-1 h-1 rounded-full bg-[#6A92BA]/40" />
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Selected Day Quick Inspector (if selected day has events) */}
        {!isCollapsed && weekAgenda[selectedDayIndex]?.events?.length > 0 && (
          <div className="px-3.5 py-1.5 bg-[#030716]/90 border-t border-[#1677FF]/30 flex items-center justify-between text-[10px] font-mono text-[#6A92BA]">
            <div className="flex items-center gap-2 truncate">
              <span className="text-[#00B8FF] font-bold">
                {weekAgenda[selectedDayIndex].display_date}:
              </span>
              <span className="text-[#D7EEFF] font-bold truncate">
                {weekAgenda[selectedDayIndex].events[0].summary}
              </span>
              <span className="text-[#00B8FF]">
                ({weekAgenda[selectedDayIndex].events[0].time_str})
              </span>
              {weekAgenda[selectedDayIndex].events[0].location && (
                <span className="flex items-center gap-1 text-[#6A92BA] truncate">
                  <MapPin className="w-3 h-3 text-[#FF314F]" />
                  <span className="truncate">
                    {weekAgenda[selectedDayIndex].events[0].location}
                  </span>
                </span>
              )}
            </div>

            {weekAgenda[selectedDayIndex].events[0].htmlLink && (
              <a
                href={weekAgenda[selectedDayIndex].events[0].htmlLink}
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-1 text-[#00B8FF] hover:text-[#D7EEFF] hover:underline flex-shrink-0"
              >
                <span>OPEN</span>
                <ExternalLink className="w-3 h-3" />
              </a>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
