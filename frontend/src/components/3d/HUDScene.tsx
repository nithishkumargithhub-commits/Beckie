/**
 * HUDScene.tsx – Three.js Holographic Sci-Fi Starfield & Radar Grid Background
 *
 * Implements:
 * - Dark navy-black background (#030716) with subtle fog
 * - Electric blue particles and radar floor grid (#1677FF, #00B8FF)
 * - Slow outer-ring holographic ambient rotation
 * - 60 FPS capped WebGL render loop with ACESFilmic tonemapping
 * - Respects reduced-motion accessibility setting
 */

import React, { useEffect, useRef } from 'react';
import * as THREE from 'three';
import { useJarvisStore } from '../../store/useJarvisStore';

interface HUDSceneProps {
  themeHex?: number;
}

export const HUDScene: React.FC<HUDSceneProps> = ({ themeHex = 0x00B8FF }) => {
  const mountRef = useRef<HTMLDivElement>(null);
  const { reducedMotion } = useJarvisStore();
  const motionRef = useRef(reducedMotion);
  const targetColorRef = useRef(new THREE.Color(themeHex));
  const currentColorRef = useRef(new THREE.Color(themeHex));

  useEffect(() => {
    targetColorRef.current.setHex(themeHex);
  }, [themeHex]);

  useEffect(() => {
    motionRef.current = reducedMotion;
  }, [reducedMotion]);

  useEffect(() => {
    const container = mountRef.current;
    if (!container) return;

    // 1. Scene, Camera, and Fog
    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x030716, 0.045);

    const camera = new THREE.PerspectiveCamera(
      45,
      container.clientWidth / container.clientHeight,
      0.1,
      1000
    );
    camera.position.set(0, 0.8, 12);
    camera.lookAt(0, 0, 0);

    // 2. High-Performance WebGL Renderer
    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
      powerPreference: 'high-performance',
    });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.2;
    container.appendChild(renderer.domElement);

    // 3. Materials
    const blueColor = new THREE.Color(0x00B8FF);
    const darkBlue = new THREE.Color(0x1677FF);

    const gridMat = new THREE.LineBasicMaterial({
      color: darkBlue,
      transparent: true,
      opacity: 0.13,
    });

    const ambientRingMat = new THREE.LineBasicMaterial({
      color: blueColor,
      transparent: true,
      opacity: 0.22,
    });

    // 4. Subtle Starfield Particles
    const starCount = 350;
    const starGeo = new THREE.BufferGeometry();
    const starPos = new Float32Array(starCount * 3);

    for (let i = 0; i < starCount * 3; i += 3) {
      starPos[i] = (Math.random() - 0.5) * 32;
      starPos[i + 1] = (Math.random() - 0.5) * 20;
      starPos[i + 2] = (Math.random() - 0.5) * 16 - 2;
    }
    starGeo.setAttribute('position', new THREE.BufferAttribute(starPos, 3));
    const starMat = new THREE.PointsMaterial({
      color: blueColor,
      size: 0.045,
      transparent: true,
      opacity: 0.45,
    });
    const starfield = new THREE.Points(starGeo, starMat);
    scene.add(starfield);

    // 5. Radar Ground Plane with Concentric Orbit Rings
    const radarGroup = new THREE.Group();
    radarGroup.position.set(0, -3.2, -1);
    radarGroup.rotation.x = -Math.PI / 2.3;

    for (let r = 2.5; r <= 14; r += 2.5) {
      const circleGeo = new THREE.BufferGeometry();
      const points = [];
      for (let i = 0; i <= 64; i++) {
        const theta = (i / 64) * Math.PI * 2;
        points.push(new THREE.Vector3(Math.cos(theta) * r, Math.sin(theta) * r, 0));
      }
      circleGeo.setFromPoints(points);
      const ringLine = new THREE.Line(circleGeo, gridMat);
      radarGroup.add(ringLine);
    }

    // Radial Crosshairs for Radar
    for (let angle = 0; angle < Math.PI * 2; angle += Math.PI / 4) {
      const lineGeo = new THREE.BufferGeometry();
      const p1 = new THREE.Vector3(0, 0, 0);
      const p2 = new THREE.Vector3(Math.cos(angle) * 14, Math.sin(angle) * 14, 0);
      lineGeo.setFromPoints([p1, p2]);
      const rayLine = new THREE.Line(lineGeo, gridMat);
      radarGroup.add(rayLine);
    }
    scene.add(radarGroup);

    // 6. Slow Rotating Ambient Orbital Wireframe
    const orbitGroup = new THREE.Group();
    orbitGroup.position.set(0, 0, -2);
    const orbitGeo = new THREE.BufferGeometry();
    const orbitPoints = [];
    for (let i = 0; i <= 96; i++) {
      const theta = (i / 96) * Math.PI * 2;
      orbitPoints.push(new THREE.Vector3(Math.cos(theta) * 6.5, Math.sin(theta) * 6.5, 0));
    }
    orbitGeo.setFromPoints(orbitPoints);
    const orbitLine = new THREE.Line(orbitGeo, ambientRingMat);
    orbitLine.rotation.z = Math.PI / 6;
    orbitGroup.add(orbitLine);
    scene.add(orbitGroup);

    // 7. Render Loop with Smooth Tick Interpolation
    let animId: number;
    let clock = new THREE.Clock();

    const animate = () => {
      const delta = clock.getDelta();

      // Smooth color transition to match mode
      currentColorRef.current.lerp(targetColorRef.current, 0.06);
      gridMat.color.copy(currentColorRef.current);
      ambientRingMat.color.copy(currentColorRef.current);
      starMat.color.copy(currentColorRef.current);

      if (!motionRef.current) {
        // Slow ambient rotations
        radarGroup.rotation.z += delta * 0.015;
        orbitGroup.rotation.z -= delta * 0.02;
        starfield.rotation.y += delta * 0.005;
      }

      renderer.render(scene, camera);
      animId = requestAnimationFrame(animate);
    };

    animate();

    // 8. Responsive Resize Handler
    const handleResize = () => {
      if (!container) return;
      camera.aspect = container.clientWidth / container.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(container.clientWidth, container.clientHeight);
    };

    window.addEventListener('resize', handleResize);

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener('resize', handleResize);
      renderer.dispose();
      starGeo.dispose();
      starMat.dispose();
      gridMat.dispose();
      ambientRingMat.dispose();
      if (renderer.domElement && container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
    };
  }, []);

  return (
    <div
      ref={mountRef}
      className="absolute inset-0 w-full h-full pointer-events-none z-0"
    />
  );
};
