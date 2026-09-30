/**
 * avatarStore.ts – Zustand Store for Local Avatar State, Manifests, and Controls
 */

import { create } from 'zustand';
import {
  AvatarFsmState,
  AvatarManifest,
  AvatarPermissions,
  DiscoveredAsset,
  BlenderDetectionInfo,
  ConversionPreviewInfo,
  ConversionReportInfo,
  FlightTuning,
} from '../types/avatar';
import { AvatarAssetAnalyzer } from '../services/AvatarAssetAnalyzer';
import { AvatarImportService } from '../services/AvatarImportService';

interface AvatarStoreState {
  // Model and Manifest
  manifest: AvatarManifest | null;
  runtimeAssetPath: string | null;
  discoveredAssets: DiscoveredAsset[];
  isLoadingAsset: boolean;
  loadError: string | null;

  // FBX & Blender Conversion Pipeline
  blenderInfo: BlenderDetectionInfo | null;
  conversionPreview: ConversionPreviewInfo | null;
  conversionReport: ConversionReportInfo | null;
  isConverting: boolean;
  conversionError: string | null;
  rootFbxDiscovered: DiscoveredAsset | null;

  // Behavior & FSM
  fsmState: AvatarFsmState;
  speechSnippet: string;
  isVramPressureHigh: boolean;

  // Modals & Panels
  settingsOpen: boolean;
  inspectionOpen: boolean;
  importReviewOpen: boolean;

  // User Permissions
  permissions: AvatarPermissions;

  // Flight & Aerodynamic Kinematics Tuning
  flightTuning: FlightTuning;

  // Actions
  loadInitialState: () => Promise<void>;
  scanLocalAssets: () => Promise<void>;
  checkBlender: () => Promise<void>;
  loadConversionReport: () => Promise<void>;
  analyzeAndActivateAsset: (relativePath: string) => Promise<boolean>;
  convertFbxToGlb: (sourcePath: string) => Promise<boolean>;
  importFbxFromRoot: (sourcePath: string) => Promise<boolean>;
  updatePermissions: (updates: Partial<AvatarPermissions>) => Promise<void>;
  updateFlightTuning: (updates: Partial<FlightTuning>) => void;
  setFsmState: (state: AvatarFsmState) => void;
  setSpeechSnippet: (text: string) => void;
  setSettingsOpen: (open: boolean) => void;
  setInspectionOpen: (open: boolean) => void;
  setImportReviewOpen: (open: boolean) => void;
  resetAvatarPosition: () => void;
  resetToCenterTrigger: number;
}

const defaultPermissions: AvatarPermissions = {
  enabled: true,
  ambientMovement: false,
  proceduralHover: false,
  flightBehavior: false,
  weaponPose: false,
  reducedMotion: false,
  suspendUnderLoad: true,
  quality: 'Balanced',
  volume: 0.8,
  rememberChoice: false,
};

const defaultFlightTuning: FlightTuning = {
  wingSpeedMultiplier: 1.0,
  liftMultiplier: 1.0,
  dwellTimeMultiplier: 1.0,
  speechCalloutsEnabled: true,
  voiceAudioEnabled: false,
};

