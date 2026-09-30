/**
 * themeUtils.ts – Dynamic Cybernetic Theming for Alienware Performance Modes
 *
 * Maps active thermal/performance modes to color palettes, glows, ambient lighting,
 * and fan speeds across the BECKIE 3D HUD Dashboard.
 */

export type OperatingModeKey = 'g-mode' | 'performance' | 'balanced' | 'quiet' | 'cool' | 'fullspeed';

export interface ModeThemeConfig {
  key: OperatingModeKey;
  label: string;
  shortLabel: string;
  subLabel: string;
  accentColor: string;       // Primary vivid accent
  accentBright: string;      // Highlight tint
  accentSecondary: string;   // Secondary contrast
  glowColor: string;         // Box & text shadow rgba
  borderColor: string;      // Tactical border rgba
  bgTint: string;           // Glass panel background tint
  ambientGradient: string;  // Fullscreen ambient aura
  hexThree: number;         // 3D particle & grid color for Three.js
  fanRpmDesc: string;       // Fan readout text
  badgeText: string;        // Badge pill
  fanSpeedPct: number;      // Fan capacity percentage
  fanSpeedRpm: number;      // Max fan RPM
  iconType: 'flame' | 'rocket' | 'shield' | 'leaf' | 'snowflake' | 'gauge';
}

export const ALL_MODES: { key: OperatingModeKey; name: string; tag: string }[] = [
  { key: 'g-mode', name: 'G-MODE', tag: 'HIGH PERF' },
  { key: 'performance', name: 'PERFORMANCE', tag: 'OVERCLOCK' },
  { key: 'balanced', name: 'BALANCED', tag: 'DYNAMIC' },
  { key: 'quiet', name: 'QUIET', tag: 'STEALTH' },
  { key: 'cool', name: 'COOL', tag: 'SUB-ZERO' },
  { key: 'fullspeed', name: 'FULL SPEED', tag: '100% FAN' },
];

