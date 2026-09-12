"""
Shared Pillow drawing helpers for the image-based game renderers
(crash graph, blackjack table). Keeps the visual language consistent
with utils/leaderboard_render.py — dark gradients, rounded cards,
Poppins type — without duplicating font/gradient code in every file.
"""

import io
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

_FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "fonts")

_FONT_FILES = {
    "Bold": "Poppins-Bold.ttf",
    "SemiBold": "Poppins-SemiBold.ttf",
    "Medium": "Poppins-Medium.ttf",
    "Regular": "Poppins-Regular.ttf",
}

_font_cache = {}


def load_font(size: int, weight: str = "Regular") -> ImageFont.FreeTypeFont:
    key = (size, weight)
    if key in _font_cache:
        return _font_cache[key]

    candidates = [
        os.path.join(_FONT_DIR, _FONT_FILES.get(weight, _FONT_FILES["Regular"])),
        f"/usr/share/fonts/truetype/google-fonts/Poppins-{weight}.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    font = None
    for path in candidates:
        try:
            font = ImageFont.truetype(path, size)
            break
        except Exception:
            continue
    if font is None:
        font = ImageFont.load_default()
    _font_cache[key] = font
    return font


def vertical_gradient(w, h, top, bottom):
    base = Image.new("RGB", (w, h), top)
    draw = ImageDraw.Draw(base)
    for y in range(h):
        t = y / max(h - 1, 1)
        color = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        draw.line([(0, y), (w, y)], fill=color)
    return base


def radial_glow(w, h, center, radius, color, max_alpha=140):
    """Soft radial glow used behind rockets / result banners."""
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    cx, cy = center
    steps = 24
    for i in range(steps, 0, -1):
        r = radius * (i / steps)
        alpha = int(max_alpha * (1 - i / steps) ** 1.6)
        gd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*color, alpha))
    return glow


def rounded_rect(draw, box, radius, fill=None, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def text_center(draw, cx, y, text, font, fill, anchor_top=True):
    tw = draw.textlength(text, font=font)
    x = cx - tw / 2
    draw.text((x, y), text, font=font, fill=fill)
    return tw


def add_noise_vignette(base: Image.Image, strength=60):
    """Subtle darkened vignette corners so the card doesn't look flat."""
    w, h = base.size
    vign = Image.new("L", (w, h), 0)
    vd = ImageDraw.Draw(vign)
    vd.rectangle([0, 0, w, h], fill=0)
    vd.ellipse([-w * 0.3, -h * 0.3, w * 1.3, h * 1.3], fill=strength)
    vign = vign.filter(ImageFilter.GaussianBlur(80))
    dark = Image.new("RGB", (w, h), (0, 0, 0))
    base_rgba = base.convert("RGB")
    return Image.composite(base_rgba, dark, ImageOps_invert(vign))


def ImageOps_invert(img_l):
    # tiny local inline invert to avoid importing ImageOps just for this
    return img_l.point(lambda p: 255 - p)


def to_buffer(img: Image.Image) -> io.BytesIO:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf
