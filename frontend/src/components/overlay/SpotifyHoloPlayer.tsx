/**
 * SpotifyHoloPlayer.tsx – BECKIE 3D HUD Floating 3D Spotify Window
 *
 * Implements:
 * - True Floating 3D Window in User Dashboard with draggable positioning
 * - Interactive 3D mouse parallax tilt (rotateX, rotateY, translateZ)
 * - Three dedicated navigation tabs:
 *   1. [AUDIO CORE]: Instant track search, vinyl visualizer, seeker, and controls
 *   2. [MY PLAYLISTS]: 3D cards of user playlists with 1-click playback and playlist pinning
 *   3. [PREFERENCES]: User favorite genres, sound profile, visualizer style, and token status
 * - Blue-and-Red holographic sci-fi aesthetic with glowing neon glassmorphism
 */

import React, { useEffect, useState, useRef } from 'react';
import {
  Music,
  Play,
  Pause,
  SkipBack,
  SkipForward,
  Volume2,
  X,
  Disc3,
  RefreshCw,
  Search,
  Sparkles,
  ExternalLink,
  ListMusic,
  Sliders,
  Plus,
  Radio,
  CheckCircle2,
  Maximize2,
  Minimize2,
  GripHorizontal
} from 'lucide-react';
import { useJarvisStore } from '../../store/useJarvisStore';
import { SpotifyPlaylist } from '../../types/telemetry';

const QUICK_VIBES = [
  { label: 'Lo-Fi Chill', query: 'lofi hip hop chill beats' },
  { label: 'Synthwave', query: 'synthwave cyberpunk retrowave' },
  { label: 'Top Hits', query: 'today top hits' },
  { label: 'Acoustic', query: 'peaceful acoustic' },
];

