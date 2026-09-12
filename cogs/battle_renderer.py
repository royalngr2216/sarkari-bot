"""
battle_renderer.py
──────────────────
Generates a Showdown-style battle image each turn.
Called by pokemon_battle.py — returns a discord.File.

Sprites fetched via aiohttp at runtime (your bot already has it).
Falls back to a colored silhouette if a sprite fails to load.
"""

import io
import math
import asyncio
import aiohttp
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ── Fonts ─────────────────────────────────────────────────────────
_BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
_REG  = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"


def _font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


# ── Canvas ────────────────────────────────────────────────────────
# Final output size. Everything is drawn at SS_FACTOR x this size,
# then downsampled with LANCZOS for smooth anti-aliased edges.
W, H = 1000, 600
SS = 2  # supersampling factor

# ── Colours ───────────────────────────────────────────────────────
BG_TOP       = (16, 19, 34, 255)
BG_BOTTOM    = (9, 11, 20, 255)
GRID         = (255, 255, 255, 10)

FIELD_BG     = (20, 24, 42, 235)
FIELD_BORD   = (54, 66, 104, 255)

PANEL_TOP    = (32, 38, 64, 245)
PANEL_BOTTOM = (22, 26, 46, 245)
PANEL_BORD   = (80, 105, 175, 230)

ACCENT_BLUE  = (90, 150, 255)
ACCENT_RED   = (255, 110, 110)

PLATFORM_L   = (70, 120, 230)   # player platform glow
PLATFORM_R   = (235, 95, 95)    # opponent platform glow

TEXT_MAIN    = (240, 243, 255)
TEXT_DIM     = (140, 155, 195)
TEXT_FAINT   = (95, 108, 145)

HP_GREEN_1   = (60, 230, 120)
HP_GREEN_2   = (35, 175, 95)
HP_YELLOW_1  = (255, 215, 70)
HP_YELLOW_2  = (225, 170, 30)
HP_RED_1     = (255, 90, 100)
HP_RED_2     = (210, 50, 65)
HP_TRACK     = (42, 50, 80)

LOG_BG_TOP   = (24, 28, 50, 240)
LOG_BG_BOTTOM= (16, 19, 36, 240)
LOG_BORD     = (70, 92, 150, 220)
LOG_HILITE   = (60, 90, 160, 90)

DOT_ALIVE    = (70, 225, 130)
DOT_FAINT    = (70, 78, 105)
DOT_ACTIVE   = (255, 215, 70)

TURN_PILL_BG = (54, 66, 110, 255)

STATUS_COLORS = {
    "burn":      (235, 110,  60),
    "paralysis": (245, 205,  40),
    "poison":    (185,  90, 225),
    "toxic":     (150,  60, 210),
    "sleep":     (130, 150, 215),
    "freeze":    (110, 215, 235),
}
STATUS_ABBR = {
    "burn": "BRN", "paralysis": "PAR", "poison": "PSN",
    "toxic": "TOX", "sleep": "SLP",   "freeze": "FRZ",
}


# ── Sprite URLs ───────────────────────────────────────────────────

def _clean(name: str) -> str:
    return name.lower().replace(" ", "").replace(".", "").replace("'", "").replace("-", "")


def back_sprite_url(name: str) -> str:
    # Changed to the comprehensive animated GIF folder (supports up to Gen 9)
    return f"https://play.pokemonshowdown.com/sprites/ani-back/{_clean(name)}.gif"


def front_sprite_url(name: str) -> str:
    # Changed to the comprehensive animated GIF folder (supports up to Gen 9)
    return f"https://play.pokemonshowdown.com/sprites/ani/{_clean(name)}.gif"


# ── Sprite loader (async, with fallback) ─────────────────────────

async def _load_sprite(session: aiohttp.ClientSession, url: str,
                        fallback_color=(100, 140, 220)) -> Image.Image:
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as r:
            if r.status == 200:
                data = await r.read()
                img  = Image.open(io.BytesIO(data)).convert("RGBA")
                return img
    except Exception:
        pass
    # Fallback: soft glowing silhouette with a "?" mark
    size = 120
    fb = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d  = ImageDraw.Draw(fb)
    d.ellipse([10, 10, size - 10, size - 10], fill=(*fallback_color, 170))
    d.ellipse([10, 10, size - 10, size - 10], outline=(255, 255, 255, 90), width=3)
    fn = _font(_BOLD, 36)
    bbox = d.textbbox((0, 0), "?", font=fn)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text(((size - tw) / 2 - bbox[0], (size - th) / 2 - bbox[1]),
           "?", font=fn, fill=(255, 255, 255, 230))
    return fb


