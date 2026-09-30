/**
 * App.tsx – BECKIE 3D HUD Interface Main Assembly
 *
 * Implements Blue-and-Red Holographic Operating Theme with Fixed Responsive HUD Grid:
 * 1. Top-Left Identity Zone (Branding & Status Capsule)
 * 2. Top-Center Latency & Time Zone
 * 3. Top-Right Global Controls Zone ([LOGS] [SETTINGS] [PAUSE ALL])
 * 4. Left GPU Telemetry Circle (GpuModule with 5-blade fan & strict units)
 * 5. Center Beckie Core (AI reactor visualization)
 * 6. Right CPU Telemetry Circle (CpuModule with 7-blade fan & strict units)
 * 7. Bottom-Left Privacy Controls (Mic, Tracking, Mode)
 * 8. Bottom-Right Affective State Panel
 */

import React, { useEffect } from 'react';
import { useJarvisStore } from './store/useJarvisStore';
import { HUDScene } from './components/3d/HUDScene';
import { IdentityCard } from './components/hud/IdentityCard';
import { TopCenterModeDisplay } from './components/hud/TopCenterModeDisplay';
import { GlobalControls } from './components/hud/GlobalControls';
import { GpuModule } from './components/hud/GpuModule';
import { CpuModule } from './components/hud/CpuModule';
import { BottomStatusPanels } from './components/hud/BottomStatusPanels';
import { AffectiveStatePanel } from './components/hud/AffectiveStatePanel';
import { DetailPopover } from './components/overlay/DetailPopover';
import { SettingsPanel } from './components/overlay/SettingsPanel';
import { LogsPanel } from './components/overlay/LogsPanel';
import { CalendarTasksPanel } from './components/overlay/CalendarTasksPanel';
import { SpotifyHoloPlayer } from './components/overlay/SpotifyHoloPlayer';
import { WeekAgenda3D } from './components/hud/WeekAgenda3D';
import { getModeTheme } from './utils/themeUtils';
import { useAvatarStore } from './stores/avatarStore';
import { AvatarScene } from './components/avatar/AvatarScene';
import { HolographicSpeechBubble } from './components/avatar/HolographicSpeechBubble';
import { AvatarInspectionPanel } from './components/avatar/AvatarInspectionPanel';
import { AvatarSettingsPanel } from './components/avatar/AvatarSettingsPanel';

export const App: React.FC = () => {
  const {
    pollTelemetry,
    gpu,
    cpu,
    beckie,
    reducedMotion,
    setSelectedMetric,
    activeModeOverride,
    setActiveModeOverride,
  } = useJarvisStore();

  const isPaused = beckie.status === 'PAUSED';

  // Active theme calculation
  const hardwareMode = cpu.performanceMode?.mode || gpu.performanceMode?.mode || 'Balanced';
  const effectiveMode = activeModeOverride || hardwareMode;
  const theme = getModeTheme(effectiveMode);

  // 1-second telemetry polling loop
  useEffect(() => {
    pollTelemetry();
    const interval = setInterval(() => {
      pollTelemetry();
    }, 1000);
    return () => clearInterval(interval);
  }, [pollTelemetry]);

  // Load avatar state and discover local 3D assets on startup
  useEffect(() => {
    useAvatarStore.getState().loadInitialState();
  }, []);

  return (
    <div
      className="relative w-screen h-screen bg-[#030716] overflow-hidden select-none transition-colors duration-700"
      data-mode={theme.key}
    >
      {/* Dynamic Mode Ambient Lighting Aura */}
      <div
        className="mode-ambient-aura absolute inset-0 pointer-events-none z-[1] transition-all duration-700"
        style={{ background: theme.ambientGradient }}
      />

      {/* Sci-Fi Scanlines Texture Overlay */}
      <div className="scanlines absolute inset-0 pointer-events-none z-10 opacity-60" />

      {/* Background Three.js Starfield & Radar Grid with Mode Color Sync */}
      <HUDScene themeHex={theme.hexThree} />

      {/* BECKIE Local 3D Holographic Avatar Canvas */}
      <AvatarScene themeHex={theme.hexThree} themeColor={theme.accentColor} />

      {/* ZONE 1: Top-Left Identity Card */}
      <IdentityCard />

      {/* ZONE 2: Dedicated Top-Center Alienware Mode Command Box */}
      <TopCenterModeDisplay
        activeModeOverride={activeModeOverride}
        onSelectMode={setActiveModeOverride}
      />

      {/* ZONE 3: Top-Right Global Controls */}
      <GlobalControls />

      {/* ZONE 4: Left Telemetry Circle – GPU Holographic Fan */}
      <div className="hud-zone-left-circle flex items-center justify-center">
        <GpuModule
          telemetry={gpu}
          isPaused={isPaused}
          reducedMotion={reducedMotion}
          onClick={() => setSelectedMetric('gpu')}
        />
      </div>

      {/* ZONE 6: Right Telemetry Circle – CPU Holographic Fan */}
      <div className="hud-zone-right-circle flex items-center justify-center">
        <CpuModule
          telemetry={cpu}
          isPaused={isPaused}
          reducedMotion={reducedMotion}
          onClick={() => setSelectedMetric('cpu')}
        />
      </div>

      {/* ZONE 7: Bottom-Left Privacy Controls */}
      <BottomStatusPanels />

      {/* ZONE 8: Bottom-Right Inferred Affective State Panel */}
      <AffectiveStatePanel />

      {/* ZONE 9: 3D Holographic Week Agenda Command Deck */}
      <WeekAgenda3D />

      {/* Interactive 2D Overlays */}
      <DetailPopover />
      <SettingsPanel />
      <LogsPanel />
      <CalendarTasksPanel />
      <SpotifyHoloPlayer />

      {/* BECKIE Avatar Subtitle Bubble and Modal Panels */}
      <HolographicSpeechBubble themeColor={theme.accentColor} />
      <AvatarInspectionPanel />
      <AvatarSettingsPanel />
    </div>
  );
};


export default App;
