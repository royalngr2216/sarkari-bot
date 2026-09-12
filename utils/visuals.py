"""
Shared visual toolkit — ECHLEON design system.

Every Pillow-based render in the bot (profile cards, game animations,
reveal cards, leaderboards) should pull fonts/colors/helpers from here
instead of redefining its own. This is what keeps every image looking
like it belongs to the same bot.

Usage:
    from utils.visuals import FONT_BOLD, COLORS, rounded_rectangle, add_glow

    font = FONT_BOLD(48)
    img = Image.new("RGBA", (800, 400), COLORS["bg"])
"""

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os
import functools

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_DIR = os.path.join(BASE_DIR, "assets", "fonts")


# ─────────────────────────────────────────────────────────────────
# FONTS
# ─────────────────────────────────────────────────────────────────
# Cached per (weight, size) so repeated calls (e.g. inside animation
# frame loops) don't re-read the .ttf off disk every frame.

@functools.lru_cache(maxsize=None)
def _load(weight: str, size: int) -> ImageFont.FreeTypeFont:
    path = os.path.join(FONT_DIR, f"Poppins-{weight}.ttf")
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        # Falls back gracefully if fonts are ever missing (e.g. fresh
        # clone without assets/) instead of crashing every render.
        return ImageFont.load_default(size=size)


def FONT_BOLD(size: int) -> ImageFont.FreeTypeFont:
    return _load("Bold", size)


def FONT_SEMIBOLD(size: int) -> ImageFont.FreeTypeFont:
    return _load("SemiBold", size)


def FONT_MEDIUM(size: int) -> ImageFont.FreeTypeFont:
    return _load("Medium", size)


def FONT_REGULAR(size: int) -> ImageFont.FreeTypeFont:
    return _load("Regular", size)


# ─────────────────────────────────────────────────────────────────
# COLOR PALETTE
# ─────────────────────────────────────────────────────────────────
# Keep every card/animation pulling from this one palette so a slots
# win and a profile card and a battle render all feel related.

COLORS = {
    "bg_dark":      (20, 22, 30, 255),
    "bg_panel":     (30, 33, 44, 255),
    "bg_panel_alt": (38, 41, 54, 255),

    "accent":       (114, 137, 218, 255),   # blurple-ish brand accent
    "accent_soft":  (114, 137, 218, 90),

    "success":      (67, 214, 138, 255),
    "danger":       (237, 78, 92, 255),
    "warning":      (245, 191, 66, 255),

    "text_primary":   (245, 246, 250, 255),
    "text_secondary": (160, 165, 180, 255),
    "text_muted":     (100, 104, 120, 255),

    "gold":   (255, 205, 66, 255),
    "silver": (200, 205, 215, 255),
    "bronze": (205, 140, 90, 255),
}

# Rarity colors — reused by pokemons, hunt/fish loot, mine ores, etc.
# so "rarity" always reads the same way across every feature.
RARITY_COLORS = {
    "common":    (163, 168, 178, 255),
    "uncommon":  (67, 214, 138, 255),
    "rare":      (66, 165, 245, 255),
    "epic":      (170, 102, 245, 255),
    "legendary": (255, 175, 64, 255),
    "mythic":    (245, 78, 140, 255),
}


# ─────────────────────────────────────────────────────────────────
# SHAPE HELPERS
# ─────────────────────────────────────────────────────────────────

def rounded_rectangle(draw: ImageDraw.ImageDraw, box, radius, fill=None, outline=None, width=1):
    """Thin wrapper so every card uses identical corner rounding."""
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def add_glow(base: Image.Image, color, blur=18, intensity=1.0) -> Image.Image:
    """
    Returns a new RGBA image with a soft colored glow behind base's
    alpha silhouette. Use for win celebrations / rare-item reveals —
    composite the result BEHIND the original image.
    """
    alpha = base.split()[-1]
    glow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    solid = Image.new("RGBA", base.size, color)
    glow.paste(solid, (0, 0), alpha)
    glow = glow.filter(ImageFilter.GaussianBlur(blur))
    if intensity != 1.0:
        r, g, b, a = glow.split()
        a = a.point(lambda p: min(255, int(p * intensity)))
        glow = Image.merge("RGBA", (r, g, b, a))
    return glow


def vertical_gradient(size, top_color, bottom_color) -> Image.Image:
    """Simple top-to-bottom gradient panel, used for card backgrounds."""
    w, h = size
    base = Image.new("RGBA", (1, h), (0, 0, 0, 0))
    for y in range(h):
        t = y / max(h - 1, 1)
        r = int(top_color[0] + (bottom_color[0] - top_color[0]) * t)
        g = int(top_color[1] + (bottom_color[1] - top_color[1]) * t)
        b = int(top_color[2] + (bottom_color[2] - top_color[2]) * t)
        a = int(top_color[3] + (bottom_color[3] - top_color[3]) * t)
        base.putpixel((0, y), (r, g, b, a))
    return base.resize((w, h))


def progress_bar(draw: ImageDraw.ImageDraw, box, fraction, bg_color, fill_color, radius=None):
    """
    box = (x1, y1, x2, y2). fraction clamped 0..1.
    Used for XP bars, HP bars, cooldown bars — anywhere a stat needs
    a visual fill instead of just a number.
    """
    fraction = max(0.0, min(1.0, fraction))
    x1, y1, x2, y2 = box
    if radius is None:
        radius = (y2 - y1) // 2
    draw.rounded_rectangle(box, radius=radius, fill=bg_color)
    if fraction > 0:
        fill_w = x1 + (x2 - x1) * fraction
        draw.rounded_rectangle((x1, y1, fill_w, y2), radius=radius, fill=fill_color)


def circular_avatar(avatar_img: Image.Image, size: int, border_color=None, border_width=0) -> Image.Image:
    """Crops any avatar image (fetched via discord.Asset.read()) into a circle."""
    avatar_img = avatar_img.convert("RGBA").resize((size, size))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)

    if border_color and border_width > 0:
        bordered_size = size + border_width * 2
        out = Image.new("RGBA", (bordered_size, bordered_size), (0, 0, 0, 0))
        ImageDraw.Draw(out).ellipse((0, 0, bordered_size, bordered_size), fill=border_color)
        out.paste(avatar_img, (border_width, border_width), mask)
        return out

    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(avatar_img, (0, 0), mask)
    return out


def text_with_shadow(draw: ImageDraw.ImageDraw, pos, text, font, fill, shadow_color=(0, 0, 0, 160), offset=(2, 2), anchor=None):
    """Draws drop-shadowed text — makes text pop off busy/gradient backgrounds."""
    x, y = pos
    draw.text((x + offset[0], y + offset[1]), text, font=font, fill=shadow_color, anchor=anchor)
    draw.text((x, y), text, font=font, fill=fill, anchor=anchor)
