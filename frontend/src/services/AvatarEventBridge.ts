/**
 * AvatarEventBridge.ts – Local Event-Driven Bridge for BECKIE Lifecycle Events
 *
 * Connects Python backend voice, LLM, TTS, and privacy events with the AvatarController:
 * - voice.listening.started / voice.listening.stopped -> LISTENING / IDLE
 * - llm.generation.started / llm.generation.completed -> THINKING / IDLE
 * - tts.started / tts.completed -> SPEAKING / IDLE
 * - privacy.mic.paused -> PAUSED
 * - assistant.emergency_paused -> PAUSED
 *
 * Exclusively uses localhost connections (127.0.0.1). Zero external network calls.
 */

import { AvatarFsmState } from '../types/avatar';

type AvatarEventListener = (event: string, payload: any) => void;

export class AvatarEventBridge {
  private static instance: AvatarEventBridge;
  private ws: WebSocket | null = null;
  private listeners: AvatarEventListener[] = [];
  private reconnectTimer: number | null = null;
  private isConnecting: boolean = false;

  public static getInstance(): AvatarEventBridge {
    if (!AvatarEventBridge.instance) {
      AvatarEventBridge.instance = new AvatarEventBridge();
    }
    return AvatarEventBridge.instance;
  }

  private constructor() {
    this.connect();
  }

  public connect(): void {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }
    if (this.isConnecting) return;
    this.isConnecting = true;

    try {
      this.ws = new WebSocket('ws://127.0.0.1:8000/ws');

      this.ws.onopen = () => {
        this.isConnecting = false;
        console.log('[AvatarEventBridge] Connected to localhost WebSocket event stream');
      };

      this.ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          this.handleIncomingMessage(msg);
        } catch (e) {
          // Non-JSON message
        }
      };

      this.ws.onclose = () => {
        this.isConnecting = false;
        this.scheduleReconnect();
      };

      this.ws.onerror = () => {
        this.isConnecting = false;
      };
    } catch (e) {
      this.isConnecting = false;
      this.scheduleReconnect();
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) return;
    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, 3000);
  }

  private handleIncomingMessage(msg: any): void {
    if (!msg) return;

    // Direct avatar event wrapper
    if (msg.type === 'avatar_event' && msg.event) {
      this.dispatch(msg.event, msg.data || {});
      return;
    }

    // Map common reminder/daemon/chat events if delivered
    if (msg.event) {
      this.dispatch(msg.event, msg.data || msg);
    }
  }

  public addListener(listener: AvatarEventListener): () => void {
    this.listeners.push(listener);
    return () => {
      this.listeners = this.listeners.filter((l) => l !== listener);
    };
  }

  public dispatch(event: string, payload: any): void {
    for (const listener of this.listeners) {
      try {
        listener(event, payload);
      } catch (err) {
        console.error('[AvatarEventBridge] Listener error:', err);
      }
    }
  }

  /**
   * Simulate a local event directly (for testing without live microphone/TTS).
   */
  public async simulateLocalEvent(event: string, data?: any): Promise<void> {
    try {
      await fetch('http://127.0.0.1:8000/api/avatar/simulate-event', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ event, data: data || {} }),
      });
    } catch (err) {
      // Local fallback in browser
      this.dispatch(event, data || {});
    }
  }
}
