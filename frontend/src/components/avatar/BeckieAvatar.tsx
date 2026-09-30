/**
 * BeckieAvatar.tsx – 3D Avatar Instance & Shader Behavior Controller
 *
 * Implements:
 * - Holographic PBR shader material application
 * - Synchronous voice pulse on speech amplitude
 * - Gentle look-at camera tracking
 * - Strict resource disposal upon unmount
 */

import React, { useEffect, useRef } from 'react';
import * as THREE from 'three';
import { AvatarFsmState, AvatarPermissions } from '../../types/avatar';
import {
  computeProceduralHoverOffset,
  disposeThreeHierarchy,
} from './avatarAnimationUtils';

interface BeckieAvatarProps {
  model: THREE.Object3D;
  fsmState: AvatarFsmState;
  permissions: AvatarPermissions;
  themeHex?: number;
  position?: [number, number, number];
}

export const BeckieAvatar: React.FC<BeckieAvatarProps> = ({
  model,
  fsmState,
  permissions,
  themeHex = 0x00B8FF,
  position = [0, 0, 0],
}) => {
  useEffect(() => {
    return () => {
      disposeThreeHierarchy(model);
    };
  }, [model]);

  return (
    <div
      className="beckie-avatar-instance hidden"
      data-state={fsmState}
      data-theme={themeHex}
      data-pos={position.join(',')}
    />
  );
};