# ── Rounded rectangle helper (Pillow < 9 compat) ──────────────────

def _rrect(draw: ImageDraw.ImageDraw, xy, radius=8, **kwargs):
    try:
        draw.rounded_rectangle(xy, radius=radius, **kwargs)
    except AttributeError:
        draw.rectangle(xy, **kwargs)


# ── Vertical gradient panel with rounded corners ──────────────────

def _gradient_panel(size, top_color, bottom_color, radius=14,
                     outline=None, outline_width=2):
    w, h = size
    grad = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    for y in range(h):
        t = y / max(1, h - 1)
        r = int(top_color[0] + (bottom_color[0] - top_color[0]) * t)
        g = int(top_color[1] + (bottom_color[1] - top_color[1]) * t)
        b = int(top_color[2] + (bottom_color[2] - top_color[2]) * t)
        a = int(top_color[3] + (bottom_color[3] - top_color[3]) * t)
        ImageDraw.Draw(grad).line([(0, y), (w, y)], fill=(r, g, b, a))

    mask = Image.new("L", (w, h), 0)
    _rrect(ImageDraw.Draw(mask), [0, 0, w - 1, h - 1], radius=radius, fill=255)
    grad.putalpha(mask)

    if outline:
        d = ImageDraw.Draw(grad)
        _rrect(d, [0, 0, w - 1, h - 1], radius=radius,
               outline=outline, width=outline_width)
    return grad


# ── Soft radial glow (used for platforms / shadows) ────────────────

def _radial_glow(size, color, max_alpha=120):
    import numpy as np
    w, h = size
    yy, xx = np.mgrid[0:h, 0:w]
    cx, cy = (w - 1) / 2, (h - 1) / 2
    nx = (xx - cx) / (w / 2)
    ny = (yy - cy) / (h / 2)
    d = np.sqrt(nx * nx + ny * ny)
    alpha = np.clip(1 - d, 0, 1) ** 1.6 * max_alpha
    alpha = alpha.astype(np.uint8)

    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    rgba[..., 0] = color[0]
    rgba[..., 1] = color[1]
    rgba[..., 2] = color[2]
    rgba[..., 3] = alpha
    return Image.fromarray(rgba, "RGBA")


# ── HP bar colour ─────────────────────────────────────────────────

def _hp_colors(pct: float):
    if pct > 0.5:
        return HP_GREEN_1, HP_GREEN_2
    if pct > 0.2:
        return HP_YELLOW_1, HP_YELLOW_2
    return HP_RED_1, HP_RED_2


# ── Draw HP box (modern HUD card) ─────────────────────────────────

