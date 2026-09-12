from discord.ext import commands, tasks
import discord
import random
import asyncio
import aiohttp
import datetime
import io
import math

from PIL import Image, ImageDraw, ImageFont

from utils.pokemon_db import (
    db,
    get_balls,
    remove_ball,
    log_emiel_event,
)


# ─────────────────────────────────────────────────────────────────────
# URL HELPERS
# ─────────────────────────────────────────────────────────────────────

def _clean(name: str) -> str:
    return name.lower().replace(" ", "").replace(".", "").replace("'", "")

def gif_url(name: str) -> str:
    return f"https://play.pokemonshowdown.com/sprites/xyani/{_clean(name)}.gif"

def sprite_url(name: str) -> str:
    return f"https://play.pokemonshowdown.com/sprites/gen5/{_clean(name)}.png"

BALLS = {
    "pb": {
        "name": "Poké Ball",
        "db": "pokeball"
    },
    "ub": {
        "name": "Ultra Ball",
        "db": "ultraball"
    },
    "mb": {
        "name": "Master Ball",
        "db": "masterball"
    }
}

BALL_EMOJI = {
    "pb": "<:pb:1517998351227031632>",
    "ub": "<:ub:1517997681564324114>",
    "mb": "<a:mb:1517997721288704111>",
}

CATCH_RATES = {
    "pb": {
        "common": 35,
        "pseudo": 15,
        "ultra_beast": 15,
        "legendary": 7,
        "mythical": 3
    },

    "ub": {
        "common": 60,
        "pseudo": 30,
        "ultra_beast": 30,
        "legendary": 15,
        "mythical": 6
    },

    "mb": {
        "common": 100,
        "pseudo": 100,
        "ultra_beast": 100,
        "legendary": 100,
        "mythical": 100
    }
}

# ─────────────────────────────────────────────────────────────────────
# CATCH SUSPENSE / EMIEL CONSTANTS
# ─────────────────────────────────────────────────────────────────────

EMIEL_STEAL_CHANCE = 0.20  # 10% chance Emiel steals a successful catch

FAILURE_FLAVOR_TEXT = [
    "The Pokémon escaped!",
    "It broke free at the last second!",
    "That was close!",
    "The ball shattered open!",
    "So close!",
]
# ─────────────────────────────────────────────────────────────────────
# RARITY SYSTEM
# ─────────────────────────────────────────────────────────────────────

MYTHICAL_IDS: frozenset[int] = frozenset({
    151, 251, 385, 386, 489, 490, 491, 492, 493, 494,
    647, 648, 649, 719, 720, 721, 801, 802, 807, 808,
    809, 893,
})

LEGENDARY_IDS: frozenset[int] = frozenset({
    144, 145, 146, 150,
    243, 244, 245, 249, 250,
    377, 378, 379, 380, 381, 382, 383, 384,
    480, 481, 482, 483, 484, 485, 486, 487, 488,
    638, 639, 640, 641, 642, 643, 644, 645, 646,
    716, 717, 718,
    785, 786, 787, 788, 789, 790, 791, 792, 800,
    888, 889, 890, 891, 892, 894, 895, 896, 897, 898,
})

ULTRA_BEAST_IDS: frozenset[int] = frozenset({
    793, 794, 795, 796, 797, 798, 799, 803, 804, 805, 806,
})

PSEUDO_LEGENDARY_IDS: frozenset[int] = frozenset({
    149, 248, 373, 376, 445, 635, 706, 784, 887,
})


def get_rarity(pokedex_id: int) -> str:
    """Return a rarity tier string for the given Pokédex ID."""
    if pokedex_id in MYTHICAL_IDS:
        return "mythical"
    if pokedex_id in LEGENDARY_IDS:
        return "legendary"
    if pokedex_id in ULTRA_BEAST_IDS:
        return "ultra_beast"
    if pokedex_id in PSEUDO_LEGENDARY_IDS:
        return "pseudo"
    return "common"


# Ordering for sort-by-rarity (lower = rarer)
RARITY_ORDER: dict[str, int] = {
    "mythical":    0,
    "legendary":   1,
    "ultra_beast": 2,
    "pseudo":      3,
    "common":      4,
}

