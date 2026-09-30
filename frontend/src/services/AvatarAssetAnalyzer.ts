/**
 * AvatarAssetAnalyzer.ts – Truthful 3D Asset Inspection and Capability Pipeline
 *
 * Implements truthful analysis without false claims of 'automatic training':
 * - Inspects scene hierarchy, mesh names, skeleton joints, animations, morph targets
 * - Computes truthful capability flags
 * - Enforces static ambient-only constraints when asset lacks rigging
 * - Persists and retrieves avatar-manifest.json
 */

import { AvatarManifest } from '../types/avatar';

export class AvatarAssetAnalyzer {
  private static BASE_API = 'http://127.0.0.1:8000/api/avatar';

  /**
   * Request comprehensive analysis of a local 3D model.
   */
  public static async analyzeAsset(relativePath: string): Promise<AvatarManifest | null> {
    try {
      const res = await fetch(`${this.BASE_API}/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: relativePath, relativePath }),
      });

      if (res.ok) {
        const data = await res.json();
        return data.manifest || null;
      }
    } catch (err) {
      console.error('[AvatarAssetAnalyzer] Asset analysis request failed:', err);
    }
    return null;
  }

  /**
   * Fetch current active avatar manifest from local disk.
   */
  public static async fetchCurrentManifest(): Promise<AvatarManifest | null> {
    try {
      const res = await fetch(`${this.BASE_API}/manifest`);
      if (res.ok) {
        const data = await res.json();
        return data.manifest || null;
      }
    } catch (err) {
      console.warn('[AvatarAssetAnalyzer] Failed to load current avatar manifest:', err);
    }
    return null;
  }
}
