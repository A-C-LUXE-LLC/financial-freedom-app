/**
 * Tiny Web Audio chime generator — no audio files, just synthesized tones.
 * Used for win celebrations. Respects the user's mute toggle.
 */
let ctx = null;
let muted = false;

export const setMuted = (val) => { muted = val; };
export const isMuted = () => muted;

function getCtx() {
  if (typeof window === "undefined") return null;
  if (!ctx) {
    try { ctx = new (window.AudioContext || window.webkitAudioContext)(); }
    catch (e) { ctx = null; }
  }
  return ctx;
}

function tone(freq, durMs, when, type = "sine", gain = 0.15) {
  const ac = getCtx(); if (!ac) return;
  const osc = ac.createOscillator();
  const g = ac.createGain();
  osc.type = type;
  osc.frequency.setValueAtTime(freq, ac.currentTime + when);
  g.gain.setValueAtTime(0.0001, ac.currentTime + when);
  g.gain.exponentialRampToValueAtTime(gain, ac.currentTime + when + 0.02);
  g.gain.exponentialRampToValueAtTime(0.0001, ac.currentTime + when + durMs / 1000);
  osc.connect(g).connect(ac.destination);
  osc.start(ac.currentTime + when);
  osc.stop(ac.currentTime + when + durMs / 1000 + 0.05);
}

export function playWinChime() {
  if (muted) return;
  // gentle ascending 3-note arpeggio C5 -> E5 -> G5
  tone(523.25, 180, 0.00, "sine", 0.14);
  tone(659.25, 180, 0.10, "sine", 0.14);
  tone(783.99, 280, 0.20, "sine", 0.14);
}

export function playTapChime() {
  if (muted) return;
  tone(880, 80, 0.0, "sine", 0.08);
}

export function playWishChime() {
  if (muted) return;
  // sparkle: high to mid descending
  tone(1318.51, 120, 0.0, "triangle", 0.08);
  tone(987.77, 120, 0.08, "triangle", 0.08);
}