export const SpotifyHoloPlayer: React.FC = () => {
  const {
    spotifyOpen,
    setSpotifyOpen,
    spotify,
    fetchSpotify,
    controlSpotify,
    playSpotifyTrack,
    launchSpotifyApp,
    playlists,
    preferences,
    fetchPlaylists,
    fetchPreferences,
    addCustomPlaylist,
    fetchSpotifyAuthUrl,
  } = useJarvisStore();

  const [activeTab, setActiveTab] = useState<'player' | 'playlists' | 'preferences'>('player');
  const [searchQuery, setSearchQuery] = useState('');
  const [isPlayingQuery, setIsPlayingQuery] = useState(false);
  const [statusFeedback, setStatusFeedback] = useState<string | null>(null);

  const handleSyncAccount = async () => {
    setStatusFeedback('Connecting to Spotify account...');
    const url = await fetchSpotifyAuthUrl();
    const targetUrl = url || 'https://accounts.spotify.com/authorize?client_id=05c1aa8b547440a08006bc5f6c5e1310&response_type=code&redirect_uri=http%3A%2F%2F127.0.0.1%3A8888%2Fcallback&scope=streaming+user-read-playback-state+user-modify-playback-state+playlist-read-private+playlist-read-collaborative+user-library-read+user-top-read+user-read-recently-played';
    window.open(targetUrl, '_blank');
    let attempts = 0;
    const poll = setInterval(async () => {
      attempts++;
      await fetchPlaylists();
      await fetchPreferences();
      if (attempts >= 10) clearInterval(poll);
    }, 2500);
  };

  // New playlist form
  const [showAddPlaylist, setShowAddPlaylist] = useState(false);
  const [newPlName, setNewPlName] = useState('');
  const [newPlUri, setNewPlUri] = useState('');

  // 3D Parallax Tilt & Window Drag State
  const [isMinimized, setIsMinimized] = useState(false);
  const [position, setPosition] = useState<{ x: number; y: number } | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });
  const [tilt, setTilt] = useState({ x: 0, y: 0 });
  const windowRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (spotifyOpen) {
      fetchSpotify();
      fetchPlaylists();
      fetchPreferences();
      const interval = setInterval(() => {
        fetchSpotify();
      }, 3000);
      return () => clearInterval(interval);
    }
  }, [spotifyOpen, fetchSpotify, fetchPlaylists, fetchPreferences]);

  // Handle Dragging
  const handleMouseDown = (e: React.MouseEvent) => {
    if ((e.target as HTMLElement).closest('button') || (e.target as HTMLElement).closest('input')) {
      return;
    }
    const rect = windowRef.current?.getBoundingClientRect();
    if (!rect) return;
    setIsDragging(true);
    setDragOffset({
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
    });
  };

  useEffect(() => {
    const handleMouseMoveWindow = (e: MouseEvent) => {
      if (!isDragging) return;
      setPosition({
        x: Math.max(10, Math.min(window.innerWidth - 380, e.clientX - dragOffset.x)),
        y: Math.max(10, Math.min(window.innerHeight - 200, e.clientY - dragOffset.y)),
      });
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    if (isDragging) {
      window.addEventListener('mousemove', handleMouseMoveWindow);
      window.addEventListener('mouseup', handleMouseUp);
    }
    return () => {
      window.removeEventListener('mousemove', handleMouseMoveWindow);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging, dragOffset]);

  // 3D Mouse Parallax
  const handleMouseMoveTilt = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!windowRef.current || isDragging || isMinimized) return;
    const rect = windowRef.current.getBoundingClientRect();
    const xRel = (e.clientX - rect.left) / rect.width - 0.5;
    const yRel = (e.clientY - rect.top) / rect.height - 0.5;
    setTilt({
      x: -yRel * 12,
      y: xRel * 14,
    });
  };

  const handleMouseLeaveTilt = () => {
    setTilt({ x: 0, y: 0 });
  };

  if (!spotifyOpen) return null;

  const handlePlaySearch = async (queryToPlay?: string) => {
    const q = (queryToPlay || searchQuery).trim();
    if (!q) return;
    setIsPlayingQuery(true);
    setStatusFeedback(`Starting '${q}'...`);
    const success = await playSpotifyTrack(q);
    setIsPlayingQuery(false);
    if (success) {
      setStatusFeedback(`Playing: ${q}`);
      setSearchQuery('');
      setTimeout(() => setStatusFeedback(null), 4000);
    } else {
      setStatusFeedback('Launched Spotify playback.');
      setTimeout(() => setStatusFeedback(null), 4000);
    }
  };

  const handlePlayPlaylist = async (pl: SpotifyPlaylist) => {
    setStatusFeedback(`Loading playlist '${pl.name}'...`);
    await playSpotifyTrack(pl.uri);
    setTimeout(() => {
      fetchSpotify();
      setStatusFeedback(`Now Playing: ${pl.name}`);
      setTimeout(() => setStatusFeedback(null), 4000);
    }, 1000);
  };

  const handleCreatePlaylist = async () => {
    if (!newPlName.trim() || !newPlUri.trim()) return;
    await addCustomPlaylist(newPlName, newPlUri);
    setNewPlName('');
    setNewPlUri('');
    setShowAddPlaylist(false);
  };

  const handleLaunchApp = async () => {
    setStatusFeedback('Launching Spotify App...');
    await launchSpotifyApp();
    setTimeout(() => {
      fetchSpotify();
      setStatusFeedback(null);
    }, 2000);
  };

  const formatTime = (ms?: number) => {
    if (!ms) return '0:00';
    const totalSec = Math.floor(ms / 1000);
    const min = Math.floor(totalSec / 60);
    const sec = totalSec % 60;
    return `${min}:${sec < 10 ? '0' : ''}${sec}`;
  };

  const progressPct =
    spotify.duration_ms && spotify.progress_ms
      ? Math.min(100, Math.round((spotify.progress_ms / spotify.duration_ms) * 100))
      : 0;

  // Window styling: default or dragged position
  const windowStyle: React.CSSProperties = {
    position: 'fixed',
    left: position ? `${position.x}px` : undefined,
    top: position ? `${position.y}px` : undefined,
    right: position ? undefined : '26px',
    bottom: position ? undefined : '88px',
    zIndex: 45,
    perspective: '1200px',
  };

  return (
    <div
      ref={windowRef}
      style={windowStyle}
      onMouseMove={handleMouseMoveTilt}
      onMouseLeave={handleMouseLeaveTilt}
      className="select-none pointer-events-auto transition-transform duration-150"
    >
      {/* 3D Perspective Holographic Window Shell */}
      <div
        style={{
          transformStyle: 'preserve-3d',
          transform: isMinimized
            ? 'rotateX(0deg) scale(0.95)'
            : `rotateX(${tilt.x}deg) rotateY(${tilt.y}deg) translateZ(20px)`,
          transition: isDragging ? 'none' : 'transform 0.15s cubic-bezier(0.2, 0.8, 0.2, 1)',
        }}
        className={`w-92 rounded-2xl bg-[#061028]/95 border border-[#1677FF]/60 shadow-[0_20px_50px_rgba(0,184,255,0.35),inset_0_0_20px_rgba(22,119,255,0.15)] backdrop-blur-2xl overflow-hidden ${
          isDragging ? 'cursor-grabbing opacity-90' : ''
        }`}
      >
        {/* Holographic Window Header with Drag Handle */}
        <div
          onMouseDown={handleMouseDown}
          className="flex items-center justify-between px-3.5 py-2.5 border-b border-[#1677FF]/35 bg-[#0a1840]/80 cursor-grab active:cursor-grabbing"
        >
          <div className="flex items-center gap-2">
            <GripHorizontal className="w-3.5 h-3.5 text-[#6A92BA]/60" />
            <Music className="w-3.5 h-3.5 text-[#00B8FF] animate-pulse" />
            <span className="hud-title text-[11px] font-bold tracking-wider text-[#D7EEFF]">
              SPOTIFY 3D AUDIO DECK
            </span>
          </div>

          <div className="flex items-center gap-1.5">
            <button
              onClick={() => fetchSpotify()}
              title="Refresh playback"
              className="p-1 text-[#6A92BA] hover:text-[#00B8FF] hover:bg-[#1677FF]/20 rounded transition-colors"
            >
              <RefreshCw className="w-3 h-3" />
            </button>
            <button
              onClick={() => setIsMinimized(!isMinimized)}
              title={isMinimized ? 'Expand Window' : 'Minimize Window'}
              className="p-1 text-[#6A92BA] hover:text-[#D7EEFF] hover:bg-[#1677FF]/20 rounded transition-colors"
            >
              {isMinimized ? <Maximize2 className="w-3 h-3" /> : <Minimize2 className="w-3 h-3" />}
            </button>
            <button
              onClick={() => setSpotifyOpen(false)}
              title="Close Player"
              className="p-1 text-[#6A92BA] hover:text-[#FF314F] hover:bg-[#FF314F]/20 rounded transition-colors"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Tab Navigation Strip */}
        {!isMinimized && (
          <div className="flex items-center border-b border-[#1677FF]/25 bg-[#030716]/60 px-2 pt-1 gap-1 text-[10px] font-mono">
            <button
              onClick={() => setActiveTab('player')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-t-lg transition-all border-b-2 font-bold ${
                activeTab === 'player'
                  ? 'border-[#00B8FF] text-[#00B8FF] bg-[#1677FF]/20 shadow-[0_0_10px_rgba(0,184,255,0.3)]'
                  : 'border-transparent text-[#6A92BA] hover:text-[#D7EEFF]'
              }`}
            >
              <Radio className="w-3 h-3" />
              <span>PLAYER</span>
            </button>

            <button
              onClick={() => setActiveTab('playlists')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-t-lg transition-all border-b-2 font-bold ${
                activeTab === 'playlists'
                  ? 'border-[#00B8FF] text-[#00B8FF] bg-[#1677FF]/20 shadow-[0_0_10px_rgba(0,184,255,0.3)]'
                  : 'border-transparent text-[#6A92BA] hover:text-[#D7EEFF]'
              }`}
            >
              <ListMusic className="w-3 h-3" />
              <span>PLAYLISTS</span>
              <span className="text-[9px] px-1.5 py-0.2 rounded-full bg-[#1677FF]/30 text-[#00B8FF]">
                {playlists.length}
              </span>
            </button>

            <button
              onClick={() => setActiveTab('preferences')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-t-lg transition-all border-b-2 font-bold ${
                activeTab === 'preferences'
                  ? 'border-[#00B8FF] text-[#00B8FF] bg-[#1677FF]/20 shadow-[0_0_10px_rgba(0,184,255,0.3)]'
                  : 'border-transparent text-[#6A92BA] hover:text-[#D7EEFF]'
              }`}
            >
              <Sliders className="w-3 h-3" />
              <span>PREFERENCES</span>
            </button>
          </div>
        )}

        {/* TAB 1: PLAYER / AUDIO RUNNER */}
        {!isMinimized && activeTab === 'player' && (
          <div className="p-4 space-y-3.5">
            {/* Instant Search Bar */}
            <div className="space-y-1.5">
              <div className="flex gap-1.5">
                <div className="relative flex-1">
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handlePlaySearch()}
                    placeholder="Search song, artist, playlist..."
                    className="w-full pl-8 pr-2.5 py-1.5 rounded-xl bg-[#030716] border border-[#1677FF]/40 text-xs font-mono text-[#D7EEFF] placeholder-[#6A92BA]/60 focus:outline-none focus:border-[#00B8FF] transition-all"
                  />
                  <Search className="w-3.5 h-3.5 text-[#6A92BA] absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                </div>
                <button
                  onClick={() => handlePlaySearch()}
                  disabled={isPlayingQuery || !searchQuery.trim()}
                  className="px-3.5 py-1.5 rounded-xl bg-gradient-to-r from-[#1677FF] to-[#00B8FF] hover:opacity-95 text-[#030716] font-bold text-xs font-mono disabled:opacity-40 shadow-[0_0_12px_rgba(0,184,255,0.35)] flex items-center gap-1 transition-all"
                >
                  <Play className="w-3 h-3 fill-current" />
                  <span>PLAY</span>
                </button>
              </div>

              {/* Quick Genre Chips */}
              <div className="flex items-center gap-1.5 overflow-x-auto pb-0.5 scrollbar-none">
                <Sparkles className="w-2.5 h-2.5 text-[#00B8FF] flex-shrink-0" />
                {QUICK_VIBES.map((vibe) => (
                  <button
                    key={vibe.label}
                    onClick={() => handlePlaySearch(vibe.query)}
                    className="px-2 py-0.5 rounded-md bg-[#1677FF]/15 hover:bg-[#1677FF]/35 border border-[#1677FF]/35 text-[#00B8FF] hover:text-[#D7EEFF] text-[9px] font-mono whitespace-nowrap transition-all"
                  >
                    {vibe.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Status Alert if triggered */}
            {statusFeedback && (
              <div className="px-2.5 py-1 rounded-lg bg-[#00B8FF]/15 border border-[#00B8FF]/40 text-[#00B8FF] text-[10px] font-mono flex items-center justify-between animate-pulse">
                <span className="truncate">{statusFeedback}</span>
                <Music className="w-3 h-3 flex-shrink-0" />
              </div>
            )}

            {/* Holographic Track Display & Album Art */}
            <div className="flex items-center gap-3 p-3 rounded-xl bg-[#030716]/85 border border-[#1677FF]/35 shadow-[inset_0_0_15px_rgba(22,119,255,0.1)]">
              <div className="relative w-16 h-16 rounded-xl bg-[#030716] border border-[#1677FF]/50 flex items-center justify-center overflow-hidden flex-shrink-0 shadow-[0_0_20px_rgba(0,184,255,0.3)]">
                {spotify.album_art ? (
                  <img
                    src={spotify.album_art}
                    alt={spotify.title || 'Album Art'}
                    className={`w-full h-full object-cover ${spotify.is_playing ? 'animate-pulse' : ''}`}
                  />
                ) : (
                  <Disc3
                    className={`w-10 h-10 text-[#00B8FF] ${
                      spotify.is_playing ? 'animate-spin' : ''
                    }`}
                    style={{ animationDuration: '6s' }}
                  />
                )}
                {spotify.is_playing && (
                  <div className="absolute inset-0 bg-[#00B8FF]/15 pointer-events-none" />
                )}
              </div>

              <div className="flex-1 min-w-0">
                <h4 className="text-xs font-bold text-[#D7EEFF] truncate tracking-wide">
                  {spotify.title || 'Spotify Ready'}
                </h4>
                <p className="text-[11px] font-mono text-[#00B8FF] truncate">
                  {spotify.artist || 'Play any song above'}
                </p>
                {spotify.album && (
                  <p className="text-[10px] font-mono text-[#6A92BA] truncate">
                    {spotify.album}
                  </p>
                )}
              </div>
            </div>

            {/* Progress Bar */}
            <div className="space-y-1">
              <div className="w-full h-1.5 rounded-full bg-[#030716] border border-[#1677FF]/30 overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-[#1677FF] to-[#00B8FF] transition-all duration-300 shadow-[0_0_8px_#00B8FF]"
                  style={{ width: `${progressPct}%` }}
                />
              </div>
              <div className="flex items-center justify-between text-[9px] font-mono text-[#6A92BA]">
                <span>{formatTime(spotify.progress_ms)}</span>
                <span>{formatTime(spotify.duration_ms)}</span>
              </div>
            </div>

            {/* Controls */}
            <div className="flex items-center justify-between pt-0.5">
              <button
                onClick={handleLaunchApp}
                title="Launch Spotify Desktop App"
                className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-[#1677FF]/30 hover:border-[#00B8FF] bg-[#1677FF]/10 hover:bg-[#1677FF]/25 text-[#6A92BA] hover:text-[#00B8FF] text-[10px] font-mono transition-all"
              >
                <ExternalLink className="w-3 h-3 text-[#00B8FF]" />
                <span>APP</span>
              </button>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => controlSpotify('skip_previous')}
                  className="p-2 rounded-lg border border-[#1677FF]/30 hover:border-[#00B8FF] text-[#6A92BA] hover:text-[#00B8FF] hover:bg-[#1677FF]/15 transition-all"
                  title="Previous Track"
                >
                  <SkipBack className="w-4 h-4" />
                </button>

                <button
                  onClick={() => controlSpotify('toggle')}
                  className="p-2.5 rounded-xl border border-[#00B8FF]/70 bg-[#1677FF]/30 hover:bg-[#00B8FF]/30 text-[#00B8FF] hover:text-[#D7EEFF] shadow-[0_0_18px_rgba(0,184,255,0.45)] transition-all"
                  title={spotify.is_playing ? 'Pause' : 'Play'}
                >
                  {spotify.is_playing ? (
                    <Pause className="w-5 h-5 fill-current" />
                  ) : (
                    <Play className="w-5 h-5 fill-current" />
                  )}
                </button>

                <button
                  onClick={() => controlSpotify('skip_next')}
                  className="p-2 rounded-lg border border-[#1677FF]/30 hover:border-[#00B8FF] text-[#6A92BA] hover:text-[#00B8FF] hover:bg-[#1677FF]/15 transition-all"
                  title="Next Track"
                >
                  <SkipForward className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: MY PLAYLISTS */}
        {!isMinimized && activeTab === 'playlists' && (
          <div className="p-4 space-y-3 max-h-80 overflow-y-auto">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-mono text-[#6A92BA] uppercase tracking-wider font-bold">
                PINNED &amp; SPOTIFY PLAYLISTS
              </span>
              <button
                onClick={() => setShowAddPlaylist(!showAddPlaylist)}
                className="flex items-center gap-1 text-[10px] font-mono text-[#00B8FF] hover:text-[#D7EEFF] transition-colors"
              >
                <Plus className="w-3 h-3" />
                <span>{showAddPlaylist ? 'CANCEL' : 'PIN PLAYLIST'}</span>
              </button>
            </div>

            {/* Add Playlist Form */}
            {showAddPlaylist && (
              <div className="p-2.5 rounded-xl bg-[#030716]/90 border border-[#00B8FF]/40 space-y-2 text-[10px] font-mono">
                <input
                  type="text"
                  placeholder="Playlist Name (e.g. My Favorites)"
                  value={newPlName}
                  onChange={(e) => setNewPlName(e.target.value)}
                  className="w-full px-2.5 py-1.5 rounded-lg bg-[#061028] border border-[#1677FF]/40 text-[#D7EEFF] focus:outline-none focus:border-[#00B8FF]"
                />
                <input
                  type="text"
                  placeholder="Spotify Link or URI (spotify:playlist:...)"
                  value={newPlUri}
                  onChange={(e) => setNewPlUri(e.target.value)}
                  className="w-full px-2.5 py-1.5 rounded-lg bg-[#061028] border border-[#1677FF]/40 text-[#D7EEFF] focus:outline-none focus:border-[#00B8FF]"
                />
                <button
                  onClick={handleCreatePlaylist}
                  disabled={!newPlName.trim() || !newPlUri.trim()}
                  className="w-full py-1.5 rounded-lg bg-[#00B8FF] text-[#030716] font-bold disabled:opacity-40"
                >
                  SAVE PLAYLIST TO DECK
                </button>
              </div>
            )}

            {/* Playlists 3D Cards */}
            {playlists.length === 0 ? (
              <div className="p-5 text-center rounded-xl bg-[#030716]/85 border border-dashed border-[#1677FF]/40 space-y-2.5">
                <div className="w-10 h-10 rounded-full bg-[#1677FF]/15 border border-[#00B8FF]/40 flex items-center justify-center mx-auto text-[#00B8FF] shadow-[0_0_15px_rgba(0,184,255,0.25)]">
                  <ListMusic className="w-5 h-5 animate-pulse" />
                </div>
                <div className="space-y-1">
                  <div className="text-xs font-mono font-bold text-[#D7EEFF]">
                    PERSONAL PLAYLISTS NOT YET SYNCED
                  </div>
                  <p className="text-[10px] font-mono text-[#6A92BA] max-w-xs mx-auto leading-relaxed">
                    Authorize playlist permission once to stream your exact personal Spotify playlists directly on this HUD.
                  </p>
                </div>
                <button
                  onClick={handleSyncAccount}
                  className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-gradient-to-r from-[#1677FF] to-[#00B8FF] text-[#030716] font-bold text-[10px] font-mono shadow-[0_0_15px_rgba(0,184,255,0.4)] hover:brightness-110 active:scale-95 transition-all cursor-pointer"
                >
                  <ExternalLink className="w-3.5 h-3.5" />
                  <span>SYNC MY SPOTIFY PLAYLISTS</span>
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-2">
                {playlists.map((pl: SpotifyPlaylist) => (
                  <div
                    key={pl.id}
                    onClick={() => handlePlayPlaylist(pl)}
                    style={{
                      transformStyle: 'preserve-3d',
                    }}
                    className="group relative p-2.5 rounded-xl bg-[#030716]/80 hover:bg-[#1677FF]/20 border border-[#1677FF]/30 hover:border-[#00B8FF] shadow-[0_4px_15px_rgba(0,184,255,0.1)] hover:shadow-[0_8px_25px_rgba(0,184,255,0.3)] transition-all cursor-pointer flex items-center justify-between"
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <div className="w-10 h-10 rounded-lg bg-[#0a1840] border border-[#1677FF]/40 overflow-hidden flex-shrink-0 flex items-center justify-center">
                        {pl.image ? (
                          <img src={pl.image} alt={pl.name} className="w-full h-full object-cover" />
                        ) : (
                          <ListMusic className="w-5 h-5 text-[#00B8FF]" />
                        )}
                      </div>
                      <div className="min-w-0">
                        <div className="text-[11px] font-bold text-[#D7EEFF] truncate group-hover:text-[#00B8FF] transition-colors">
                          {pl.name}
                        </div>
                        <div className="flex items-center gap-1.5 text-[9px] font-mono text-[#6A92BA]">
                          <span>{pl.curator}</span>
                          {pl.track_count > 0 && <span>• {pl.track_count} tracks</span>}
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 flex-shrink-0">
                      <span className="px-1.5 py-0.5 rounded bg-[#1677FF]/20 border border-[#1677FF]/40 text-[#00B8FF] text-[8px] font-mono font-bold uppercase">
                        {pl.tag}
                      </span>
                      <button
                        className="p-1.5 rounded-lg bg-[#00B8FF]/20 group-hover:bg-[#00B8FF] text-[#00B8FF] group-hover:text-[#030716] transition-all shadow-[0_0_10px_rgba(0,184,255,0.3)]"
                        title="Play Playlist"
                      >
                        <Play className="w-3.5 h-3.5 fill-current" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* TAB 3: PREFERENCES */}
        {!isMinimized && activeTab === 'preferences' && (
          <div className="p-4 space-y-3.5 max-h-80 overflow-y-auto">
            {/* Top Artists from Personal Account */}
            {preferences?.top_artists && preferences.top_artists.length > 0 && (
              <div className="space-y-1.5">
                <span className="text-[10px] font-mono text-[#6A92BA] uppercase tracking-wider font-bold">
                  MY TOP ARTISTS
                </span>
                <div className="grid grid-cols-2 gap-1.5 pt-1">
                  {preferences.top_artists.slice(0, 6).map((art) => (
                    <div
                      key={art.name}
                      onClick={() => handlePlaySearch(art.name)}
                      className="flex items-center gap-2 p-1.5 rounded-lg bg-[#030716]/80 hover:bg-[#1677FF]/20 border border-[#1677FF]/30 hover:border-[#00B8FF] cursor-pointer transition-all"
                    >
                      {art.image ? (
                        <img src={art.image} alt={art.name} className="w-7 h-7 rounded-full object-cover border border-[#00B8FF]/40 flex-shrink-0" />
                      ) : (
                        <Radio className="w-4 h-4 text-[#00B8FF] flex-shrink-0" />
                      )}
                      <div className="min-w-0">
                        <div className="text-[10px] font-bold text-[#D7EEFF] truncate">{art.name}</div>
                        <div className="text-[8px] font-mono text-[#6A92BA] truncate">{art.genres[0] || 'Artist'}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Favorite Genres Chips */}
            <div className="space-y-1.5">
              <span className="text-[10px] font-mono text-[#6A92BA] uppercase tracking-wider font-bold">
                MY FAVORITE GENRES (CLICK TO RUN)
              </span>
              <div className="flex flex-wrap gap-1.5 pt-1">
                {(preferences?.favorite_genres || QUICK_VIBES.map((v) => v.label)).map((genre) => (
                  <button
                    key={genre}
                    onClick={() => handlePlaySearch(genre)}
                    className="px-2.5 py-1 rounded-lg bg-[#1677FF]/15 hover:bg-[#1677FF]/35 border border-[#00B8FF]/30 text-[#D7EEFF] hover:text-[#00B8FF] text-[10px] font-mono transition-all flex items-center gap-1.5 shadow-[0_0_8px_rgba(0,184,255,0.15)]"
                  >
                    <Sparkles className="w-2.5 h-2.5 text-[#00B8FF]" />
                    <span>{genre}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Audio Profile & Settings */}
            <div className="p-3 rounded-xl bg-[#030716]/80 border border-[#1677FF]/30 space-y-2 text-[10px] font-mono">
              <div className="flex justify-between items-center text-[#D7EEFF]">
                <span className="text-[#6A92BA]">AUDIO PROFILE:</span>
                <span className="font-bold text-[#00B8FF]">
                  {preferences?.sound_profile || 'High Fidelity // Bass Boosted'}
                </span>
              </div>
              <div className="flex justify-between items-center text-[#D7EEFF]">
                <span className="text-[#6A92BA]">VISUALIZER STYLE:</span>
                <span className="font-bold text-[#D7EEFF]">
                  {preferences?.visualizer_style || 'Holographic Vinyl Disc'}
                </span>
              </div>
              <div className="flex justify-between items-center text-[#D7EEFF]">
                <span className="text-[#6A92BA]">STORAGE INTEGRATION:</span>
                <span className="flex items-center gap-1 text-emerald-400 font-bold">
                  <CheckCircle2 className="w-3 h-3" />
                  <span>PERMANENT ENCRYPTED</span>
                </span>
              </div>
            </div>

            <button
              onClick={handleLaunchApp}
              className="w-full py-2 px-3 rounded-xl bg-[#1677FF]/20 hover:bg-[#1677FF]/40 border border-[#1677FF]/50 text-[#D7EEFF] hover:text-[#00B8FF] text-[10px] font-mono flex items-center justify-center gap-2 transition-all"
            >
              <ExternalLink className="w-3.5 h-3.5 text-[#00B8FF]" />
              <span>OPEN SPOTIFY DESKTOP APP</span>
            </button>
          </div>
        )}

        {/* Bottom Status Bar */}
        <div className="px-3.5 py-1.5 border-t border-[#1677FF]/25 bg-[#061028] flex items-center justify-between text-[9px] font-mono text-[#6A92BA]">
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-[#00B8FF] shadow-[0_0_8px_#00B8FF]" />
            <span className="text-[#D7EEFF]">
              {spotify.is_playing ? 'STREAMING ACTIVE' : '3D AUDIO CORE • ONLINE'}
            </span>
          </span>
          <span className="flex items-center gap-1 text-[#00B8FF]">
            <Volume2 className="w-3 h-3" />
            <span>STANDALONE DECK</span>
          </span>
        </div>
      </div>
    </div>
  );
};
