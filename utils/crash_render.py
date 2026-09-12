"""
Renders the .crash game as a live multiplier graph instead of a bare
number in an embed — grid, rising curve, glowing marker, and a
distinct "explosion" / "cashed out" end state.
"""

from PIL import Image, ImageDraw
from utils.render_common import load_font, vertical_gradient, radial_glow, to_buffer

W, H = 760, 380
PAD_L, PAD_R, PAD_T, PAD_B = 70, 40, 70, 56

BG_TOP = (18, 20, 32)
BG_BOTTOM = (10, 11, 18)
GRID_COLOR = (46, 49, 66)
AXIS_TEXT = (130, 133, 150)
GHOST_COLOR = (90, 93, 110)

FONT_MULT = load_font(64, "Bold")
FONT_SMALL = load_font(20, "Medium")
FONT_TINY = load_font(17, "Regular")
FONT_LABEL = load_font(16, "Regular")


def _color_for_mult(mult):
    if mult < 1.5:
        return (87, 242, 135)     # green
    elif mult < 3.0:
        return (254, 231, 92)     # yellow
    elif mult < 7.0:
        return (255, 119, 0)      # orange
    else:
        return (237, 66, 69)      # red


def _nice_step(view_max):
    raw = view_max / 4
    for step in (0.25, 0.5, 1, 2, 5, 10, 20, 50, 100, 250, 500):
        if raw <= step:
            return step
    return 1000


def _plot_point(mult, view_max, plot_w, plot_h):
    frac = min(mult / view_max, 1.0)
    x = PAD_L
    y = PAD_T + plot_h - frac * plot_h
    return x, y


def _curve_points(history, view_max, plot_w, plot_h):
    pts = []
    n = max(len(history) - 1, 1)
    for i, m in enumerate(history):
        x = PAD_L + (i / n) * plot_w
        frac = min(m / view_max, 1.0)
        y = PAD_T + plot_h - frac * plot_h
        pts.append((x, y))
    return pts


def render_crash(
    history,
    status,
    bet,
    potential,
    format_cash,
    crash_point=None,
    cashout_mult=None,
    ghost_history=None,
):
    """
    history: list[float] multipliers sampled once per animation frame (index = time)
    status: "live" | "crashed" | "cashed"
    ghost_history: extra multipliers *after* the cashout point, shown dim,
                    so a cashed-out player can see what they left on the table.
    """
    base = vertical_gradient(W, H, BG_TOP, BG_BOTTOM).convert("RGBA")
    draw = ImageDraw.Draw(base)

    current_mult = history[-1] if history else 1.0
    display_end = max(history + (ghost_history or [])) if (ghost_history or history) else current_mult
    view_max = max(2.0, display_end * 1.2)

    plot_w = W - PAD_L - PAD_R
    plot_h = H - PAD_T - PAD_B

    # ── grid ──
    step = _nice_step(view_max)
    level = step
    while level < view_max:
        frac = level / view_max
        y = PAD_T + plot_h - frac * plot_h
        draw.line([(PAD_L, y), (W - PAD_R, y)], fill=GRID_COLOR, width=1)
        label = f"{level:g}×"
        draw.text((10, y - 8), label, font=FONT_LABEL, fill=AXIS_TEXT)
        level += step
    # baseline
    draw.line([(PAD_L, PAD_T + plot_h), (W - PAD_R, PAD_T + plot_h)], fill=GRID_COLOR, width=1)
    draw.text((10, PAD_T + plot_h - 8), "1×", font=FONT_LABEL, fill=AXIS_TEXT)

    color = _color_for_mult(current_mult if status != "crashed" else (crash_point or current_mult))

    # ── ghost curve (post-cashout potential continuation) ──
    if ghost_history and len(ghost_history) > 1:
        full = history + ghost_history
        n = max(len(full) - 1, 1)
        pts = []
        for i, m in enumerate(full):
            x = PAD_L + (i / n) * plot_w
            frac = min(m / view_max, 1.0)
            y = PAD_T + plot_h - frac * plot_h
            pts.append((x, y))
        if len(pts) > 1:
            draw.line(pts, fill=GHOST_COLOR, width=3, joint="curve")
        # crash marker at the very end of the ghost line
        if crash_point is not None:
            gx, gy = pts[-1]
            draw.ellipse([gx - 6, gy - 6, gx + 6, gy + 6], fill=(70, 30, 32), outline=(140, 60, 63), width=2)

    # ── main curve ──
    if history and len(history) > 1:
        n = max(len(history) - 1, 1)
        pts = [
            (PAD_L + (i / n) * plot_w, PAD_T + plot_h - min(m / view_max, 1.0) * plot_h)
            for i, m in enumerate(history)
        ]
        # glow under the line
        glow = radial_glow(W, H, pts[-1], 90, color, max_alpha=110)
        base.alpha_composite(glow)
        draw = ImageDraw.Draw(base)
        draw.line(pts, fill=color, width=5, joint="curve")
        tip = pts[-1]
    else:
        tip = (PAD_L, PAD_T + plot_h)

    # ── marker at current position ──
    marker_fill = color
    if status == "crashed":
        marker_fill = (237, 66, 69)
    elif status == "cashed":
        marker_fill = (87, 242, 135)

    draw.ellipse([tip[0] - 9, tip[1] - 9, tip[0] + 9, tip[1] + 9], fill=(15, 16, 24))
    draw.ellipse([tip[0] - 7, tip[1] - 7, tip[0] + 7, tip[1] + 7], fill=marker_fill)

    if status == "crashed":
        # small burst lines around the marker
        import math
        for a in range(0, 360, 45):
            rad = math.radians(a)
            x1 = tip[0] + 11 * math.cos(rad)
            y1 = tip[1] + 11 * math.sin(rad)
            x2 = tip[0] + 20 * math.cos(rad)
            y2 = tip[1] + 20 * math.sin(rad)
            draw.line([(x1, y1), (x2, y2)], fill=(237, 66, 69), width=3)

    # ── header: big multiplier readout ──
    if status == "crashed":
        headline = f"{crash_point:.2f}×"
        head_color = (237, 66, 69)
        sub = "CRASHED"
    elif status == "cashed":
        headline = f"{cashout_mult:.2f}×"
        head_color = (87, 242, 135)
        sub = "CASHED OUT"
    else:
        headline = f"{current_mult:.2f}×"
        head_color = color
        sub = "LIVE"

    draw.text((PAD_L, 12), headline, font=FONT_MULT, fill=head_color)
    tw = draw.textlength(headline, font=FONT_MULT)
    draw.text((PAD_L + tw + 16, 30), sub, font=FONT_SMALL, fill=(230, 231, 236))

    # ── footer: bet / payout ──
    bet_text = f"Bet {format_cash(bet)}"
    pay_label = "Lost" if status == "crashed" else ("Cashed" if status == "cashed" else "Cash out now")
    pay_text = f"{pay_label}  {format_cash(potential)}"

    draw.text((PAD_L, H - 34), bet_text, font=FONT_TINY, fill=AXIS_TEXT)
    ptw = draw.textlength(pay_text, font=FONT_TINY)
    draw.text((W - PAD_R - ptw, H - 34), pay_text, font=FONT_TINY, fill=head_color)

    return to_buffer(base)