# Accent bar color per rarity (RGB)
RARITY_COLORS: dict[str, tuple] = {
    "mythical":    (255, 215,   0),   # gold
    "legendary":   (163,  73, 232),   # purple
    "ultra_beast": ( 32, 210, 210),   # teal / cyan
    "pseudo":      (232, 100,  32),   # warm orange
    "common":      ( 88, 101, 242),   # Discord blurple
}

# Short display labels used in the embed footer legend
RARITY_LABELS: dict[str, str] = {
    "mythical":    "✨ Mythical",
    "legendary":   "👑 Legendary",
    "ultra_beast": "🔮 Ultra Beast",
    "pseudo":      "🔥 Pseudo",
    "common":      "Common",
}

# Embed highlight colors for catch/spawn messages
RARITY_EMBED_COLORS: dict[str, int] = {
    "mythical":    0xFFD700,
    "legendary":   0xA349E8,
    "ultra_beast": 0x20D2D2,
    "pseudo":      0xE86420,
    "common":      0x57F287,
}

# Extra text injected into the spawn embed for rare encounters
RARITY_SPAWN_EXTRA: dict[str, str] = {
    "mythical":    "\n\n✨ **A MYTHICAL Pokémon has appeared — incredibly rare!** ✨",
    "legendary":   "\n\n👑 **A LEGENDARY Pokémon has appeared!** 👑",
    "ultra_beast": "\n\n🔮 **An ULTRA BEAST has appeared!** 🔮",
    "pseudo":      "\n\n🔥 **A powerful Pseudo-Legendary has appeared!** 🔥",
    "common":      "",
}


# ─────────────────────────────────────────────────────────────────────
# DEX IMAGE CONSTANTS
# ─────────────────────────────────────────────────────────────────────

COLS      = 3        # cards per row
CELL_W    = 112      # card width  (px)
CELL_H    = 162      # card height (px) — extra room for rarity label
PAD       = 14       # outer padding
GAP       = 10       # gap between cards
SPRITE_SZ = 84       # sprite bounding box

# Discord dark-mode palette
BG_COLOR   = (32,  34,  37)
CARD_COLOR = (47,  49,  54)
SHADOW_CLR = (22,  23,  25)
WHITE      = (255, 255, 255)
SUBTEXT    = (148, 155, 164)


# ─────────────────────────────────────────────────────────────────────
# FONT LOADER
# ─────────────────────────────────────────────────────────────────────

