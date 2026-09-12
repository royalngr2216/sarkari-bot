"""
Renders the .leaderboard command as a single image card instead of a
plain text embed — avatars, medal accents for the top 3, and the
requester's own rank pinned at the bottom if they're outside the top 10.
"""

import io
import aiohttp
from PIL import Image, ImageDraw, ImageFont, ImageOps

from utils.titles import get_equipped, TITLES

# ─────────────────────────────────────────────────────────────────
# LAYOUT
# ─────────────────────────────────────────────────────────────────

WIDTH        = 940
HEADER_H     = 170
ROW_H        = 92
ROW_GAP      = 10
PAD_X        = 36
YOU_DIVIDER_H = 46
FOOTER_H     = 46

BG_TOP     = (20, 22, 34)
BG_BOTTOM  = (11, 12, 20)
CARD_BG    = (28, 30, 46)
CARD_BG_ME = (36, 32, 54)
TEXT_MAIN  = (240, 241, 245)
TEXT_SUB   = (150, 153, 168)

RANK_COLORS = {
    1: (255, 215, 0),     # gold
    2: (200, 205, 214),   # silver
    3: (205, 127, 50),    # bronze
}
RANK_DEFAULT = (88, 101, 242)

MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}


def _load_font(size: int, weight: str = "Regular") -> ImageFont.FreeTypeFont:
    candidates = [
        f"/usr/share/fonts/truetype/google-fonts/Poppins-{weight}.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


FONT_TITLE   = _load_font(40, "Bold")
FONT_SUB     = _load_font(19, "Regular")
FONT_RANK    = _load_font(26, "Bold")
FONT_NAME    = _load_font(24, "Medium")
FONT_BADGE   = _load_font(15, "Medium")
FONT_CASH    = _load_font(26, "Bold")
FONT_FOOTER  = _load_font(16, "Regular")


def _vertical_gradient(w, h, top, bottom):
    base = Image.new("RGB", (w, h), top)
    draw = ImageDraw.Draw(base)
    for y in range(h):
        t = y / max(h - 1, 1)
        color = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        draw.line([(0, y), (w, y)], fill=color)
    return base


def _rounded_mask(size, radius):
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([(0, 0), (size[0] - 1, size[1] - 1)], radius=radius, fill=255)
    return mask


async def _fetch_avatar(session: aiohttp.ClientSession, url: str, size: int) -> Image.Image:
    try:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.read()
                img = Image.open(io.BytesIO(data)).convert("RGBA")
                img = ImageOps.fit(img, (size, size))
                mask = Image.new("L", (size, size), 0)
                ImageDraw.Draw(mask).ellipse([(0, 0), (size, size)], fill=255)
                out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
                out.paste(img, (0, 0), mask)
                return out
    except Exception:
        pass
    # fallback: flat circle placeholder
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(out).ellipse([(0, 0), (size, size)], fill=(70, 74, 94, 255))
    return out


def _truncate(draw, text, font, max_w):
    if draw.textlength(text, font=font) <= max_w:
        return text
    while text and draw.textlength(text + "…", font=font) > max_w:
        text = text[:-1]
    return text + "…"


def _draw_row(base, draw, y, rank, name, cash_text, title_key, avatar, *, is_requester=False):
    x0, x1 = PAD_X, WIDTH - PAD_X
    h = ROW_H

    bg = CARD_BG_ME if is_requester else CARD_BG
    draw.rounded_rectangle([(x0, y), (x1, y + h)], radius=18, fill=bg)

    accent = RANK_COLORS.get(rank, RANK_DEFAULT)
    draw.rounded_rectangle([(x0, y), (x0 + 6, y + h)], radius=3, fill=accent)

    # Rank badge (medal for top 3, number otherwise)
    rank_cx = x0 + 56
    rank_cy = y + h // 2
    if rank in MEDALS:
        draw.ellipse([(rank_cx - 26, rank_cy - 26), (rank_cx + 26, rank_cy + 26)], fill=accent)
        rtext = str(rank)
        tw = draw.textlength(rtext, font=FONT_RANK)
        draw.text((rank_cx - tw / 2, rank_cy - 16), rtext, font=FONT_RANK, fill=(20, 20, 20))
    else:
        draw.ellipse([(rank_cx - 26, rank_cy - 26), (rank_cx + 26, rank_cy + 26)], outline=(70, 74, 94), width=2)
        rtext = str(rank)
        tw = draw.textlength(rtext, font=FONT_RANK)
        draw.text((rank_cx - tw / 2, rank_cy - 16), rtext, font=FONT_RANK, fill=TEXT_MAIN)

    # Avatar
    av_x, av_y = x0 + 100, y + (h - 60) // 2
    base.paste(avatar, (av_x, av_y), avatar)

    # Name + title badge
    name_x = av_x + 76
    max_name_w = 380
    badge = ""
    if title_key and title_key in TITLES:
        badge = f"{TITLES[title_key]['emoji']} {TITLES[title_key]['label']}"

    if badge:
        draw.text((name_x, y + 20), _truncate(draw, name, FONT_NAME, max_name_w), font=FONT_NAME, fill=TEXT_MAIN)
        badge_color = TITLES[title_key]["color"]
        draw.text((name_x, y + 52), badge, font=FONT_BADGE, fill=badge_color)
    else:
        draw.text((name_x, y + h // 2 - 14), _truncate(draw, name, FONT_NAME, max_name_w), font=FONT_NAME, fill=TEXT_MAIN)

    # Cash, right aligned
    cw = draw.textlength(cash_text, font=FONT_CASH)
    draw.text((x1 - 28 - cw, y + h // 2 - 15), cash_text, font=FONT_CASH, fill=(87, 242, 135))


async def render_leaderboard(
    top_entries: list[dict],
    requester_entry: dict | None,
    format_cash,
) -> io.BytesIO:
    """
    top_entries: list of {"rank", "name", "cash", "user_id", "avatar_url"}
    requester_entry: same shape for the requester if they're outside the
                      top 10 shown, or None if they're already in it / have no cash.
    """
    n_rows = len(top_entries)
    extra_h = (YOU_DIVIDER_H + ROW_H + ROW_GAP) if requester_entry else 0
    total_h = HEADER_H + n_rows * (ROW_H + ROW_GAP) + extra_h + FOOTER_H

    base = _vertical_gradient(WIDTH, total_h, BG_TOP, BG_BOTTOM).convert("RGBA")
    draw = ImageDraw.Draw(base)

    # Header
    draw.text((PAD_X, 34), "LEADERBOARD", font=FONT_TITLE, fill=TEXT_MAIN)
    draw.text((PAD_X, 88), "Top trainers by net worth", font=FONT_SUB, fill=TEXT_SUB)
    draw.line([(PAD_X, HEADER_H - 20), (WIDTH - PAD_X, HEADER_H - 20)], fill=(50, 53, 70), width=2)

    async with aiohttp.ClientSession() as session:
        y = HEADER_H
        for entry in top_entries:
            avatar = await _fetch_avatar(session, entry["avatar_url"], 60)
            _draw_row(
                base, draw, y,
                entry["rank"], entry["name"], format_cash(entry["cash"]),
                entry.get("title_key"), avatar,
            )
            y += ROW_H + ROW_GAP

        if requester_entry:
            mid_y = y + YOU_DIVIDER_H // 2
            draw.line([(PAD_X, mid_y - 1), (WIDTH // 2 - 40, mid_y - 1)], fill=(50, 53, 70), width=2)
            you_text = "YOUR RANK"
            tw = draw.textlength(you_text, font=FONT_SUB)
            draw.text((WIDTH // 2 - tw / 2, mid_y - 12), you_text, font=FONT_SUB, fill=TEXT_SUB)
            draw.line([(WIDTH // 2 + 40, mid_y - 1), (WIDTH - PAD_X, mid_y - 1)], fill=(50, 53, 70), width=2)
            y += YOU_DIVIDER_H

            avatar = await _fetch_avatar(session, requester_entry["avatar_url"], 60)
            _draw_row(
                base, draw, y,
                requester_entry["rank"], requester_entry["name"], format_cash(requester_entry["cash"]),
                requester_entry.get("title_key"), avatar,
                is_requester=True,
            )
            y += ROW_H

    footer_text = "ECHLEON  •  .titles to spend big  •  .cash to check yourself"
    draw.text((PAD_X, total_h - 34), footer_text, font=FONT_FOOTER, fill=TEXT_SUB)

    buf = io.BytesIO()
    base.convert("RGB").save(buf, format="PNG")
    buf.seek(0)
    return buf