def _draw_hp_box(canvas: Image.Image,
                  x: int, y: int,
                  name: str,
                  hp_cur: int, hp_max: int,
                  status: str | None,
                  show_hp_numbers: bool,
                  team_pokes: list,
                  active_name: str,
                  side_color,
                  width: int = 330,
                  height: int = 104):

    box = _gradient_panel((width, height), PANEL_TOP, PANEL_BOTTOM,
                           radius=14, outline=PANEL_BORD, outline_width=2)
    d = ImageDraw.Draw(box)

    # Side accent stripe
    _rrect(d, [0, 0, 6, height - 1], radius=4, fill=(*side_color, 255))

    fn_name = _font(_BOLD, 22)
    fn_lv   = _font(_REG,  13)
    fn_sm   = _font(_BOLD, 12)
    fn_hp   = _font(_BOLD, 14)

    # Name
    d.text((20, 12), name.upper(), font=fn_name, fill=TEXT_MAIN)

    # Level pill
    lv_text = "Lv.100"
    bbox = d.textbbox((0, 0), lv_text, font=fn_lv)
    lv_w = bbox[2] - bbox[0]
    pill_w = lv_w + 18
    _rrect(d, [width - pill_w - 14, 16, width - 14, 36],
           radius=10, fill=(48, 56, 90, 255))
    d.text((width - pill_w - 14 + 9, 19), lv_text, font=fn_lv, fill=TEXT_DIM)

    # Status badge
    label_y = 46
    if status:
        sc   = STATUS_COLORS.get(status, (130, 130, 130))
        abbr = STATUS_ABBR.get(status, status[:3].upper())
        bbox = d.textbbox((0, 0), abbr, font=fn_sm)
        bw = bbox[2] - bbox[0] + 18
        _rrect(d, [20, label_y - 2, 20 + bw, label_y + 20], radius=8, fill=sc)
        d.text((20 + 9, label_y + 1), abbr, font=fn_sm, fill=(25, 20, 15))

    # HP bar
    bar_y  = height - 26
    bar_x  = 20
    bar_w  = width - 40
    bar_h  = 14

    _rrect(d, [bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], radius=7, fill=HP_TRACK)

    pct = max(0.0, hp_cur / hp_max) if hp_max > 0 else 0.0
    fill_w = max(6 if pct > 0 else 0, int(bar_w * pct))
    if fill_w > 0:
        top_c, bottom_c = _hp_colors(pct)
        fill_grad = _gradient_panel((fill_w, bar_h), (*top_c, 255), (*bottom_c, 255), radius=7)
        box.paste(fill_grad, (bar_x, bar_y), fill_grad)
        # re-draw to refresh draw object after paste
        d = ImageDraw.Draw(box)

    # "HP" label above bar
    d.text((bar_x, bar_y - 18), "HP", font=_font(_BOLD, 11), fill=TEXT_FAINT)

    if show_hp_numbers:
        hp_txt = f"{hp_cur} / {hp_max}"
        bbox = d.textbbox((0, 0), hp_txt, font=fn_hp)
        tw = bbox[2] - bbox[0]
        d.text((bar_x + bar_w - tw, bar_y - 19), hp_txt, font=fn_hp, fill=TEXT_DIM)

    # Team dots (bottom-left, beneath bar — only if room)
    dot_r   = 5
    dot_gap = 15
    dot_x   = bar_x
    dot_y   = label_y + 9 if not status else label_y + 9
    # place dots to the right of status badge / name row, aligned with status row
    dot_y = 46 + 9
    start_x = 20
    if status:
        sc_abbr_w = d.textbbox((0, 0), STATUS_ABBR.get(status, "XXX"), font=fn_sm)[2] + 18
        start_x = 20 + sc_abbr_w + 12

    for i, (pk_name, pk_cur, pk_max) in enumerate(team_pokes):
        cx = start_x + i * dot_gap
        if cx > width - 16:
            break
        if pk_name == active_name:
            color, r = DOT_ACTIVE, dot_r + 1
            d.ellipse([cx - r - 2, dot_y - r - 2, cx + r + 2, dot_y + r + 2],
                      outline=(*DOT_ACTIVE, 120), width=2)
        elif pk_cur <= 0:
            color, r = DOT_FAINT, dot_r
        else:
            color, r = DOT_ALIVE, dot_r
        d.ellipse([cx - r, dot_y - r, cx + r, dot_y + r], fill=color)

    canvas.alpha_composite(box, (x, y))


# ── Draw log box ────────────────────────────────────────────────────

_EMOJI_STRIP = True


def _strip_emoji(text: str) -> str:
    out = []
    for ch in text:
        if ord(ch) < 0x2190:  # keep normal punctuation / latin
            out.append(ch)
        elif ch in "★☆":
            out.append(ch)
    cleaned = "".join(out)
    return " ".join(cleaned.split())


