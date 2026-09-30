/**
 * AvatarSettingsPanel.tsx – User Consent, Revocable Permissions & Performance Controls
 *
 * Implements Section 7 Controls:
 * - Enable Avatar toggle
 * - Ambient motion toggle (Off by default)
 * - Procedural hover toggle (Off by default)
 * - Flight behavior toggle (Off by default, strict unrigged warnings)
 * - Weapon pose toggle (Off by default, non-combat warnings)
 * - Reduced motion accessibility override
 * - Suspend under heavy system load
 * - Quality selector (Low / Balanced / High)
 * - Reset position to Center Core Dock
 */

import React from 'react';
import {
  X,
  Sliders,
  Shield,
  Wind,
  Feather,
  Sword,
  EyeOff,
  Gauge,
  RotateCcw,
  Inspect,
  Volume2,
} from 'lucide-react';
import { useAvatarStore } from '../../stores/avatarStore';
import { AvatarQuality } from '../../types/avatar';

export const AvatarSettingsPanel: React.FC = () => {
  const {
    settingsOpen,
    setSettingsOpen,
    setInspectionOpen,
    permissions,
    updatePermissions,
    resetAvatarPosition,
    manifest,
  } = useAvatarStore();

  if (!settingsOpen) return null;

  const isUnrigged = !manifest?.hasSkeleton;

  const handleQualityChange = (quality: AvatarQuality) => {
    updatePermissions({ quality });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4">
      <div className="relative w-full max-w-2xl bg-[#030716] border border-cyan-500/40 rounded-2xl shadow-[0_0_50px_rgba(0,184,255,0.25)] flex flex-col overflow-hidden text-slate-200 font-sans">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-cyan-500/30 bg-gradient-to-r from-cyan-950/40 via-blue-950/20 to-transparent">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-cyan-500/10 border border-cyan-400/30 text-cyan-400">
              <Sliders className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold tracking-wider text-cyan-300 font-mono">
                BECKIE AVATAR BEHAVIOR & PERMISSIONS
              </h2>
              <p className="text-xs text-slate-400">
                Configure procedural motion, hardware safety, and user consent policies
              </p>
            </div>
          </div>
          <button
            onClick={() => setSettingsOpen(false)}
            className="p-2 rounded-lg hover:bg-white/10 text-slate-400 hover:text-white transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 overflow-y-auto space-y-6 max-h-[75vh] text-sm">
          {/* Master Enable */}
          <div className="flex items-center justify-between p-4 rounded-xl bg-slate-900/60 border border-cyan-500/30">
            <div>
              <div className="font-bold text-slate-100 flex items-center gap-2">
                <Shield className="w-4 h-4 text-cyan-400" />
                Enable 3D Avatar Rendering
              </div>
              <p className="text-xs text-slate-400 mt-1">
                Displays the local holographic 3D model inside the HUD core aperture.
              </p>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={permissions.enabled}
                onChange={(e) => updatePermissions({ enabled: e.target.checked })}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-slate-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-cyan-500"></div>
            </label>
          </div>

          {/* Behavior Toggles */}
          <div className="space-y-3">
            <h3 className="text-xs font-mono text-cyan-400 font-bold uppercase tracking-wider">
              Procedural Motion & Autonomous Behavior
            </h3>

            {/* Ambient Movement */}
            <div className="flex items-center justify-between p-3 rounded-lg bg-slate-950/60 border border-slate-800">
              <div className="flex items-start gap-3">
                <Wind className="w-5 h-5 text-cyan-400 shrink-0 mt-0.5" />
                <div>
                  <div className="font-bold text-slate-200">Ambient Navigation Schedule</div>
                  <div className="text-xs text-slate-400">
                    Periodically moves avatar between safe observation waypoints (15-45s deterministic schedule).
                  </div>
                </div>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={permissions.ambientMovement}
                  onChange={(e) => updatePermissions({ ambientMovement: e.target.checked })}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-slate-800 rounded-full peer peer-checked:after:translate-x-full peer-checked:bg-cyan-500 after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all"></div>
              </label>
            </div>

            {/* Procedural Hover */}
            <div className="flex items-center justify-between p-3 rounded-lg bg-slate-950/60 border border-slate-800">
              <div className="flex items-start gap-3">
                <Feather className="w-5 h-5 text-cyan-400 shrink-0 mt-0.5" />
                <div>
                  <div className="font-bold text-slate-200">Procedural Vertical Bobbing & Hover</div>
                  <div className="text-xs text-slate-400">
                    Gentle organic levitation wave in 3D space. Safe for static models.
                  </div>
                </div>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={permissions.proceduralHover}
                  onChange={(e) => updatePermissions({ proceduralHover: e.target.checked })}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-slate-800 rounded-full peer peer-checked:after:translate-x-full peer-checked:bg-cyan-500 after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all"></div>
              </label>
            </div>

            {/* Flight Behavior */}
            <div className="flex items-center justify-between p-3 rounded-lg bg-slate-950/60 border border-slate-800">
              <div className="flex items-start gap-3">
                <Feather className="w-5 h-5 text-blue-400 shrink-0 mt-0.5" />
                <div>
                  <div className="font-bold text-slate-200">Flight Trajectory Arcs</div>
                  <div className="text-xs text-slate-400">
                    Use high-altitude Bezier paths when repositioning across HUD zones.
                  </div>
                  {isUnrigged && (
                    <div className="text-[11px] text-amber-400 mt-0.5">
                      ⚠️ Note: Unrigged model uses rigid glider glide (wing flapping disabled).
                    </div>
                  )}
                </div>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={permissions.flightBehavior}
                  onChange={(e) => updatePermissions({ flightBehavior: e.target.checked })}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-slate-800 rounded-full peer peer-checked:after:translate-x-full peer-checked:bg-cyan-500 after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all"></div>
              </label>
            </div>

            {/* Weapon Pose */}
            <div className="flex items-center justify-between p-3 rounded-lg bg-slate-950/60 border border-slate-800">
              <div className="flex items-start gap-3">
                <Sword className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
                <div>
                  <div className="font-bold text-slate-200">Safe Weapon Display Pose</div>
                  <div className="text-xs text-slate-400">
                    Display blade equipment in a neutral, non-threatening idle stance.
                  </div>
                  <div className="text-[11px] text-emerald-400 mt-0.5">
                    ✓ Strictly ceremonial. Combat/offensive animations permanently disabled.
                  </div>
                </div>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={permissions.weaponPose}
                  onChange={(e) => updatePermissions({ weaponPose: e.target.checked })}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-slate-800 rounded-full peer peer-checked:after:translate-x-full peer-checked:bg-cyan-500 after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all"></div>
              </label>
            </div>
          </div>

          {/* Accessibility & Safety */}
          <div className="space-y-3">
            <h3 className="text-xs font-mono text-cyan-400 font-bold uppercase tracking-wider">
              Accessibility & Hardware Protection
            </h3>

            {/* Reduced Motion */}
            <div className="flex items-center justify-between p-3 rounded-lg bg-slate-950/60 border border-slate-800">
              <div className="flex items-start gap-3">
                <EyeOff className="w-5 h-5 text-slate-400 shrink-0 mt-0.5" />
                <div>
                  <div className="font-bold text-slate-200">Reduced Motion Mode</div>
                  <div className="text-xs text-slate-400">
                    Locks avatar to Center Core Dock. Disables travel, bobbing, and camera tilting.
                  </div>
                </div>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={permissions.reducedMotion}
                  onChange={(e) => updatePermissions({ reducedMotion: e.target.checked })}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-slate-800 rounded-full peer peer-checked:after:translate-x-full peer-checked:bg-cyan-500 after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all"></div>
              </label>
            </div>

            {/* Suspend Under Load */}
            <div className="flex items-center justify-between p-3 rounded-lg bg-slate-950/60 border border-slate-800">
              <div className="flex items-start gap-3">
                <Gauge className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
                <div>
                  <div className="font-bold text-slate-200">Suspend Under Heavy Load</div>
                  <div className="text-xs text-slate-400">
                    Automatically pauses 3D rendering if Alienware hardware triggers thermal throttling or VRAM &gt; 90%.
                  </div>
                </div>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={permissions.suspendUnderLoad}
                  onChange={(e) => updatePermissions({ suspendUnderLoad: e.target.checked })}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-slate-800 rounded-full peer peer-checked:after:translate-x-full peer-checked:bg-cyan-500 after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all"></div>
              </label>
            </div>
          </div>

          {/* Quality Selector */}
          <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono text-cyan-400 font-bold uppercase">
                Render Quality & LOD
              </span>
              <span className="text-xs text-slate-400 font-mono">Current: {permissions.quality}</span>
            </div>
            <div className="grid grid-cols-3 gap-2 pt-1 font-mono text-xs">
              {(['Low', 'Balanced', 'High'] as AvatarQuality[]).map((q) => (
                <button
                  key={q}
                  onClick={() => handleQualityChange(q)}
                  className={`py-2 px-3 rounded-lg border text-center font-bold transition-all ${
                    permissions.quality === q
                      ? 'border-cyan-400 bg-cyan-950/60 text-cyan-300 shadow-[0_0_12px_rgba(0,184,255,0.3)]'
                      : 'border-slate-800 bg-slate-950/40 text-slate-400 hover:border-slate-700'
                  }`}
                >
                  {q}
                </button>
              ))}
            </div>
          </div>

          {/* Action Row */}
          <div className="flex items-center justify-between pt-2">
            <button
              onClick={() => {
                setSettingsOpen(false);
                setInspectionOpen(true);
              }}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-cyan-950/80 border border-cyan-500/40 text-cyan-300 hover:bg-cyan-900 text-xs font-mono font-bold transition-colors"
            >
              <Inspect className="w-4 h-4" />
              INSPECT ASSET SKELETON & MESH
            </button>

            <button
              onClick={resetAvatarPosition}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-900 border border-slate-700 text-slate-300 hover:bg-slate-800 text-xs font-mono font-bold transition-colors"
            >
              <RotateCcw className="w-4 h-4 text-cyan-400" />
              RESET TO CENTER DOCK
            </button>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-cyan-500/20 bg-slate-950/80 flex justify-end">
          <button
            onClick={() => setSettingsOpen(false)}
            className="px-6 py-2 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 text-xs font-mono font-bold transition-colors shadow-[0_0_20px_rgba(0,184,255,0.4)]"
          >
            SAVE & CLOSE
          </button>
        </div>
      </div>
    </div>
  );
};