export function getModeTheme(rawMode?: string | null): ModeThemeConfig {
  const m = (rawMode || '').toLowerCase().trim();

  // 1. G-Mode / Game Shift / High Performance
  if (
    m.includes('g-mode') ||
    m.includes('gmode') ||
    m.includes('gkey') ||
    m.includes('high performance') ||
    m.includes('gameshift')
  ) {
    return {
      key: 'g-mode',
      label: 'G-MODE // MAXIMUM PERFORMANCE',
      shortLabel: 'G-MODE',
      subLabel: 'ALIENWARE GAME SHIFT • FULL THERMAL OVERDRIVE',
      accentColor: '#FF1744',
      accentBright: '#FF5252',
      accentSecondary: '#FF314F',
      glowColor: 'rgba(255, 23, 68, 0.58)',
      borderColor: 'rgba(255, 49, 79, 0.85)',
      bgTint: 'rgba(38, 6, 12, 0.82)',
      ambientGradient: 'radial-gradient(circle at 50% 10%, rgba(255, 23, 68, 0.24) 0%, rgba(255, 49, 79, 0.08) 45%, transparent 75%)',
      hexThree: 0xFF1744,
      fanRpmDesc: '5,400 RPM • 100% CAPACITY (MAX OVERDRIVE)',
      badgeText: 'G-SHIFT ACTIVE',
      fanSpeedPct: 100,
      fanSpeedRpm: 5400,
      iconType: 'flame',
    };
  }

  // 2. Full Speed / Turbo
  if (m.includes('fullspeed') || m.includes('full speed') || m.includes('turbo')) {
    return {
      key: 'fullspeed',
      label: 'FULL SPEED // 100% BLOWER',
      shortLabel: 'FULL SPEED',
      subLabel: 'MANUAL OVERDRIVE • CONSTANT MAXIMUM RPM',
      accentColor: '#D946EF',
      accentBright: '#F0ABFC',
      accentSecondary: '#C026D3',
      glowColor: 'rgba(217, 70, 239, 0.55)',
      borderColor: 'rgba(217, 70, 239, 0.85)',
      bgTint: 'rgba(28, 7, 36, 0.82)',
      ambientGradient: 'radial-gradient(circle at 50% 10%, rgba(217, 70, 239, 0.22) 0%, rgba(192, 38, 211, 0.08) 45%, transparent 75%)',
      hexThree: 0xD946EF,
      fanRpmDesc: '5,400 RPM • 100% CONSTANT BLOWER',
      badgeText: 'OVERDRIVE ACTIVE',
      fanSpeedPct: 100,
      fanSpeedRpm: 5400,
      iconType: 'gauge',
    };
  }

  // 3. Performance Mode
  if (m.includes('performance')) {
    return {
      key: 'performance',
      label: 'PERFORMANCE MODE // HIGH HEADROOM',
      shortLabel: 'PERFORMANCE',
      subLabel: 'MAXIMUM CLOCK HEADROOM • AGGRESSIVE FAN CURVE',
      accentColor: '#FF8A2A',
      accentBright: '#FFB300',
      accentSecondary: '#FF6D00',
      glowColor: 'rgba(255, 138, 42, 0.55)',
      borderColor: 'rgba(255, 138, 42, 0.85)',
      bgTint: 'rgba(32, 16, 6, 0.82)',
      ambientGradient: 'radial-gradient(circle at 50% 10%, rgba(255, 138, 42, 0.22) 0%, rgba(255, 109, 0, 0.07) 45%, transparent 75%)',
      hexThree: 0xFF8A2A,
      fanRpmDesc: '~3,800 RPM • 70% AGGRESSIVE AIRFLOW',
      badgeText: 'PERFORMANCE TUNED',
      fanSpeedPct: 70,
      fanSpeedRpm: 3800,
      iconType: 'rocket',
    };
  }

  // 4. Quiet / Stealth / Silent
  if (m.includes('quiet') || m.includes('stealth') || m.includes('silent') || m.includes('saver')) {
    return {
      key: 'quiet',
      label: 'QUIET // STEALTH MODE',
      shortLabel: 'QUIET / STEALTH',
      subLabel: 'WHISPER-SILENT OPERATION • ACOUSTIC PRIORITY',
      accentColor: '#00E676',
      accentBright: '#69F0AE',
      accentSecondary: '#00C853',
      glowColor: 'rgba(0, 230, 118, 0.52)',
      borderColor: 'rgba(0, 230, 118, 0.85)',
      bgTint: 'rgba(4, 28, 16, 0.82)',
      ambientGradient: 'radial-gradient(circle at 50% 10%, rgba(0, 230, 118, 0.20) 0%, rgba(0, 200, 83, 0.06) 45%, transparent 75%)',
      hexThree: 0x00E676,
      fanRpmDesc: '~1,600 RPM • 30% ACOUSTIC SILENCE',
      badgeText: 'STEALTH ACTIVE',
      fanSpeedPct: 30,
      fanSpeedRpm: 1600,
      iconType: 'leaf',
    };
  }

  // 5. Cool Mode
  if (m.includes('cool')) {
    return {
      key: 'cool',
      label: 'COOL MODE // THERMAL FOCUS',
      shortLabel: 'COOL MODE',
      subLabel: 'CHASSIS SURFACE COOLING • PROACTIVE DISSIPATION',
      accentColor: '#00F0FF',
      accentBright: '#70F7FF',
      accentSecondary: '#00B8D4',
      glowColor: 'rgba(0, 240, 255, 0.52)',
      borderColor: 'rgba(0, 240, 255, 0.85)',
      bgTint: 'rgba(3, 24, 34, 0.82)',
      ambientGradient: 'radial-gradient(circle at 50% 10%, rgba(0, 240, 255, 0.20) 0%, rgba(0, 184, 212, 0.06) 45%, transparent 75%)',
      hexThree: 0x00F0FF,
      fanRpmDesc: '~3,200 RPM • 60% PROACTIVE AIRFLOW',
      badgeText: 'COOL PROFILE ACTIVE',
      fanSpeedPct: 60,
      fanSpeedRpm: 3200,
      iconType: 'snowflake',
    };
  }

  // 6. Default: Balanced
  return {
    key: 'balanced',
    label: 'BALANCED MODE // OPTIMAL EFFICIENCY',
    shortLabel: 'BALANCED',
    subLabel: 'INTELLIGENT DYNAMIC SCALING • OPTIMAL THERMALS & ACOUSTICS',
    accentColor: '#00B8FF',
    accentBright: '#60CDFF',
    accentSecondary: '#1677FF',
    glowColor: 'rgba(0, 184, 255, 0.45)',
    borderColor: 'rgba(22, 119, 255, 0.75)',
    bgTint: 'rgba(6, 16, 40, 0.82)',
    ambientGradient: 'radial-gradient(circle at 50% 10%, rgba(0, 184, 255, 0.16) 0%, rgba(22, 119, 255, 0.06) 45%, transparent 75%)',
    hexThree: 0x00B8FF,
    fanRpmDesc: 'DYNAMIC AUTO • ~2,400 RPM (SENSOR REGULATED)',
    badgeText: 'DYNAMIC BALANCED',
    fanSpeedPct: 45,
    fanSpeedRpm: 2400,
    iconType: 'shield',
  };
}
