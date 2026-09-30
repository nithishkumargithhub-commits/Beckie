/**
 * avatar-controller.test.ts – Avatar FSM Engine & Priority Transitions Tests
 *
 * Enforces Section 6 & 11 Acceptance Criteria:
 * - 15 discrete states
 * - Priority order: Emergency Pause > Privacy Mic > Conversation > Ambient
 * - Event mappings from local pipeline
 */

import { describe, it, expect } from 'vitest';
import { AvatarController } from '../components/avatar/AvatarController';
import { AvatarNavigationSystem } from '../components/avatar/AvatarNavigationSystem';
import { AvatarPermissions } from '../types/avatar';

const defaultPermissions: AvatarPermissions = {
  enabled: true,
  ambientMovement: true,
  proceduralHover: true,
  flightBehavior: false,
  weaponPose: false,
  reducedMotion: false,
  suspendUnderLoad: true,
  quality: 'Balanced',
  volume: 0.8,
  rememberChoice: false,
};

describe('AvatarController FSM Engine', () => {
  it('maps voice, llm, and tts events correctly', () => {
    const nav = new AvatarNavigationSystem();
    const ctrl = new AvatarController(nav, defaultPermissions);

    expect(ctrl.getState()).toBe('IDLE');

    // 1. Voice listening
    ctrl.handleEvent('voice.listening.started', {});
    expect(ctrl.getState()).toBe('LISTENING');

    // 2. LLM thinking
    ctrl.handleEvent('llm.generation.started', {});
    expect(ctrl.getState()).toBe('THINKING');

    // 3. TTS speaking
    ctrl.handleEvent('tts.started', { text: 'Hello from BECKIE' });
    expect(ctrl.getState()).toBe('SPEAKING');
    expect(ctrl.getSpeechSnippet()).toBe('Hello from BECKIE');

    // 4. TTS completed
    ctrl.handleEvent('tts.completed', {});
    expect(ctrl.getState()).toBe('IDLE');
  });

  it('enforces emergency pause as highest priority override', () => {
    const nav = new AvatarNavigationSystem();
    const ctrl = new AvatarController(nav, defaultPermissions);

    ctrl.handleEvent('tts.started', { text: 'Speaking...' });
    expect(ctrl.getState()).toBe('SPEAKING');

    // Trigger emergency pause
    ctrl.handleEvent('assistant.emergency_paused', { emergencyPaused: true });
    expect(ctrl.getState()).toBe('PAUSED');

    // Attempting to speak or listen while paused must be rejected
    ctrl.handleEvent('voice.listening.started', {});
    expect(ctrl.getState()).toBe('PAUSED');

    ctrl.handleEvent('tts.started', { text: 'Blocked' });
    expect(ctrl.getState()).toBe('PAUSED');

    // Resuming restores IDLE
    ctrl.handleEvent('assistant.emergency_paused', { emergencyPaused: false });
    expect(ctrl.getState()).toBe('IDLE');
  });

  it('respects mic mute privacy override', () => {
    const nav = new AvatarNavigationSystem();
    const ctrl = new AvatarController(nav, defaultPermissions);

    // Mute mic
    ctrl.handleEvent('privacy.mic.paused', { micPaused: true });

    // Listening event should not transition to LISTENING
    ctrl.handleEvent('voice.listening.started', {});
    expect(ctrl.getState()).toBe('IDLE');
  });
});
