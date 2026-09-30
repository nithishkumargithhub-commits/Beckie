/**
 * CalendarTasksPanel.tsx – BECKIE 3D HUD Holographic Calendar & Tasks Widget
 *
 * Implements:
 * - Live Google Calendar agenda display (times, titles, locations, links)
 * - Interactive Google Tasks checklist with real-time toggle and task creation
 * - Blue-and-Red Holographic HUD styling with glassmorphism and scanline accents
 */

import React, { useState, useEffect } from 'react';
import {
  Calendar as CalendarIcon,
  CheckSquare,
  Square,
  Clock,
  MapPin,
  ExternalLink,
  Plus,
  RefreshCw,
  X,
  CalendarCheck,
  ListTodo
} from 'lucide-react';
import { useJarvisStore } from '../../store/useJarvisStore';

export const CalendarTasksPanel: React.FC = () => {
  const {
    calendarOpen,
    setCalendarOpen,
    calendarEvents,
    tasks,
    calendarLoading,
    fetchCalendarEvents,
    fetchTasks,
    createCalendarEvent,
    createTask,
    toggleTask
  } = useJarvisStore();

  const [activeTab, setActiveTab] = useState<'calendar' | 'tasks'>('calendar');
  const [newEventTitle, setNewEventTitle] = useState('');
  const [newEventTime, setNewEventTime] = useState('');
  const [showEventForm, setShowEventForm] = useState(false);
  const [newTaskTitle, setNewTaskTitle] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (calendarOpen) {
      fetchCalendarEvents();
      fetchTasks();
    }
  }, [calendarOpen, fetchCalendarEvents, fetchTasks]);

  if (!calendarOpen) return null;

  const handleAddEvent = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newEventTitle.trim()) return;
    setIsSubmitting(true);
    await createCalendarEvent(newEventTitle.trim(), newEventTime.trim() || undefined);
    setNewEventTitle('');
    setNewEventTime('');
    setShowEventForm(false);
    setIsSubmitting(false);
  };

  const handleAddTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTaskTitle.trim()) return;
    setIsSubmitting(true);
    await createTask(newTaskTitle.trim());
    setNewTaskTitle('');
    setIsSubmitting(false);
  };

  const formatEventDate = (dateStr?: string) => {
    if (!dateStr) return 'TBD';
    try {
      const dt = new Date(dateStr);
      return dt.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
      });
    } catch {
      return dateStr;
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#030716]/80 backdrop-blur-md">
      <div
        className="relative w-full max-w-2xl max-h-[85vh] flex flex-col rounded-2xl bg-[#061028]/95 border border-[#1677FF]/50 shadow-[0_0_35px_rgba(22,119,255,0.3)] overflow-hidden"
        style={{
          boxShadow: '0 0 35px rgba(22, 119, 255, 0.25), inset 0 0 20px rgba(0, 184, 255, 0.08)',
        }}
      >
        {/* Holographic Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#1677FF]/30 bg-[#0a1840]/60">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-[#1677FF]/20 border border-[#00B8FF]/60 flex items-center justify-center text-[#00B8FF] shadow-[0_0_12px_rgba(0,184,255,0.4)]">
              {activeTab === 'calendar' ? <CalendarCheck className="w-4 h-4" /> : <ListTodo className="w-4 h-4" />}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-bold tracking-wider text-[#D7EEFF] uppercase">
                  BECKIE // SCHEDULE & TASKS
                </span>
                <span className="w-2 h-2 rounded-full bg-[#00B8FF] animate-pulse" />
              </div>
              <p className="text-[11px] font-mono text-[#6A92BA]">
                LIVE SYNCED • GOOGLE CLOUD OAUTH
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                fetchCalendarEvents();
                fetchTasks();
              }}
              title="Refresh"
              className="p-1.5 rounded-lg border border-[#1677FF]/30 hover:border-[#00B8FF] text-[#6A92BA] hover:text-[#00B8FF] hover:bg-[#1677FF]/15 transition-all"
            >
              <RefreshCw className={`w-4 h-4 ${calendarLoading ? 'animate-spin text-[#00B8FF]' : ''}`} />
            </button>
            <button
              onClick={() => setCalendarOpen(false)}
              className="p-1.5 rounded-lg border border-[#FF314F]/40 hover:border-[#FF314F] text-[#FF314F] hover:bg-[#FF314F]/15 transition-all"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Tab Switcher */}
        <div className="flex items-center px-6 pt-3 border-b border-[#1677FF]/20 bg-[#061028]/80 gap-3">
          <button
            onClick={() => setActiveTab('calendar')}
            className={`pb-2.5 px-3 text-xs font-bold font-mono tracking-wider flex items-center gap-2 border-b-2 transition-all ${
              activeTab === 'calendar'
                ? 'border-[#00B8FF] text-[#00B8FF] shadow-[0_4px_10px_rgba(0,184,255,0.3)]'
                : 'border-transparent text-[#6A92BA] hover:text-[#D7EEFF]'
            }`}
          >
            <CalendarIcon className="w-3.5 h-3.5" />
            <span>CALENDAR EVENTS ({calendarEvents.length})</span>
          </button>
          <button
            onClick={() => setActiveTab('tasks')}
            className={`pb-2.5 px-3 text-xs font-bold font-mono tracking-wider flex items-center gap-2 border-b-2 transition-all ${
              activeTab === 'tasks'
                ? 'border-[#00B8FF] text-[#00B8FF] shadow-[0_4px_10px_rgba(0,184,255,0.3)]'
                : 'border-transparent text-[#6A92BA] hover:text-[#D7EEFF]'
            }`}
          >
            <CheckSquare className="w-3.5 h-3.5" />
            <span>GOOGLE TASKS ({tasks.length})</span>
          </button>
        </div>

        {/* Panel Content Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4 max-h-[60vh]">
          {activeTab === 'calendar' ? (
            <div className="space-y-3">
              {/* Add Event Toggle / Form */}
              <div className="rounded-xl border border-[#1677FF]/30 bg-[#081534]/50 p-3">
                {!showEventForm ? (
                  <button
                    onClick={() => setShowEventForm(true)}
                    className="w-full py-2 px-3 rounded-lg border border-dashed border-[#1677FF]/40 hover:border-[#00B8FF] text-[#00B8FF] hover:bg-[#1677FF]/10 text-xs font-mono font-bold flex items-center justify-center gap-2 transition-all"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    <span>+ SCHEDULE NEW CALENDAR EVENT</span>
                  </button>
                ) : (
                  <form onSubmit={handleAddEvent} className="space-y-2.5">
                    <div className="flex items-center justify-between text-[11px] font-mono text-[#00B8FF] font-bold">
                      <span>QUICK SCHEDULE</span>
                      <button
                        type="button"
                        onClick={() => setShowEventForm(false)}
                        className="text-[#6A92BA] hover:text-[#FF314F]"
                      >
                        Cancel
                      </button>
                    </div>
                    <input
                      type="text"
                      placeholder="Event Title (e.g., Team Sync, Doctor Appointment)"
                      value={newEventTitle}
                      onChange={(e) => setNewEventTitle(e.target.value)}
                      className="w-full px-3 py-1.5 rounded-lg bg-[#030716] border border-[#1677FF]/50 text-xs text-[#D7EEFF] placeholder-[#6A92BA]/60 focus:outline-none focus:border-[#00B8FF]"
                    />
                    <input
                      type="text"
                      placeholder="When (e.g., tomorrow at 3pm, in 2 hours)"
                      value={newEventTime}
                      onChange={(e) => setNewEventTime(e.target.value)}
                      className="w-full px-3 py-1.5 rounded-lg bg-[#030716] border border-[#1677FF]/50 text-xs text-[#D7EEFF] placeholder-[#6A92BA]/60 focus:outline-none focus:border-[#00B8FF]"
                    />
                    <button
                      type="submit"
                      disabled={isSubmitting || !newEventTitle.trim()}
                      className="w-full py-2 rounded-lg bg-[#1677FF]/30 hover:bg-[#1677FF]/50 border border-[#00B8FF]/60 text-[#D7EEFF] text-xs font-mono font-bold flex items-center justify-center gap-2 transition-all disabled:opacity-50"
                    >
                      <Plus className="w-3.5 h-3.5 text-[#00B8FF]" />
                      <span>{isSubmitting ? 'SYNCING TO GOOGLE...' : 'ADD TO GOOGLE CALENDAR'}</span>
                    </button>
                  </form>
                )}
              </div>

              {/* Event Cards */}
              {calendarEvents.length === 0 ? (
                <div className="p-8 text-center text-xs font-mono text-[#6A92BA]">
                  No upcoming events scheduled on Google Calendar.
                </div>
              ) : (
                calendarEvents.map((ev) => (
                  <div
                    key={ev.id}
                    className="p-3.5 rounded-xl border border-[#1677FF]/30 bg-[#081534]/70 hover:border-[#00B8FF]/60 transition-all flex items-start justify-between gap-3 shadow-[0_0_15px_rgba(22,119,255,0.08)]"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-[#1677FF]/20 border border-[#00B8FF]/40 text-[#00B8FF] flex items-center gap-1">
                          <Clock className="w-2.5 h-2.5" />
                          {formatEventDate(ev.start)}
                        </span>
                      </div>
                      <h4 className="text-sm font-bold text-[#D7EEFF] tracking-wide">
                        {ev.summary}
                      </h4>
                      {ev.location && (
                        <p className="text-[11px] font-mono text-[#6A92BA] flex items-center gap-1">
                          <MapPin className="w-3 h-3 text-[#FF314F]" />
                          <span>{ev.location}</span>
                        </p>
                      )}
                    </div>

                    {ev.htmlLink && (
                      <a
                        href={ev.htmlLink}
                        target="_blank"
                        rel="noreferrer"
                        className="p-2 rounded-lg text-[#6A92BA] hover:text-[#00B8FF] hover:bg-[#1677FF]/15 transition-all"
                        title="Open in Google Calendar"
                      >
                        <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                    )}
                  </div>
                ))
              )}
            </div>
          ) : (
            <div className="space-y-3">
              {/* Quick Add Task */}
              <form onSubmit={handleAddTask} className="flex gap-2">
                <input
                  type="text"
                  placeholder="Add a new Google Task..."
                  value={newTaskTitle}
                  onChange={(e) => setNewTaskTitle(e.target.value)}
                  className="flex-1 px-3 py-2 rounded-xl bg-[#030716] border border-[#1677FF]/50 text-xs text-[#D7EEFF] placeholder-[#6A92BA]/60 focus:outline-none focus:border-[#00B8FF]"
                />
                <button
                  type="submit"
                  disabled={isSubmitting || !newTaskTitle.trim()}
                  className="px-4 py-2 rounded-xl bg-[#1677FF]/30 hover:bg-[#1677FF]/50 border border-[#00B8FF]/60 text-[#D7EEFF] text-xs font-mono font-bold flex items-center gap-1.5 transition-all disabled:opacity-50"
                >
                  <Plus className="w-3.5 h-3.5 text-[#00B8FF]" />
                  <span>ADD</span>
                </button>
              </form>

              {/* Task Items Checklist */}
              {tasks.length === 0 ? (
                <div className="p-8 text-center text-xs font-mono text-[#6A92BA]">
                  No active tasks found in your Google Tasks account.
                </div>
              ) : (
                <div className="space-y-2">
                  {tasks.map((task) => (
                    <div
                      key={task.id}
                      onClick={() => toggleTask(task.id, task.completed)}
                      className={`p-3 rounded-xl border transition-all flex items-start gap-3 cursor-pointer select-none ${
                        task.completed
                          ? 'border-[#1677FF]/15 bg-[#081534]/30 opacity-60'
                          : 'border-[#1677FF]/35 bg-[#081534]/70 hover:border-[#00B8FF]/70'
                      }`}
                    >
                      <button
                        type="button"
                        className="mt-0.5 text-[#00B8FF] hover:scale-110 transition-transform"
                      >
                        {task.completed ? (
                          <CheckSquare className="w-4 h-4 text-[#00B8FF]" />
                        ) : (
                          <Square className="w-4 h-4 text-[#6A92BA]" />
                        )}
                      </button>
                      <div className="flex-1">
                        <p
                          className={`text-xs font-medium tracking-wide ${
                            task.completed
                              ? 'line-through text-[#6A92BA]'
                              : 'text-[#D7EEFF]'
                          }`}
                        >
                          {task.title}
                        </p>
                        {task.notes && (
                          <p className="text-[11px] font-mono text-[#6A92BA]/80 mt-0.5">
                            {task.notes}
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer Status Line */}
        <div className="px-6 py-2.5 border-t border-[#1677FF]/20 bg-[#061028] flex items-center justify-between text-[10px] font-mono text-[#6A92BA]">
          <span>STATUS: REALTIME CLIENT ACTIVE</span>
          <span>PROTOCOL: HTTPS REST OAuth2</span>
        </div>
      </div>
    </div>
  );
};