def _draw_log(canvas: Image.Image, x: int, y: int,
               lines: list[str], turn_num: int,
               width=960, height=190):

    box = _gradient_panel((width, height), LOG_BG_TOP, LOG_BG_BOTTOM,
                           radius=16, outline=LOG_BORD, outline_width=2)
    d = ImageDraw.Draw(box)

    fn_header = _font(_BOLD, 14)
    fn_line   = _font(_REG, 16)
    fn_line_b = _font(_BOLD, 16)

    # Header row
    d.text((22, 14), "BATTLE LOG", font=fn_header, fill=(140, 165, 235))
    turn_txt = f"TURN {turn_num}"
    bbox = d.textbbox((0, 0), turn_txt, font=fn_header)
    tw = bbox[2] - bbox[0]
    d.text((width - tw - 22, 14), turn_txt, font=fn_header, fill=TEXT_FAINT)

    _rrect(d, [22, 40, width - 22, 41], radius=1, fill=(70, 85, 130, 160))

    shown = [l for l in lines if l.strip()][-4:]
    row_h = 28
    base_y = 48

    for i, line in enumerate(shown):
        clean = _strip_emoji(line)
        if len(clean) > 90:
            clean = clean[:87] + "..."

        is_last = (i == len(shown) - 1)
        ty = base_y + i * row_h

        if is_last:
            _rrect(d, [16, ty - 2, width - 16, ty + row_h - 6],
                   radius=8, fill=LOG_HILITE)

        font  = fn_line_b if is_last else fn_line
        color = TEXT_MAIN if is_last else TEXT_DIM
        alpha_color = color if is_last else TEXT_DIM

        # bullet
        d.ellipse([24, ty + row_h / 2 - 9, 24 + 6, ty + row_h / 2 - 3],
                  fill=(120, 145, 220) if is_last else (70, 85, 120))

        d.text((40, ty + (row_h - 20) / 2), clean, font=font, fill=alpha_color)

    canvas.alpha_composite(box, (x, y))


# ── Top header bar (player names + turn / vs) ──────────────────────

def _draw_header(canvas: Image.Image, x: int, y: int, width: int, height: int,
                  p0_name: str, p1_name: str):

    box = _gradient_panel((width, height), PANEL_TOP, PANEL_BOTTOM,
                           radius=14, outline=PANEL_BORD, outline_width=2)
    d = ImageDraw.Draw(box)

    fn_name = _font(_BOLD, 20)
    fn_vs   = _font(_BOLD, 14)

    # Player 0 (left) — blue accent dot
    d.ellipse([18, height / 2 - 6, 30, height / 2 + 6], fill=ACCENT_BLUE)
    p0 = p0_name if len(p0_name) <= 18 else p0_name[:16] + "…"
    d.text((40, height / 2), p0, font=fn_name, fill=TEXT_MAIN, anchor="lm")

    # Player 1 (right) — red accent dot
    p1 = p1_name if len(p1_name) <= 18 else p1_name[:16] + "…"
    bbox = d.textbbox((0, 0), p1, font=fn_name)
    p1w = bbox[2] - bbox[0]
    d.text((width - 40 - p1w, height / 2), p1, font=fn_name, fill=TEXT_MAIN, anchor="lm")
    d.ellipse([width - 30, height / 2 - 6, width - 18, height / 2 + 6], fill=ACCENT_RED)

    # VS pill — center
    vs_w, vs_h = 56, 28
    vs_x = (width - vs_w) / 2
    vs_y = (height - vs_h) / 2
    _rrect(d, [vs_x, vs_y, vs_x + vs_w, vs_y + vs_h], radius=14, fill=TURN_PILL_BG)
    d.text((vs_x + vs_w / 2, vs_y + vs_h / 2), "VS", font=fn_vs,
           fill=(220, 225, 245), anchor="mm")

    canvas.alpha_composite(box, (x, y))


# ── Turn pill (top-right of battlefield) ────────────────────────────

