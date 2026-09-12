from discord.ext import commands
import discord
import io
import aiohttp

from PIL import Image, ImageDraw

from utils.economy import (
    create_account,
    economy_collection,
    get_cash,
    format_cash
)
from utils.stats import (
    stats_collection,
    create_profile
)
from utils.titles import (
    get_equipped,
    TITLES
)
from utils.achievements import ALL_ACHIEVEMENTS
from utils.visuals import (
    FONT_BOLD,
    FONT_SEMIBOLD,
    FONT_MEDIUM,
    FONT_REGULAR,
    COLORS,
    rounded_rectangle,
    vertical_gradient,
    progress_bar,
    circular_avatar,
    text_with_shadow,
    add_glow
)


CARD_W, CARD_H = 1000, 420


async def _fetch_avatar_bytes(member: discord.Member) -> bytes:
    async with aiohttp.ClientSession() as session:
        async with session.get(member.display_avatar.replace(size=256).url) as resp:
            return await resp.read()


def _stat_block(draw, x, y, label, value, accent):
    """One small stat cell: big value on top, muted label under it."""
    text_with_shadow(draw, (x, y), value, FONT_BOLD(30), accent)
    draw.text((x, y + 40), label, font=FONT_REGULAR(18), fill=COLORS["text_secondary"])


async def build_profile_card(member: discord.Member) -> io.BytesIO:

    create_account(member.id)
    create_profile(member.id)

    cash = get_cash(member.id)

    stats = stats_collection.find_one({"user_id": str(member.id)}) or {}
    econ = economy_collection.find_one({"user_id": str(member.id)}) or {}

    wins = stats.get("wins", 0)
    losses = stats.get("losses", 0)
    games_played = stats.get("games_played", wins + losses)
    biggest_win = stats.get("biggest_win", 0)
    best_streak = stats.get("best_streak", 0)
    total_gambled = stats.get("total_gambled", 0)

    win_rate = (wins / games_played * 100) if games_played else 0.0

    owned_achievements = len(econ.get("claimed_achievements", []))
    total_achievements = len(ALL_ACHIEVEMENTS)

    equipped_key = get_equipped(member.id)
    title_info = TITLES.get(equipped_key) if equipped_key else None

    # ── BASE CARD ──────────────────────────────────────────────
    card = vertical_gradient((CARD_W, CARD_H), COLORS["bg_panel"], COLORS["bg_dark"])
    draw = ImageDraw.Draw(card)

    rounded_rectangle(draw, (0, 0, CARD_W - 1, CARD_H - 1), 28,
                       outline=COLORS["accent"], width=3)

    # Accent side stripe, tinted by equipped title color if any
    stripe_color = title_info["color"] if title_info else 0x7289DA
    stripe_rgb = ((stripe_color >> 16) & 255, (stripe_color >> 8) & 255, stripe_color & 255, 255)
    draw.rounded_rectangle((0, 0, 10, CARD_H - 1), radius=0, fill=stripe_rgb)

    # ── AVATAR ─────────────────────────────────────────────────
    try:
        avatar_bytes = await _fetch_avatar_bytes(member)
        avatar_img = Image.open(io.BytesIO(avatar_bytes))
    except Exception:
        avatar_img = Image.new("RGBA", (256, 256), COLORS["bg_panel_alt"])

    avatar_size = 160
    avatar = circular_avatar(avatar_img, avatar_size, border_color=stripe_rgb, border_width=6)

    glow = add_glow(avatar, stripe_rgb, blur=22, intensity=0.6)
    card.alpha_composite(glow, (40 - 22, 40 - 22))
    card.alpha_composite(avatar, (40, 40))

    # ── NAME + TITLE ───────────────────────────────────────────
    name_x = 40 + avatar_size + 30
    name_y = 48

    text_with_shadow(draw, (name_x, name_y), member.display_name, FONT_BOLD(40), COLORS["text_primary"])

    if title_info:
        badge_text = f"{title_info['emoji']} {title_info['label']}"
        draw.text((name_x, name_y + 52), badge_text, font=FONT_SEMIBOLD(22), fill=stripe_rgb)
    else:
        draw.text((name_x, name_y + 52), "No title equipped", font=FONT_REGULAR(20), fill=COLORS["text_muted"])

    # ── CASH ───────────────────────────────────────────────────
    text_with_shadow(draw, (name_x, name_y + 100), format_cash(cash), FONT_BOLD(34), COLORS["gold"])
    draw.text((name_x, name_y + 140), "Cash Balance", font=FONT_REGULAR(18), fill=COLORS["text_secondary"])

    # ── DIVIDER ────────────────────────────────────────────────
    divider_y = 230
    draw.line((40, divider_y, CARD_W - 40, divider_y), fill=COLORS["bg_panel_alt"], width=2)

    # ── STAT GRID ──────────────────────────────────────────────
    stat_y = divider_y + 30
    col_w = (CARD_W - 80) // 4

    _stat_block(draw, 40 + col_w * 0, stat_y, "Games Played", f"{games_played:,}", COLORS["accent"])
    _stat_block(draw, 40 + col_w * 1, stat_y, "Win Rate", f"{win_rate:.1f}%", COLORS["success"])
    _stat_block(draw, 40 + col_w * 2, stat_y, "Biggest Win", format_cash(biggest_win), COLORS["warning"])
    _stat_block(draw, 40 + col_w * 3, stat_y, "Best Streak", f"{best_streak:,}", COLORS["danger"])

    # ── ACHIEVEMENT PROGRESS BAR ─────────────────────────────────
    ach_y = stat_y + 80
    draw.text((40, ach_y), f"Achievements  {owned_achievements}/{total_achievements}",
              font=FONT_MEDIUM(20), fill=COLORS["text_primary"])

    fraction = (owned_achievements / total_achievements) if total_achievements else 0
    progress_bar(
        draw,
        (40, ach_y + 34, CARD_W - 40, ach_y + 54),
        fraction,
        COLORS["bg_panel_alt"],
        COLORS["accent"]
    )

    buf = io.BytesIO()
    card.save(buf, format="PNG")
    buf.seek(0)
    return buf


class Profile(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="profile", aliases=["rank", "card"])
    async def profile(self, ctx, member: discord.Member = None):

        member = member or ctx.author

        async with ctx.typing():
            buf = await build_profile_card(member)

        await ctx.send(file=discord.File(buf, filename="profile.png"))


async def setup(bot):
    await bot.add_cog(Profile(bot))