export const useAvatarStore = create<AvatarStoreState>((set, get) => ({
  manifest: null,
  runtimeAssetPath: 'assets/avatars/beckie/source/corrupted_archangel_six_wings_boss.glb',
  discoveredAssets: [],
  isLoadingAsset: false,
  loadError: null,

  blenderInfo: null,
  conversionPreview: null,
  conversionReport: null,
  isConverting: false,
  conversionError: null,
  rootFbxDiscovered: null,

  fsmState: 'IDLE',
  speechSnippet: '',
  isVramPressureHigh: false,
  flightTuning: defaultFlightTuning,

  updateFlightTuning: (updates) =>
    set((state) => ({
      flightTuning: { ...state.flightTuning, ...updates },
    })),

  settingsOpen: false,
  inspectionOpen: false,
  importReviewOpen: false,
  resetToCenterTrigger: 0,

  permissions: defaultPermissions,

  loadInitialState: async () => {
    // 1. Fetch manifest from backend
    try {
      const manifest = await AvatarAssetAnalyzer.fetchCurrentManifest();
      if (manifest) {
        set({ manifest, runtimeAssetPath: manifest.runtimeFile });
      }
    } catch (e) {
      console.warn('[avatarStore] No saved manifest found:', e);
    }

    // 2. Fetch permissions from backend state
    try {
      const res = await fetch('http://127.0.0.1:8000/api/avatar/state');
      if (res.ok) {
        const data = await res.json();
        if (data.state) {
          set({
            permissions: {
              enabled: data.state.enabled ?? true,
              ambientMovement: data.state.ambientMovement ?? false,
              proceduralHover: data.state.proceduralHover ?? false,
              flightBehavior: data.state.flightBehavior ?? false,
              weaponPose: data.state.weaponPose ?? false,
              reducedMotion: data.state.reducedMotion ?? false,
              suspendUnderLoad: data.state.suspendUnderLoad ?? true,
              quality: data.state.quality ?? 'Balanced',
              volume: data.state.volume ?? 0.8,
              rememberChoice: data.state.rememberChoice ?? false,
            },
          });
        }
      }
    } catch (e) {
      console.warn('[avatarStore] Failed to load permissions:', e);
    }

    // 3. Check Blender & load conversion report
    await get().checkBlender();
    await get().loadConversionReport();

    // 4. Scan for discovered local assets
    await get().scanLocalAssets();
  },

  scanLocalAssets: async () => {
    const assets = await AvatarImportService.discoverAssets();
    set({ discoveredAssets: assets });

    // Check if MidPoly.fbx exists in root or non-source folder
    const rootFbx = assets.find(
      (a) =>
        a.fileName.toLowerCase() === 'midpoly.fbx' &&
        !a.relativePath.includes('assets/avatars/beckie/source')
    );
    if (rootFbx) {
      set({ rootFbxDiscovered: rootFbx, importReviewOpen: true });
    }
  },

  checkBlender: async () => {
    const info = await AvatarImportService.detectBlender();
    set({ blenderInfo: info });
  },

  loadConversionReport: async () => {
    const report = await AvatarImportService.getConversionReport();
    if (report) {
      set({ conversionReport: report });
    }
  },

  convertFbxToGlb: async (sourcePath: string) => {
    set({ isConverting: true, conversionError: null });
    const res = await AvatarImportService.convertFbxToGlb(sourcePath);
    if (res.success && res.report) {
      set({
        isConverting: false,
        conversionReport: res.report,
        runtimeAssetPath: 'assets/avatars/beckie/generated/beckie-avatar.glb',
      });
      // Re-analyze generated GLB
      await get().analyzeAndActivateAsset('assets/avatars/beckie/generated/beckie-avatar.glb');
      return true;
    }

    set({
      isConverting: false,
      conversionError: res.error || 'Conversion failed. Check diagnostics.',
    });
    return false;
  },

  importFbxFromRoot: async (sourcePath: string) => {
    const res = await AvatarImportService.importSourceAsset(sourcePath, 'MidPoly.fbx');
    if (res.success) {
      set({ importReviewOpen: false, rootFbxDiscovered: null });
      await get().scanLocalAssets();
      return true;
    }
    return false;
  },

  analyzeAndActivateAsset: async (relativePath: string) => {
    set({ isLoadingAsset: true, loadError: null });

    const val = await AvatarImportService.validateAssetPath(relativePath);
    if (!val.isValid) {
      set({ isLoadingAsset: false, loadError: val.error || 'Invalid asset path' });
      return false;
    }

    const manifest = await AvatarAssetAnalyzer.analyzeAsset(relativePath);
    if (manifest) {
      set({
        manifest,
        runtimeAssetPath: manifest.runtimeFile,
        isLoadingAsset: false,
        fsmState: 'GREETING',
      });
      return true;
    }

    set({ isLoadingAsset: false, loadError: 'Asset analysis failed or unsupported format' });
    return false;
  },

  updatePermissions: async (updates: Partial<AvatarPermissions>) => {
    const updated = { ...get().permissions, ...updates };
    set({ permissions: updated });

    try {
      await fetch('http://127.0.0.1:8000/api/avatar/permissions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ permissions: updated, userApproved: true }),
      });
    } catch (e) {
      console.error('[avatarStore] Failed to persist permissions:', e);
    }
  },

  setFsmState: (fsmState) => set({ fsmState }),
  setSpeechSnippet: (speechSnippet) => set({ speechSnippet }),
  setSettingsOpen: (settingsOpen) => set({ settingsOpen }),
  setInspectionOpen: (inspectionOpen) => set({ inspectionOpen }),
  setImportReviewOpen: (importReviewOpen) => set({ importReviewOpen }),

  resetAvatarPosition: () => {
    set((s) => ({ resetToCenterTrigger: s.resetToCenterTrigger + 1, fsmState: 'IDLE' }));
  },
}));