def _draw_turn_pill(canvas, x, y, turn_num):
    txt = f"TURN {turn_num}"
    fn = _font(_BOLD, 14)
    tmp = Image.new("RGBA", (1, 1))
    d_tmp = ImageDraw.Draw(tmp)
    bbox = d_tmp.textbbox((0, 0), txt, font=fn)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad_x, pad_y = 16, 9
    w, h = tw + pad_x * 2, th + pad_y * 2

    pill = _gradient_panel((w, h), (54, 66, 110, 235), (38, 46, 80, 235),
                            radius=h // 2, outline=PANEL_BORD, outline_width=2)
    d = ImageDraw.Draw(pill)
    d.text((w / 2, h / 2 - bbox[1] / 2 - 1), txt, font=fn, fill=(210, 220, 250), anchor="mm")
    canvas.alpha_composite(pill, (x, y))


# ── MAIN RENDER FUNCTION ──────────────────────────────────────────

async def render_battle(
    # Player 0 (bottom-left, back sprite)
    p0_name: str, p0_poke: str, p0_hp: int, p0_max: int,
    p0_status: str | None, p0_team: list,

    # Player 1 (top-right, front sprite)
    p1_name: str, p1_poke: str, p1_hp: int, p1_max: int,
    p1_status: str | None, p1_team: list,

    # Log lines (last ~8 are kept)
    log_lines: list[str],

    turn_num: int = 1,
) -> io.BytesIO:
    """
    Returns a BytesIO PNG of the battle scene.

    p0_team / p1_team: list of (pokemon_name, hp_cur, hp_max)
    """

    async with aiohttp.ClientSession(
        headers={"User-Agent": "EchleonBot/1.0"}
    ) as session:
        back_img, front_img = await asyncio.gather(
            _load_sprite(session, back_sprite_url(p0_poke),  (90, 150, 230)),
            _load_sprite(session, front_sprite_url(p1_poke), (235, 110, 110)),
        )

    sw, sh = W * SS, H * SS

    # ── Background gradient ─────────────────────────────────────
    canvas = _gradient_panel((sw, sh), BG_TOP, BG_BOTTOM, radius=0)
    canvas = canvas.convert("RGBA")

    # ── Layout (in 1x coords, then scaled by SS) ────────────────
    margin       = 20
    header_h     = 56
    field_top    = margin + header_h + 12         # 88
    field_h      = 312
    field_bottom = field_top + field_h            # 400
    log_top      = field_bottom + 12              # 412
    log_h        = H - log_top - margin           # 168

    def S(*vals):
        return tuple(int(v * SS) for v in vals)

    # ── Header (player names + VS) ───────────────────────────────
    _draw_header(canvas, *S(margin, margin),
                  int((W - margin * 2) * SS), int(header_h * SS),
                  p0_name, p1_name)

    # ── Battlefield panel ───────────────────────────────────────
    field = _gradient_panel(
        (int((W - margin * 2) * SS), int(field_h * SS)),
        (26, 31, 54, 235), (15, 18, 32, 235),
        radius=18, outline=FIELD_BORD, outline_width=2
    )
    fd = ImageDraw.Draw(field)

    # Grid lines inside field
    for gx in range(0, field.width, 70 * SS):
        fd.line([(gx, 0), (gx, field.height)], fill=GRID, width=1)
    for gy in range(0, field.height, 70 * SS):
        fd.line([(0, gy), (field.width, gy)], fill=GRID, width=1)

    canvas.alpha_composite(field, S(margin, field_top))

    # ── Platforms (radial glow ellipses) ────────────────────────
    plat_w, plat_h = 280, 70

    def paste_platform(cx, cy, color):
        glow = _radial_glow((int(plat_w * 1.6 * SS), int(plat_h * 2.2 * SS)), color, max_alpha=70)
        gx = int((cx - plat_w * 1.6 / 2) * SS) + margin * SS
        gy = int((cy - plat_h * 2.2 / 2) * SS) + field_top * SS
        canvas.alpha_composite(glow, (gx, gy))

        ring = Image.new("RGBA", (int(plat_w * SS), int(plat_h * SS)), (0, 0, 0, 0))
        rd = ImageDraw.Draw(ring)
        rd.ellipse([0, 0, ring.width - 1, ring.height - 1],
                   outline=(*color, 160), width=int(2 * SS))
        rd.ellipse([0, 0, ring.width - 1, ring.height - 1], fill=(*color, 35))
        rx = int((cx - plat_w / 2) * SS) + margin * SS
        ry = int((cy - plat_h / 2) * SS) + field_top * SS
        canvas.alpha_composite(ring, (rx, ry))

    # Opponent platform — top right of field
    opp_cx, opp_cy = (W - margin * 2) * 0.74, field_h * 0.40
    paste_platform(opp_cx, opp_cy, PLATFORM_R)

    # Player platform — bottom left of field
    ply_cx, ply_cy = (W - margin * 2) * 0.26, field_h * 0.74
    paste_platform(ply_cx, ply_cy, PLATFORM_L)

    # ── Sprites ──────────────────────────────────────────────────
    SPRITE_SIZE = 150

    def paste_sprite(sprite: Image.Image, cx_field, cy_field):
        spr = sprite.copy()
        w0, h0 = spr.size
        scale = SPRITE_SIZE / max(w0, h0)
        new_w, new_h = max(1, int(w0 * scale)), max(1, int(h0 * scale))
        spr = spr.resize((new_w, new_h), Image.LANCZOS)
        spr = spr.resize((spr.width * SS, spr.height * SS), Image.LANCZOS)
        sw_, sh_ = spr.size

        cx = int(cx_field * SS) + margin * SS
        cy = int(cy_field * SS) + field_top * SS

        img_x = cx - sw_ // 2
        img_y = cy - sh_

        # soft drop shadow
        shadow = _radial_glow((sw_ + 40 * SS, int(40 * SS)), (0, 0, 0), max_alpha=110)
        canvas.alpha_composite(shadow, (img_x - 20 * SS, cy - 20 * SS))

        canvas.alpha_composite(spr, (img_x, img_y))

    paste_sprite(back_img,  ply_cx, ply_cy + plat_h * 0.32)
    paste_sprite(front_img, opp_cx, opp_cy + plat_h * 0.32)

    # ── Turn pill — top-right corner of field ───────────────────
    _draw_turn_pill(canvas, *S(margin + (W - margin * 2) - 96, field_top + 14), turn_num)

    # ── HP boxes ─────────────────────────────────────────────────
    hp_w, hp_h = 330, 104

    # Opponent box — top-left of field
    _draw_hp_box(
        canvas, *S(margin + 14, field_top + 14),
        name=p1_poke, hp_cur=p1_hp, hp_max=p1_max,
        status=p1_status, show_hp_numbers=False,
        team_pokes=p1_team, active_name=p1_poke,
        side_color=ACCENT_RED,
        width=int(hp_w * SS), height=int(hp_h * SS),
    )

    # Player box — bottom-right of field
    _draw_hp_box(
        canvas, *S(margin + (W - margin * 2) - hp_w - 14, field_bottom - hp_h - 14),
        name=p0_poke, hp_cur=p0_hp, hp_max=p0_max,
        status=p0_status, show_hp_numbers=True,
        team_pokes=p0_team, active_name=p0_poke,
        side_color=ACCENT_BLUE,
        width=int(hp_w * SS), height=int(hp_h * SS),
    )

    # ── Log box ──────────────────────────────────────────────────
    _draw_log(
        canvas, *S(margin, log_top),
        lines=log_lines if log_lines else ["Battle started!"],
        turn_num=turn_num,
        width=int((W - margin * 2) * SS), height=int(log_h * SS),
    )

        # ── Downsample for crisp anti-aliasing ─────────────────────
    final = canvas.resize((W, H), Image.LANCZOS)

    out = io.BytesIO()
    final.convert("RGB").save(out, format="PNG", optimize=True)
    out.seek(0)
    return out  # Fixed: Added 'out' here!

# ── Convenience wrapper called from pokemon_battle.py ─────────────

async def make_battle_file(state) -> "discord.File":
    """
    Takes a BattleState and returns a discord.File ready to send.
    Import discord here only when called from the bot.
    """
    import discord

    def team_list(p_idx: int):
        result = []
        for i, pk in enumerate(state.teams[p_idx]):
            hc = state.team_hp[p_idx][i][0]
            hm = state.team_hp[p_idx][i][1]
            result.append((pk["name"], hc, hm))
        return result

    buf = await render_battle(
        p0_name   = state.players[0].display_name,
        p0_poke   = state.pokemon[0]["name"],
        p0_hp     = state.cur_hp[0],
        p0_max    = state.max_hp[0],
        p0_status = state.statuses[0],
        p0_team   = team_list(0),

        p1_name   = state.players[1].display_name,
        p1_poke   = state.pokemon[1]["name"],
        p1_hp     = state.cur_hp[1],
        p1_max    = state.max_hp[1],
        p1_status = state.statuses[1],
        p1_team   = team_list(1),

        log_lines = state.log.split("\n") if state.log else ["Battle started!"],
        turn_num  = state.turn_num,
    )
    return discord.File(buf, filename="battle.png")


# ── Render Loader Safeguard ──────────────────────────────────────────

async def setup(bot):
    """Placeholder to prevent the automated extension loader from crashing."""
    pass  # Fixed: Properly indented!
