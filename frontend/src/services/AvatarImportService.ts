/**
 * AvatarImportService.ts – Local Asset Discovery, FBX Import & Blender Conversion Pipeline
 *
 * Implements strict local-only import security:
 * - Searches only approved local folders:
 *   <project-root>/assets/avatars/beckie/source/
 *   <project-root>/assets/avatars/beckie/generated/
 * - Prefers .glb and .gltf
 * - Handles FBX discovery (MidPoly.fbx) and copy-to-source approval dialog
 * - Headless Blender detection and conversion
 * - Validates local path integrity (rejects traversal '..', rejects remote URLs)
 * - Never executes arbitrary scripts alongside 3D assets
 * - Preserves original source assets completely untouched
 */

import {
  DiscoveredAsset,
  BlenderDetectionInfo,
  ConversionPreviewInfo,
  ConversionReportInfo,
} from '../types/avatar';
import { isTauri } from './tauriBridge';

export class AvatarImportService {
  private static BASE_API = 'http://127.0.0.1:8000/api/avatar';

  /**
   * Discover candidate 3D assets in approved project directories.
   */
  public static async discoverAssets(): Promise<DiscoveredAsset[]> {
    if (isTauri()) {
      try {
        const { invoke } = await import('@tauri-apps/api/core');
        const nativeAssets = await invoke<any[]>('discover_avatar_assets');
        if (Array.isArray(nativeAssets) && nativeAssets.length > 0) {
          return nativeAssets.map((a) => ({
            fileName: a.file_name,
            relativePath: a.relative_path,
            format: a.format,
            sizeBytes: Math.round((a.size_mb || 0) * 1024 * 1024),
            sizeMb: a.size_mb,
            isRuntimeReady: a.is_runtime_ready,
            isLarge: a.is_large,
            location: a.folder_label,
          }));
        }
      } catch (err) {
        console.warn(
          '[AvatarImportService] Tauri discover command failed, falling back to local REST API:',
          err
        );
      }
    }

    try {
      const res = await fetch(`${this.BASE_API}/discover`);
      if (res.ok) {
        const data = await res.json();
        return data.assets || [];
      }
    } catch (err) {
      console.warn('[AvatarImportService] Failed to query local discovery endpoint:', err);
    }

    return [];
  }

  /**
   * Validate asset path against traversal, remote URLs, and format restrictions.
   */
  public static async validateAssetPath(
    path: string
  ): Promise<{ isValid: boolean; error?: string }> {
    if (!path || typeof path !== 'string') {
      return { isValid: false, error: 'Path cannot be empty' };
    }

    const lower = path.toLowerCase();
    if (
      lower.startsWith('http://') ||
      lower.startsWith('https://') ||
      lower.startsWith('ftp://')
    ) {
      return {
        isValid: false,
        error: 'Remote URLs are strictly prohibited. Local 3D assets only.',
      };
    }

    if (path.includes('..')) {
      return {
        isValid: false,
        error: 'Path traversal sequence (..) detected and rejected.',
      };
    }

    try {
      const res = await fetch(`${this.BASE_API}/validate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path }),
      });
      if (res.ok) {
        const data = await res.json();
        return { isValid: data.isValid, error: data.error };
      }
    } catch (err) {
      console.warn('[AvatarImportService] Validation endpoint error:', err);
    }

    return { isValid: true };
  }

  /**
   * Detect Blender installation on local machine.
   */
  public static async detectBlender(): Promise<BlenderDetectionInfo> {
    try {
      const res = await fetch(`${this.BASE_API}/blender-status`);
      if (res.ok) {
        return await res.json();
      }
    } catch (err) {
      console.warn('[AvatarImportService] Failed to check Blender status:', err);
    }

    return {
      isAvailable: false,
      blenderPath: null,
      blenderVersion: null,
      instructions:
        'Blender is required to convert MidPoly.fbx to GLB. Install Blender or import a GLB file.',
    };
  }

  /**
   * Get preview summary before conversion.
   */
  public static async getConversionPreview(
    sourcePath: string
  ): Promise<ConversionPreviewInfo | null> {
    try {
      const res = await fetch(`${this.BASE_API}/convert-preview`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sourcePath }),
      });
      if (res.ok) {
        const data = await res.json();
        return data.preview;
      }
    } catch (err) {
      console.warn('[AvatarImportService] Failed to get conversion preview:', err);
    }
    return null;
  }

  /**
   * Run headless Blender conversion.
   */
  public static async convertFbxToGlb(
    sourcePath: string
  ): Promise<{ success: boolean; report?: ConversionReportInfo; error?: string }> {
    try {
      const res = await fetch(`${this.BASE_API}/convert`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sourcePath, userApproved: true }),
      });
      const data = await res.json();
      if (res.ok) {
        return { success: true, report: data.report };
      }
      return {
        success: false,
        error: data.detail || 'Conversion failed. Check local diagnostics.',
      };
    } catch (err: any) {
      return {
        success: false,
        error: err.message || 'Could not connect to conversion service.',
      };
    }
  }

  /**
   * Safely import an approved asset (e.g. MidPoly.fbx from root) into assets/avatars/beckie/source/
   */
  public static async importSourceAsset(
    sourcePath: string,
    targetName: string = 'MidPoly.fbx'
  ): Promise<{ success: boolean; importedPath?: string; error?: string }> {
    try {
      const res = await fetch(`${this.BASE_API}/import-file`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sourcePath, targetName, userApproved: true }),
      });
      const data = await res.json();
      if (res.ok) {
        return { success: true, importedPath: data.importedPath };
      }
      return { success: false, error: data.detail || 'Asset import failed' };
    } catch (err: any) {
      return { success: false, error: err.message || 'Asset import request failed' };
    }
  }

  /**
   * Fetch the latest conversion report.
   */
  public static async getConversionReport(): Promise<ConversionReportInfo | null> {
    try {
      const res = await fetch(`${this.BASE_API}/conversion-report`);
      if (res.ok) {
        const data = await res.json();
        return data.report;
      }
    } catch (err) {
      console.warn('[AvatarImportService] Failed to fetch conversion report:', err);
    }
    return null;
  }

  /**
   * Get safe stream URL for local GLB/GLTF model.
   */
  public static getAssetStreamUrl(relativePath: string): string {
    return `${this.BASE_API}/asset-file?path=${encodeURIComponent(relativePath)}`;
  }
}
