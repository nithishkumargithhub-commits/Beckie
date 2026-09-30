/**
 * AvatarScene.tsx – High-Performance Static 3D Avatar WebGL Canvas
 *
 * Implements:
 * - Centered static 3D holographic avatar in the HUD aperture
 * - Holographic base rings with smooth ambient rotation
 * - Dynamic mode lighting synchronization (G-Mode Red, Balanced Cyan, Quiet Emerald)
 * - Reactive speech aura and FSM state integration (Listening, Thinking, Speaking)
 * - Safe asset streaming with sub-second direct load and backend fallback
 * - Non-blocking pointer events (HUD controls remain fully responsive)
 */

import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { useAvatarStore } from '../../stores/avatarStore';
import { useJarvisStore } from '../../store/useJarvisStore';
import { AvatarController } from './AvatarController';
import { AvatarEventBridge } from '../../services/AvatarEventBridge';

interface AvatarSceneProps {
  themeHex?: number;
  themeColor?: string;
}

export const AvatarScene: React.FC<AvatarSceneProps> = ({
  themeHex = 0x00B8FF,
  themeColor = '#00B8FF',
}) => {
  const mountRef = useRef<HTMLDivElement>(null);
  const [loadProgress, setLoadProgress] = useState<number>(0);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const controllerRef = useRef<AvatarController | null>(null);

  const {
    permissions,
    manifest,
    fsmState,
    setFsmState,
    setSpeechSnippet,
    resetToCenterTrigger,
    runtimeAssetPath,
    setInspectionOpen,
  } = useAvatarStore();

  const permissionsRef = useRef(permissions);
  const fsmStateRef = useRef(fsmState);
  const themeHexRef = useRef(themeHex);

  useEffect(() => {
    permissionsRef.current = permissions;
  }, [permissions]);

  useEffect(() => {
    fsmStateRef.current = fsmState;
  }, [fsmState]);

  useEffect(() => {
    themeHexRef.current = themeHex;
  }, [themeHex]);

  useEffect(() => {
    const container = mountRef.current;
    if (!container) return;

    let isDisposed = false;
    let animationFrameId: number;

    // 1. Scene, Camera, and Lights
    const scene = new THREE.Scene();

    const camera = new THREE.PerspectiveCamera(
      45,
      container.clientWidth / container.clientHeight,
      0.1,
      100
    );
    camera.position.set(0, 0, 7.5);
    camera.lookAt(0, 0, 0);

    // 2. High-Performance WebGL Renderer
    const renderer = new THREE.WebGLRenderer({
      antialias: permissions.quality !== 'Low',
      alpha: true,
      powerPreference: 'high-performance',
    });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, permissions.quality === 'High' ? 2 : 1.5));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.2;

    container.appendChild(renderer.domElement);

    // 3. Holographic Lighting Setup
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.8);
    scene.add(ambientLight);

    const keyLight = new THREE.DirectionalLight(0xffffff, 1.3);
    keyLight.position.set(2, 4, 5);
    scene.add(keyLight);

    const rimLight = new THREE.PointLight(themeHex, 3.5, 15);
    rimLight.position.set(-3, 2, -2);
    scene.add(rimLight);

    const backRimLight = new THREE.PointLight(themeHex, 2.5, 12);
    backRimLight.position.set(3, -2, -3);
    scene.add(backRimLight);

    const auraLight = new THREE.PointLight(themeHex, 1.2, 8);
    auraLight.position.set(0, 0, 1);
    scene.add(auraLight);

    // 4. Controller Setup for FSM Events & Speech Callouts
    const controller = new AvatarController(null, permissionsRef.current);
    controller.setManifest(manifest);
    controller.setSpeechCallback((text: string) => {
      setSpeechSnippet(text);
      setFsmState('SPEAKING');
    });
    controllerRef.current = controller;

    // Connect to WebSocket Event Bridge
    const bridge = AvatarEventBridge.getInstance();
    const unsubscribeBridge = bridge.addListener((event: string, payload: any) => {
      controller.handleEvent(event, payload);
      setFsmState(controller.getState());
    });

    // 5. Model Container and GLTF Loading
    const avatarRoot = new THREE.Group();
    avatarRoot.position.set(0, 0, 0);
    scene.add(avatarRoot);

    // Holographic Base Rings
    const baseRingGeo = new THREE.RingGeometry(0.8, 0.85, 48);
    const baseRingMat = new THREE.MeshBasicMaterial({
      color: themeHex,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.4,
    });
    const baseRing = new THREE.Mesh(baseRingGeo, baseRingMat);
    baseRing.rotation.x = Math.PI / 2;
    baseRing.position.y = -1.5;
    avatarRoot.add(baseRing);

    const outerRingGeo = new THREE.RingGeometry(1.2, 1.22, 64);
    const outerRingMat = new THREE.MeshBasicMaterial({
      color: themeHex,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.25,
    });
    const outerRing = new THREE.Mesh(outerRingGeo, outerRingMat);
    outerRing.rotation.x = Math.PI / 2;
    outerRing.position.y = -1.5;
    avatarRoot.add(outerRing);

    let loadedModel: THREE.Object3D | null = null;
    const loader = new GLTFLoader();

    const directStaticUrl = '/avatar/corrupted_archangel.glb';
    const backendStreamUrl = `http://127.0.0.1:8000/api/avatar/asset-file?path=${encodeURIComponent(
      runtimeAssetPath || 'assets/avatars/beckie/source/corrupted_archangel_six_wings_boss.glb'
    )}`;

    const loadModelFromUrl = (url: string, fallbackUrl?: string) => {
      setIsLoading(true);
      setLoadError(null);

      loader.load(
        url,
        (gltf) => {
          if (isDisposed) return;
          const model = gltf.scene;

          // Compute Bounding Box to center and scale uniformly
          const box = new THREE.Box3().setFromObject(model);
          const size = box.getSize(new THREE.Vector3());
          const center = box.getCenter(new THREE.Vector3());

          // Target height ~2.8 units in HUD aperture
          const maxDim = Math.max(size.x, size.y, size.z);
          const scaleFactor = 2.8 / (maxDim || 1);
          model.scale.setScalar(scaleFactor);

          // Center model pivot
          model.position.x = -center.x * scaleFactor;
          model.position.y = -center.y * scaleFactor;
          model.position.z = -center.z * scaleFactor;

          // Metallic sheen enhancements
          model.traverse((child) => {
            if ((child as THREE.Mesh).isMesh) {
              const mesh = child as THREE.Mesh;
              if (mesh.material) {
                const mat = mesh.material as THREE.MeshStandardMaterial;
                mat.roughness = Math.min(mat.roughness ?? 0.5, 0.4);
                mat.metalness = Math.max(mat.metalness ?? 0.5, 0.6);
              }
            }
          });

          loadedModel = model;
          avatarRoot.add(model);

          setIsLoading(false);
          setLoadError(null);
          setLoadProgress(100);
        },
        (xhr) => {
          if (xhr.total > 0) {
            const pct = Math.round((xhr.loaded / xhr.total) * 100);
            setLoadProgress(pct);
          } else if (xhr.loaded > 0) {
            const pct = Math.min(99, Math.round((xhr.loaded / 130758248) * 100));
            setLoadProgress(pct);
          }
        },
        (error) => {
          console.warn(`[AvatarScene] Failed to load 3D model from ${url}:`, error);
          if (fallbackUrl && !isDisposed) {
            console.info(`[AvatarScene] Retrying via fallback URL: ${fallbackUrl}`);
            loadModelFromUrl(fallbackUrl);
          } else if (!isDisposed) {
            setIsLoading(false);
            setLoadError('Failed to load local GLB asset. Ensure backend or static assets are accessible.');
          }
        }
      );
    };

    // Load from direct static route first for sub-second rendering, with backend endpoint as fallback
    loadModelFromUrl(directStaticUrl, backendStreamUrl);

    // 6. Animation and Render Loop (Static Ambient Pose)
    let lastTime = performance.now();
    const startTime = performance.now();
    let speechPulseTimer = 0;

    const animate = () => {
      if (isDisposed) return;
      animationFrameId = requestAnimationFrame(animate);

      const now = performance.now();
      const delta = Math.min((now - lastTime) / 1000, 0.1);
      lastTime = now;
      const elapsed = (now - startTime) / 1000;

      // Master enable check
      if (!permissionsRef.current.enabled) {
        avatarRoot.visible = false;
        renderer.render(scene, camera);
        return;
      }
      avatarRoot.visible = true;

      // Read current store state for Mode reactivity
      const jarvisState = useJarvisStore.getState();
      const isMusicPlaying = !!jarvisState.spotify?.is_playing;
      const modeStr = jarvisState.activeModeOverride || jarvisState.cpu.performanceMode?.mode || 'Balanced';
      const lowerMode = modeStr.toLowerCase();

      // Update lights and rings with current theme
      rimLight.color.setHex(themeHexRef.current);
      backRimLight.color.setHex(themeHexRef.current);
      auraLight.color.setHex(themeHexRef.current);
      baseRingMat.color.setHex(themeHexRef.current);
      outerRingMat.color.setHex(themeHexRef.current);

      // Controller update for FSM state
      controller.setPermissions(permissionsRef.current);
      controller.update(delta, modeStr);

      const activeFsm = controller.getState();
      if (activeFsm !== fsmStateRef.current) {
        setFsmState(activeFsm);
      }

      // Static Avatar Positioning: Locked in center core dock
      if (permissionsRef.current.reducedMotion) {
        avatarRoot.position.set(0, 0, 0);
        avatarRoot.rotation.set(0, 0, 0);
      } else {
        // Optional subtle organic hover breathing in center if enabled
        const hoverOffset = permissionsRef.current.proceduralHover
          ? Math.sin(elapsed * 1.5) * 0.04
          : 0;
        avatarRoot.position.set(0, hoverOffset, 0);
        avatarRoot.rotation.set(0, 0, 0);

        // Smooth base rings ambient rotation
        baseRing.rotation.z = elapsed * (isMusicPlaying ? 0.6 : 0.25);
        outerRing.rotation.z = -elapsed * (isMusicPlaying ? 0.4 : 0.15);
      }

      // Mode-specific light flair
      if (lowerMode.includes('g-mode')) {
        rimLight.intensity = 4.5;
        auraLight.intensity = 1.8 + Math.sin(elapsed * 3) * 0.4;
      } else if (lowerMode.includes('quiet')) {
        rimLight.intensity = 1.8;
        auraLight.intensity = 0.8;
      } else {
        rimLight.intensity = 3.2;
        auraLight.intensity = 1.2 + Math.sin(elapsed * 2) * 0.2;
      }

      // Speech & Listening Aura Reactions
      if (activeFsm === 'SPEAKING') {
        speechPulseTimer += delta * 8;
        const pulse = 1.0 + Math.sin(speechPulseTimer) * 0.5;
        auraLight.intensity = 2.8 * pulse;
        baseRingMat.opacity = 0.5 + Math.sin(speechPulseTimer) * 0.25;
        outerRingMat.opacity = 0.3 + Math.cos(speechPulseTimer) * 0.15;
      } else if (activeFsm === 'LISTENING') {
        auraLight.intensity = 2.0;
        auraLight.color.setHex(0xffaa00);
      }

      renderer.render(scene, camera);
    };

    animate();

    // 7. Responsive Resize Handler
    const handleResize = () => {
      if (!container || !renderer || !camera) return;
      const width = container.clientWidth;
      const height = container.clientHeight;
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height);
    };

    window.addEventListener('resize', handleResize);

    // 8. Cleanup
    return () => {
      isDisposed = true;
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener('resize', handleResize);
      unsubscribeBridge();

      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
      renderer.dispose();
      baseRingGeo.dispose();
      baseRingMat.dispose();
      outerRingGeo.dispose();
      outerRingMat.dispose();
    };
  }, [runtimeAssetPath, resetToCenterTrigger]);

  return (
    <div className="absolute inset-0 pointer-events-none z-[12] flex items-center justify-center overflow-hidden">
      {/* 3D Canvas Mount (Strictly pointer-events-none so HUD controls stay interactive) */}
      <div ref={mountRef} className="w-full h-full" />

      {/* Loading Progress Hologram Overlay */}
      {isLoading && (
        <div className="absolute top-[52%] left-1/2 -translate-x-1/2 -translate-y-1/2 flex flex-col items-center gap-2 p-4 rounded-xl bg-slate-950/80 border border-cyan-500/40 backdrop-blur-md font-mono text-xs text-cyan-300 pointer-events-auto">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
            <span>INITIALIZING LOCAL AVATAR GEOMETRY...</span>
          </div>
          <div className="w-48 h-1.5 bg-slate-800 rounded-full overflow-hidden border border-cyan-500/20">
            <div
              className="h-full bg-cyan-400 transition-all duration-200"
              style={{ width: `${loadProgress}%` }}
            />
          </div>
          <div className="text-[10px] text-slate-400">
            {loadProgress > 0 ? `${loadProgress}% STREAMED FROM LOCAL HOST` : 'ANALYZING BUFFER...'}
          </div>
        </div>
      )}

      {/* Load Error Message */}
      {loadError && (
        <div className="absolute top-[52%] left-1/2 -translate-x-1/2 -translate-y-1/2 p-4 rounded-xl bg-red-950/90 border border-red-500/40 backdrop-blur-md font-mono text-xs text-red-200 pointer-events-auto max-w-sm text-center">
          <div className="font-bold text-red-400 mb-1">LOCAL ASSET LOAD FAILED</div>
          <p className="text-[11px] text-slate-300">{loadError}</p>
          <button
            onClick={() => setInspectionOpen(true)}
            className="mt-3 px-3 py-1 bg-red-900/60 border border-red-400/40 rounded text-red-200 hover:bg-red-800 text-[10px]"
          >
            OPEN ASSET AUDIT
          </button>
        </div>
      )}
    </div>
  );
};