def _load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    suffix = "-Bold" if bold else ""
    candidates = [
        f"/usr/share/fonts/truetype/dejavu/DejaVuSans{suffix}.ttf",
        f"/usr/share/fonts/truetype/liberation/LiberationSans{suffix}.ttf",
        f"/usr/share/fonts/truetype/freefont/FreeSans{'Bold' if bold else ''}.ttf",
        f"C:/Windows/Fonts/{'arialbd' if bold else 'arial'}.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


# ─────────────────────────────────────────────────────────────────────
# DRAWING HELPERS
# ─────────────────────────────────────────────────────────────────────

def _draw_centered(draw, cx, y, text, font, fill):
    """Draw text horizontally centered at pixel x = cx."""
    bbox = draw.textbbox((0, 0), text, font=font)
    tw   = bbox[2] - bbox[0]
    draw.text((cx - tw // 2, y), text, fill=fill, font=font)


async def _fetch_sprite(session, name):
    """Download a gen-5 sprite; return an RGBA Image or None on failure."""
    try:
        async with session.get(
            sprite_url(name),
            timeout=aiohttp.ClientTimeout(total=6),
        ) as r:
            if r.status != 200:
                return None
            return Image.open(io.BytesIO(await r.read())).convert("RGBA")
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────
# BUILD THE GRID IMAGE
# ─────────────────────────────────────────────────────────────────────

async def build_dex_image(rows: list) -> io.BytesIO:
    """
    Render a sprite-grid dex card for up to 9 Pokémon.
    Accent bar color and rarity label are drawn per rarity tier.
    Returns a BytesIO PNG ready to attach to a Discord message.
    """
    n      = len(rows)
    n_cols = COLS
    n_rows = math.ceil(n / COLS)

    iw = PAD + n_cols * CELL_W + (n_cols - 1) * GAP + PAD
    ih = PAD + n_rows * CELL_H + (n_rows - 1) * GAP + PAD

    img  = Image.new("RGBA", (iw, ih), BG_COLOR)
    draw = ImageDraw.Draw(img)

    font_name   = _load_font(12, bold=True)
    font_id     = _load_font(11)
    font_unk    = _load_font(30, bold=True)
    font_rarity = _load_font(9)

    # Download all sprites concurrently
    async with aiohttp.ClientSession() as sess:
        sprites = await asyncio.gather(
            *[_fetch_sprite(sess, r["name"]) for r in rows]
        )

    for i, (row, spr) in enumerate(zip(rows, sprites)):
        col = i % COLS
        ri  = i // COLS
        x   = PAD + col * (CELL_W + GAP)
        y   = PAD + ri  * (CELL_H + GAP)

        rarity     = get_rarity(row["pokedex_id"])
        accent_clr = RARITY_COLORS[rarity]

        # Drop shadow
        draw.rounded_rectangle(
            [x + 3, y + 3, x + CELL_W + 3, y + CELL_H + 3],
            radius=12, fill=SHADOW_CLR,
        )
        # Card body
        draw.rounded_rectangle(
            [x, y, x + CELL_W, y + CELL_H],
            radius=12, fill=CARD_COLOR,
        )
        # Rarity-colored accent bar
        draw.rounded_rectangle(
            [x + 8, y + 5, x + CELL_W - 8, y + 9],
            radius=4, fill=accent_clr,
        )

        # Sprite
        sprite_top = y + 16
        if spr:
            spr.thumbnail((SPRITE_SZ, SPRITE_SZ), Image.LANCZOS)
            sw, sh = spr.size
            sx = x + (CELL_W - sw) // 2
            sy = sprite_top + (SPRITE_SZ - sh) // 2
            img.paste(spr, (sx, sy), spr)
        else:
            _draw_centered(
                draw,
                x + CELL_W // 2,
                sprite_top + SPRITE_SZ // 2 - 18,
                "?", font_unk, SUBTEXT,
            )

        # Name + Dex number + rarity label
        ty = sprite_top + SPRITE_SZ + 7
        cx = x + CELL_W // 2

        label = row["display"]
        if len(label) > 13:
            label = label[:12] + "\u2026"

        _draw_centered(draw, cx, ty,      label,                       font_name,   WHITE)
        _draw_centered(draw, cx, ty + 17, f"#{row['pokedex_id']:03}",  font_id,     SUBTEXT)

        # Rarity label — drawn in accent color for non-common Pokémon
        if rarity != "common":
            _draw_centered(
                draw, cx, ty + 31,
                RARITY_LABELS[rarity],
                font_rarity, accent_clr,
            )

    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return buf


# ─────────────────────────────────────────────────────────────────────
# SORT HELPERS
# ─────────────────────────────────────────────────────────────────────

def sort_rows(rows: list, mode: str) -> list:
    """Return a new sorted list of Pokémon rows for the given sort mode."""
    if mode == "rarity":
        return sorted(
            rows,
            key=lambda r: (RARITY_ORDER[get_rarity(r["pokedex_id"])], r["pokedex_id"]),
        )
    # "dex" (default)
    return sorted(rows, key=lambda r: r["pokedex_id"])


# ─────────────────────────────────────────────────────────────────────
# PAGINATED DEX VIEW
# ─────────────────────────────────────────────────────────────────────

_SORT_DEFS = [
    ("dex",    "🔢 Dex #"),
    ("rarity", "⭐ Rarity"),
]

_SORT_DISPLAY = {k: v for k, v in _SORT_DEFS}


class DexView(discord.ui.View):

    def __init__(self, rows: list, target: discord.Member):
        super().__init__(timeout=120)
        self._all_rows = rows        # original order (by date, from DB)
        self.target    = target
        self.sort_mode = "dex"
        self.page      = 0
        self.msg       = None
        self._apply_sort()
        self._rebuild_buttons()

    # ── internal helpers ─────────────────────────────────────────────

    def _apply_sort(self):
        self.rows  = sort_rows(self._all_rows, self.sort_mode)
        self.pages = [self.rows[i : i + 9] for i in range(0, len(self.rows), 9)]
        self.page  = min(self.page, max(0, len(self.pages) - 1))

    def _rebuild_buttons(self):
        """Recreate all buttons, reflecting current page and sort state."""
        self.clear_items()

        # ── Row 0: navigation ────────────────────────────────────────
        prev = discord.ui.Button(
            emoji="⬅️",
            style=discord.ButtonStyle.secondary,
            row=0,
            disabled=(self.page == 0),
        )
        prev.callback = self._cb_prev
        self.add_item(prev)

        counter = discord.ui.Button(
            label=f"{self.page + 1} / {len(self.pages)}",
            style=discord.ButtonStyle.primary,
            row=0,
            disabled=True,
        )
        counter.callback = self._cb_noop
        self.add_item(counter)

        nxt = discord.ui.Button(
            emoji="➡️",
            style=discord.ButtonStyle.secondary,
            row=0,
            disabled=(self.page >= len(self.pages) - 1),
        )
        nxt.callback = self._cb_next
        self.add_item(nxt)

        # ── Row 1: sort buttons ──────────────────────────────────────
        for mode, label in _SORT_DEFS:
            btn = discord.ui.Button(
                label=label,
                style=(
                    discord.ButtonStyle.success       # highlighted when active
                    if mode == self.sort_mode
                    else discord.ButtonStyle.secondary
                ),
                row=1,
            )
            btn.callback = self._make_sort_cb(mode)
            self.add_item(btn)

    # ── callbacks ────────────────────────────────────────────────────

    async def _cb_noop(self, interaction: discord.Interaction):
        await interaction.response.defer()

    async def _cb_prev(self, interaction: discord.Interaction):
        self.page = max(0, self.page - 1)
        await self._refresh(interaction)

    async def _cb_next(self, interaction: discord.Interaction):
        self.page = min(len(self.pages) - 1, self.page + 1)
        await self._refresh(interaction)

    def _make_sort_cb(self, mode: str):
        async def _cb(interaction: discord.Interaction):
            if self.sort_mode == mode:
                await interaction.response.defer()
                return
            self.sort_mode = mode
            self.page      = 0
            self._apply_sort()
            await self._refresh(interaction)
        return _cb

    async def _refresh(self, interaction: discord.Interaction):
        self._rebuild_buttons()
        embed, file = await self.build()
        await interaction.response.edit_message(embed=embed, attachments=[file], view=self)

    # ── embed / image builder ────────────────────────────────────────

    async def build(self):
        """Return (embed, file) for the current page."""
        buf  = await build_dex_image(self.pages[self.page])
        file = discord.File(buf, filename="dex.png")

        # Tally rare catches for the embed field
        rarity_counts: dict[str, int] = {}
        for r in self._all_rows:
            tier = get_rarity(r["pokedex_id"])
            rarity_counts[tier] = rarity_counts.get(tier, 0) + 1

        legend_parts = []
        for tier in ("mythical", "legendary", "ultra_beast", "pseudo"):
            count = rarity_counts.get(tier, 0)
            if count:
                legend_parts.append(f"{RARITY_LABELS[tier]} ×{count}")

        embed = discord.Embed(
            title=f"📖  {self.target.display_name}'s Pokédex",
            color=0x5865F2,
        )
        embed.set_author(
            name     = f"{len(self._all_rows)} Pokémon in collection",
            icon_url = self.target.display_avatar.url,
        )
        if legend_parts:
            embed.add_field(
                name   = "✨ Rare catches",
                value  = "  ·  ".join(legend_parts),
                inline = False,
            )

        embed.set_image(url="attachment://dex.png")
        embed.set_footer(
            text=(
                f"Page {self.page + 1} of {len(self.pages)}  |  "
                f"Sorted by {_SORT_DISPLAY[self.sort_mode]}  |  "
                ".pokemon sell <name> <price> to trade"
            )
        )
        return embed, file

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.msg:
            try:
                await self.msg.edit(view=self)
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────────────
# SPAWN HELPERS
# ─────────────────────────────────────────────────────────────────────

TOTAL_POKEMON = 898
active_spawns: dict = {}

# ─────────────────────────────────────────────────────────────────────
# SPAWN WEIGHTING
# ─────────────────────────────────────────────────────────────────────
# Previously every one of the 898 species had the exact same 1/898 chance
# of spawning — a Rattata and Mewtwo were equally likely. That meant
# mythicals/legendaries kept showing up constantly instead of being rare.
#
# Now a tier is picked first (weighted), then a species is picked
# uniformly within that tier. Numbers below are the % chance a spawn
# comes from that tier overall — spread across however many species
# are in it, so individually rarer tiers work out to a much smaller
# per-species chance too.
SPAWN_TIER_WEIGHTS: dict[str, float] = {
    "common":      85.0,
    "pseudo":       6.0,
    "ultra_beast":  4.0,
    "legendary":    3.5,
    "mythical":     1.5,
}

COMMON_IDS: tuple[int, ...] = tuple(
    pid for pid in range(1, TOTAL_POKEMON + 1)
    if pid not in MYTHICAL_IDS
    and pid not in LEGENDARY_IDS
    and pid not in ULTRA_BEAST_IDS
    and pid not in PSEUDO_LEGENDARY_IDS
)

SPAWN_TIER_POOLS: dict[str, tuple[int, ...]] = {
    "common":      COMMON_IDS,
    "pseudo":      tuple(PSEUDO_LEGENDARY_IDS),
    "ultra_beast": tuple(ULTRA_BEAST_IDS),
    "legendary":   tuple(LEGENDARY_IDS),
    "mythical":    tuple(MYTHICAL_IDS),
}

_SPAWN_TIERS = list(SPAWN_TIER_WEIGHTS.keys())
_SPAWN_WEIGHTS = list(SPAWN_TIER_WEIGHTS.values())


def _roll_pokedex_id() -> int:
    """Pick a rarity tier by weight, then a species uniformly within it."""
    tier = random.choices(_SPAWN_TIERS, weights=_SPAWN_WEIGHTS, k=1)[0]
    return random.choice(SPAWN_TIER_POOLS[tier])


async def fetch_random_pokemon():
    pid = _roll_pokedex_id()
    async with aiohttp.ClientSession() as s:
        async with s.get(f"https://pokeapi.co/api/v2/pokemon/{pid}") as r:
            if r.status != 200:
                return None
            data = await r.json()
    return {"id": pid, "name": data["name"], "display": data["name"].title()}


# ─────────────────────────────────────────────────────────────────────
# COG
# ─────────────────────────────────────────────────────────────────────

class PokemonSpawn(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.spawn_loop.start()

    def cog_unload(self):
        self.spawn_loop.cancel()

    @tasks.loop(minutes=5)
    async def spawn_loop(self):
        if db is None:
            return
        for doc in db.pokemon_spawn_channels.find():
            ch = self.bot.get_channel(int(doc["channel_id"]))
            if ch:
                await self.do_spawn(ch)

    @spawn_loop.before_loop
    async def before_spawn(self):
        await self.bot.wait_until_ready()

    async def do_spawn(self, channel: discord.TextChannel):
        poke = await fetch_random_pokemon()
        if not poke:
            return

        rarity = get_rarity(poke["id"])
        active_spawns[str(channel.id)] = {**poke, "caught": False}

        embed = discord.Embed(
            title="A wild Pokémon appeared! 🌿",
            description=(
                "**Who's that Pokémon?** 🤔\n\n"
                "Type `.catch pb/ub/mb <pokemon name>` to catch it!\n"
                "First trainer to guess correctly wins!\n\n"
                "⚠️ You can only catch each species **once**!"
                + RARITY_SPAWN_EXTRA[rarity]
            ),
            color=RARITY_EMBED_COLORS[rarity],
        )
        embed.set_image(url=gif_url(poke["name"]))
        embed.set_footer(text="Be fast! Only one trainer can catch it.")
        await channel.send(embed=embed)

    @commands.command(name="catch")
    async def catch(self, ctx, ball_type=None, *, guess=None):

        cid = str(ctx.channel.id)
        spawn = active_spawns.get(cid)

        if ball_type is None or guess is None:
            embed = discord.Embed(
                title="Invalid Catch Format",
                description=(
                    "To catch Pokémon, you must use a ball.\n\n"
                    "Examples:\n"
                    "`.catch pb pikachu`\n"
                    "`.catch ub rayquaza`\n"
                    "`.catch mb mew`\n\n"
                    "<:pb:1517998351227031632> pb = Poké Ball\n"
                    "<:ub:1517997681564324114> ub = Ultra Ball\n"
                    "<a:mb:1517997721288704111> mb = Master Ball\n\n"
                    "Buy balls from the shop first!"
                ),
                color=0xED4245
            )

            await ctx.send(embed=embed)
            return

        ball_type = ball_type.lower()

        if ball_type not in BALLS:
            await ctx.send(
                "❌ Valid balls are: `pb`, `ub`, `mb`"
            )
            return

        balls = get_balls(ctx.author.id)

        ball_db_name = BALLS[ball_type]["db"]
        ball_name = BALLS[ball_type]["name"]
        ball_emoji = BALL_EMOJI[ball_type]

        if balls.get(ball_db_name, 0) <= 0:
            await ctx.send(embed=discord.Embed(
                title="No Balls Available!",
                description=(
                    f"You don't have any **{ball_name}s**.\n\n"
                    "Buy some from the shop first.\n\n"
                    "<:pb:1517998351227031632> Poké Ball - 10,000\n"
                    "<:ub:1517997681564324114> Ultra Ball - 75,000\n"
                    "<a:mb:1517997721288704111> Master Ball - 750,000"
                ),
                color=0xED4245
            ))
            return

        if spawn is None or spawn["caught"]:
            await ctx.send(embed=discord.Embed(
                description="There's no wild Pokémon here right now!",
                color=0xED4245,
            ))
            return

        if guess.strip().lower() != spawn["name"].lower():
            await ctx.send(embed=discord.Embed(
                description=f"❌ That's not right, **{ctx.author.display_name}**! Keep trying!",
                color=0xED4245,
            ), delete_after=4)
            return

        uid = str(ctx.author.id)

        already = db.pokemon_collection.find_one(
            {"user_id": uid, "name": spawn["name"]}
        )

        if already:
            await ctx.send(embed=discord.Embed(
                title="Already caught! 🚫",
                description=(
                    f"**{ctx.author.display_name}**, you already own a **{spawn['display']}**!\n"
                    "Each trainer can only catch one of each species.\n\n"
                    "Let someone else catch it! 🎯"
                ),
                color=0xFFA500,
            ), delete_after=8)
            return

        # Lock the spawn immediately so nobody else can race this attempt.
        spawn["caught"] = True

        rarity = get_rarity(spawn["id"])
        catch_rate = CATCH_RATES[ball_type][rarity]

        # ─────────────────────────────────────────────
        # SUSPENSE ANIMATION
        # ─────────────────────────────────────────────

        suspense_embed = discord.Embed(
            description=f"{ball_emoji} **{ctx.author.display_name}** threw a **{ball_name}**!",
            color=0x5865F2,
        )
        msg = await ctx.send(embed=suspense_embed)

        shake_line = ""
        for _ in range(3):
            await asyncio.sleep(1)
            shake_line += "✨ Shake...\n"
            shake_embed = discord.Embed(
                description=(
                    f"{ball_emoji} **{ctx.author.display_name}** threw a **{ball_name}**!\n\n"
                    f"{shake_line}"
                ),
                color=0x5865F2,
            )
            try:
                await msg.edit(embed=shake_embed)
            except discord.HTTPException:
                pass

        await asyncio.sleep(1)

        # ─────────────────────────────────────────────
        # CATCH ROLL — balls are ALWAYS consumed
        # ─────────────────────────────────────────────

        remove_ball(ctx.author.id, ball_db_name, 1)

        success = (ball_type == "mb") or (random.uniform(0, 100) < catch_rate)

        if not success:
            fail_text = random.choice(FAILURE_FLAVOR_TEXT)

            fail_embed = discord.Embed(
                title="💨 Oh no!",
                description=(
                    f"**{spawn['display']}** broke free!\n"
                    f"*{fail_text}*\n\n"
                    f"Your **{ball_name}** was lost."
                ),
                color=0xED4245,
            )
            fail_embed.set_footer(
                text=f"Catch chance was {catch_rate}% with {ball_name}"
            )

            try:
                await msg.edit(embed=fail_embed)
            except discord.HTTPException:
                await ctx.send(embed=fail_embed)
            return

        # ─────────────────────────────────────────────
        # SUCCESS — roll for Emiel theft
        # ─────────────────────────────────────────────

        stolen = random.random() < EMIEL_STEAL_CHANCE

        if stolen:
            log_emiel_event(
                "steal",
                user_id=uid,
                pokemon_display=spawn["display"],
                rarity=rarity,
            )

            steal_embed = discord.Embed(
                title="<:emoji_11:1515736255097471006> EMIEL APPEARED!",
                description=(
                    f"Emiel raped your **{spawn['display']}** "
                    "and disappeared into the shadows!\n\n"
                    f"*Your {ball_name} is gone, and so is the Pokémon...*"
                ),
                color=0x2B2D31,
            )
            steal_embed.set_thumbnail(url=gif_url(spawn["name"]))
            steal_embed.set_footer(
                text="Better luck next time — check .emiel for the global feed"
            )

            try:
                await msg.edit(embed=steal_embed)
            except discord.HTTPException:
                await ctx.send(embed=steal_embed)
            return

        db.pokemon_collection.insert_one({
            "user_id": uid,
            "name": spawn["name"],
            "display": spawn["display"],
            "pokedex_id": spawn["id"],
            "moves": [],
            "caught_at": datetime.datetime.utcnow(),
        })

        catch_embed = discord.Embed(
            title=f"🎉 GOTCHA!",
            description=(
                f"**{spawn['display']}** was caught!\n"
                f"*{RARITY_LABELS[rarity]}*\n\n"
                f"Use `.team` to add it, `.moves` to teach it moves!\n"
                f"Want to sell? Use `.emiel sell {spawn['display']}`"
            ),
            color=RARITY_EMBED_COLORS[rarity],
        )

        catch_embed.set_image(url=gif_url(spawn["name"]))
        catch_embed.set_footer(
            text=f"Pokédex #{spawn['id']} · {RARITY_LABELS[rarity]}"
        )

        try:
            await msg.edit(embed=catch_embed)
        except discord.HTTPException:
            await ctx.send(embed=catch_embed)

    @commands.command(name="pokemons", aliases=["pc", "collection"])
    async def pokemon_collection(self, ctx, member: discord.Member = None):
        target = member or ctx.author
        rows   = list(
            db.pokemon_collection
            .find({"user_id": str(target.id)})
            .sort("caught_at", -1)
        )

        if not rows:
            await ctx.send(embed=discord.Embed(
                title="📖  Empty Pokédex",
                description=(
                    f"**{target.display_name}** hasn't caught any Pokémon yet!\n\n"
                    "Pokémon spawn every 10 minutes — type `.catch <name>` when one appears!"
                ),
                color=0xED4245,
            ))
            return

        view        = DexView(rows, target)
        embed, file = await view.build()
        msg         = await ctx.send(embed=embed, file=file, view=view)
        view.msg    = msg

    @commands.command(name="setspawnchannel")
    @commands.has_permissions(manage_guild=True)
    async def set_spawn_channel(self, ctx):
        db.pokemon_spawn_channels.update_one(
            {"channel_id": str(ctx.channel.id)},
            {"$set": {"guild_id": str(ctx.guild.id)}},
            upsert=True,
        )
        await ctx.send(embed=discord.Embed(
            description=f"✅ Pokémon will now spawn in {ctx.channel.mention} every 10 minutes!",
            color=0x57F287,
        ))


async def setup(bot):
    await bot.add_cog(PokemonSpawn(bot))
