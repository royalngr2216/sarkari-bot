"""
Pre-renders an entire crash run (1.00x -> crash point) as a single
animated GIF. This is generated once per game and posted as-is, so
playback is smooth and client-side — no more re-editing the message
every frame.
"""

import io
import math
from PIL import Image, ImageDraw

from utils.render_common import load_font, vertical_gradient, radial_glow
from utils.crash_math import mult_at_time, FRAME_MS

W, H = 760, 380
PAD_L, PAD_R, PAD_T, PAD_B = 70, 40, 70, 56

BG_TOP = (18, 20, 32)
BG_BOTTOM = (10, 11, 18)
GRID_COLOR = (46, 49, 66)
AXIS_TEXT = (130, 133, 150)

FONT_MULT = load_font(64, "Bold")
FONT_SMALL = load_font(20, "Medium")
FONT_TINY = load_font(17, "Regular")
FONT_LABEL = load_font(16, "Regular")

PLOT_W = W - PAD_L - PAD_R
PLOT_H = H - PAD_T - PAD_B


def _color_for_mult(mult):
    if mult < 1.5:
        return (87, 242, 135)
    elif mult < 3.0:
        return (254, 231, 92)
    elif mult < 7.0:
        return (255, 119, 0)
    else:
        return (237, 66, 69)


def _nice_step(view_max):
    raw = view_max / 4
    for step in (0.25, 0.5, 1, 2, 5, 10, 20, 50, 100, 250, 500):
        if raw <= step:
            return step
    return 1000


def _base_canvas(view_max):
    """Static background (gradient + grid) shared by every frame — built
    once and reused so we're not re-drawing a gradient 30-50 times."""
    base = vertical_gradient(W, H, BG_TOP, BG_BOTTOM).convert("RGB")
    draw = ImageDraw.Draw(base)

    step = _nice_step(view_max)
    level = step
    while level < view_max:
        frac = level / view_max
        y = PAD_T + PLOT_H - frac * PLOT_H
        draw.line([(PAD_L, y), (W - PAD_R, y)], fill=GRID_COLOR, width=1)
        draw.text((10, y - 8), f"{level:g}×", font=FONT_LABEL, fill=AXIS_TEXT)
        level += step
    draw.line([(PAD_L, PAD_T + PLOT_H), (W - PAD_R, PAD_T + PLOT_H)], fill=GRID_COLOR, width=1)
    draw.text((10, PAD_T + PLOT_H - 8), "1×", font=FONT_LABEL, fill=AXIS_TEXT)
    return base


def _plane_marker(draw, tip, angle_deg, color):
    """Small triangular 'plane' at the tip of the curve, oriented along
    the direction of travel, with a soft glow trailing behind it."""
    size = 13
    rad = math.radians(angle_deg)
    nose = (tip[0] + size * math.cos(rad), tip[1] + size * math.sin(rad))
    back_rad1 = math.radians(angle_deg + 150)
    back_rad2 = math.radians(angle_deg - 150)
    left = (tip[0] + size * math.cos(back_rad1), tip[1] + size * math.sin(back_rad1))
    right = (tip[0] + size * math.cos(back_rad2), tip[1] + size * math.sin(back_rad2))
    draw.polygon([nose, left, right], fill=(255, 255, 255), outline=color)


def _draw_frame(bg_template, view_max, points, bet, format_cash, status, crash_point=None):
    base = bg_template.copy().convert("RGBA")
    current_mult = points[-1][1] if points else 1.0

    color = _color_for_mult(current_mult if status != "crashed" else crash_point)

    if len(points) > 1:
        pts_xy = [
            (PAD_L + (t / points[-1][0] if points[-1][0] else 0) * PLOT_W,
             PAD_T + PLOT_H - min(m / view_max, 1.0) * PLOT_H)
            for t, m in points
        ]
        glow = radial_glow(W, H, pts_xy[-1], 85, color, max_alpha=100)
        base.alpha_composite(glow)
        draw = ImageDraw.Draw(base)
        draw.line(pts_xy, fill=color, width=5, joint="curve")
        tip = pts_xy[-1]
        if len(pts_xy) > 2:
            dx = tip[0] - pts_xy[-3][0]
            dy = tip[1] - pts_xy[-3][1]
        else:
            dx, dy = 1, -0.3
        angle = math.degrees(math.atan2(dy, dx))
    else:
        draw = ImageDraw.Draw(base)
        tip = (PAD_L, PAD_T + PLOT_H)
        angle = -20

    if status == "crashed":
        for a in range(0, 360, 45):
            r1, r2 = 10, 20
            rad = math.radians(a)
            draw.line(
                [(tip[0] + r1 * math.cos(rad), tip[1] + r1 * math.sin(rad)),
                 (tip[0] + r2 * math.cos(rad), tip[1] + r2 * math.sin(rad))],
                fill=(237, 66, 69), width=3
            )
        draw.ellipse([tip[0] - 7, tip[1] - 7, tip[0] + 7, tip[1] + 7], fill=(237, 66, 69))
    else:
        _plane_marker(draw, tip, angle, color)

    if status == "crashed":
        headline = f"{crash_point:.2f}×"
        head_color = (237, 66, 69)
        sub = "CRASHED"
    else:
        headline = f"{current_mult:.2f}×"
        head_color = color
        sub = "LIVE"

    draw.text((PAD_L, 12), headline, font=FONT_MULT, fill=head_color)
    tw = draw.textlength(headline, font=FONT_MULT)
    draw.text((PAD_L + tw + 16, 30), sub, font=FONT_SMALL, fill=(230, 231, 236))

    bet_text = f"Bet {format_cash(bet)}"
    if status == "crashed":
        pay_text = f"Lost {format_cash(bet)}"
    else:
        pay_text = f"Cash out now  {format_cash(int(bet * current_mult))}"
    draw.text((PAD_L, H - 34), bet_text, font=FONT_TINY, fill=AXIS_TEXT)
    ptw = draw.textlength(pay_text, font=FONT_TINY)
    draw.text((W - PAD_R - ptw, H - 34), pay_text, font=FONT_TINY, fill=head_color)

    return base.convert("RGB")


def build_crash_gif(crash_point: float, duration_ms: int, bet: int, format_cash) -> io.BytesIO:
    """Renders the full 1.00x -> crash_point run as one animated GIF."""
    view_max = max(2.0, crash_point * 1.15)
    bg_template = _base_canvas(view_max)

    n_frames = duration_ms // FRAME_MS
    points = []
    frames = []
    durations = []

    for i in range(n_frames + 1):
        t = i * FRAME_MS
        m = mult_at_time(t, duration_ms, crash_point)
        points.append((t, m))
        frames.append(_draw_frame(bg_template, view_max, points, bet, format_cash, "live"))
        durations.append(FRAME_MS)

    # Hold on the crash frame at the end
    crash_frame = _draw_frame(bg_template, view_max, points, bet, format_cash, "crashed", crash_point=crash_point)
    frames.append(crash_frame)
    durations.append(700)

    pal_frames = [f.convert("P", palette=Image.ADAPTIVE, colors=64, dither=Image.NONE) for f in frames]

    buf = io.BytesIO()
    pal_frames[0].save(
        buf,
        format="GIF",
        save_all=True,
        append_images=pal_frames[1:],
        duration=durations,
        disposal=2,
        optimize=True,
    )
    buf.seek(0)
    return buf
