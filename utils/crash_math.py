"""
Time-based multiplier curve for the crash game.

Instead of animating by editing a Discord message every N ms (janky,
rate-limited, inconsistent), the whole run from 1.00x to the crash
point is pre-rendered into a single animated GIF that plays smoothly
client-side. This module is the single source of truth for "what the
multiplier is at time t", so the GIF frames and the server-side
cashout/auto-cashout timing always agree with what the player is
actually looking at.
"""

import math

EASE = 1.7          # >1 = slow start, accelerating climb (typical "rocket" feel)
FRAME_MS = 100       # GIF frame spacing
MIN_FRAMES = 10
MAX_FRAMES = 50


def duration_for_crash(crash_point: float) -> int:
    """Total playback length (ms) for a given crash point, snapped to a
    whole number of FRAME_MS steps so the GIF and the timer line up exactly."""
    base = 1200
    scale = 900
    if crash_point > 1.0:
        raw = base + scale * math.log2(crash_point)
    else:
        raw = base
    raw = max(base, min(raw, 7000))

    total_frames = round(raw / FRAME_MS)
    total_frames = max(MIN_FRAMES, min(MAX_FRAMES, total_frames))
    return total_frames * FRAME_MS


def mult_at_time(t_ms: float, duration_ms: int, crash_point: float) -> float:
    """The multiplier shown on screen at time t_ms into the animation."""
    if t_ms <= 0:
        return 1.0
    if t_ms >= duration_ms:
        return crash_point
    frac = (t_ms / duration_ms) ** EASE
    return 1.0 + (crash_point - 1.0) * frac


def time_for_mult(target_mult: float, duration_ms: int, crash_point: float):
    """Inverse of mult_at_time — when (ms) does the curve cross target_mult?
    Returns None if the target is never reached (crash happens first)."""
    if target_mult <= 1.0:
        return 0
    if target_mult >= crash_point:
        return None
    frac = (target_mult - 1.0) / (crash_point - 1.0)
    t_frac = frac ** (1.0 / EASE)
    return t_frac * duration_ms
