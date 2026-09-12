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
    get_character_name,
)


def _clean(name: str) -> str:
    return name.lower().replace(" ", "").replace(".", "").replace("'", "")


def gif_url(name: str) -> str:
    return f"https://play.pokemonshowdown.com/sprites/xyani/{_clean(name)}.gif"


def sprite_url(name: str) -> str:
    return f"https://play.pokemonshowdown.com/sprites/gen5/{_clean(name)}.png"


BALLS = {
    "pb": {"name": "Poké Ball", "db": "pokeball"},
    "ub": {"name": "Ultra Ball", "db": "ultraball"},
    "mb": {"name": "Master Ball", "db": "masterball"},
}
BALL_EMOJI = {
    "pb": "<:pb:1517998351227031632>",
    "ub": "<:ub:1517997681564324114>",
    "mb": "<a:mb:1517997721288704111>",
}
CATCH_RATES = {
    "pb": {"common": 35, "pseudo": 15, "ultra_beast": 15, "legendary": 7, "mythical": 3},
    "ub": {"common": 60, "pseudo": 30, "ultra_beast": 30, "legendary": 15, "mythical": 6},
    "mb": {"common": 100, "pseudo": 100, "ultra_beast": 100, "legendary": 100, "mythical": 100},
}
EMIEL_STEAL_CHANCE = 0.20
FAILURE_FLAVOR_TEXT = [
    "The Pokémon escaped!", "It broke free at the last second!", "That was close!",
    "The ball shattered open!", "So close!",
]

MYTHICAL_IDS = frozenset({151,251,385,386,489,490,491,492,493,494,647,648,649,719,720,721,801,802,807,808,809,893})
LEGENDARY_IDS = frozenset({144,145,146,150,243,244,245,249,250,377,378,379,380,381,382,383,384,480,481,482,483,484,485,486,487,488,638,639,640,641,642,643,644,645,646,716,717,718,785,786,787,788,789,790,791,792,800,888,889,890,891,892,894,895,896,897,898})
ULTRA_BEAST_IDS = frozenset({793,794,795,796,797,798,799,803,804,805,806})
PSEUDO_LEGENDARY_IDS = frozenset({149,248,373,376,445,635,706,784,887})


def get_rarity(pokedex_id: int) -> str:
    if pokedex_id in MYTHICAL_IDS: return "mythical"
    if pokedex_id in LEGENDARY_IDS: return "legendary"
    if pokedex_id in ULTRA_BEAST_IDS: return "ultra_beast"
    if pokedex_id in PSEUDO_LEGENDARY_IDS: return "pseudo"
    return "common"


RARITY_ORDER = {"mythical": 0, "legendary": 1, "ultra_beast": 2, "pseudo": 3, "common": 4}
RARITY_COLORS = {
    "mythical": (255,215,0), "legendary": (163,73,232), "ultra_beast": (32,210,210),
    "pseudo": (232,100,32), "common": (88,101,242),
}
RARITY_LABELS = {
    "mythical": "✨ Mythical", "legendary": "👑 Legendary", "ultra_beast": "🔮 Ultra Beast",
    "pseudo": "🔥 Pseudo", "common": "Common",
}
RARITY_EMBED_COLORS = {
    "mythical": 0xFFD700, "legendary": 0xA349E8, "ultra_beast": 0x20D2D2,
    "pseudo": 0xE86420, "common": 0x57F287,
}
RARITY_SPAWN_EXTRA = {
    "mythical": "\n\n✨ **A MYTHICAL Pokémon has appeared — incredibly rare!** ✨",
    "legendary": "\n\n👑 **A LEGENDARY Pokémon has appeared!** 👑",
    "ultra_beast": "\n\n🔮 **An ULTRA BEAST has appeared!** 🔮",
    "pseudo": "\n\n🔥 **A powerful Pseudo-Legendary has appeared!** 🔥",
    "common": "",
}
SPAWN_TIER_WEIGHTS = {"common": 85.0, "pseudo": 6.0, "ultra_beast": 4.0, "legendary": 3.5, "mythical": 1.5}

TOTAL_POKEMON = 898
COMMON_IDS = tuple(pid for pid in range(1, TOTAL_POKEMON + 1) if pid not in MYTHICAL_IDS and pid not in LEGENDARY_IDS and pid not in ULTRA_BEAST_IDS and pid not in PSEUDO_LEGENDARY_IDS)
SPAWN_TIER_POOLS = {
    "common": COMMON_IDS, "pseudo": tuple(PSEUDO_LEGENDARY_IDS), "ultra_beast": tuple(ULTRA_BEAST_IDS),
    "legendary": tuple(LEGENDARY_IDS), "mythical": tuple(MYTHICAL_IDS),
}


def _roll_pokedex_id() -> int:
    tier = random.choices(list(SPAWN_TIER_WEIGHTS), weights=list(SPAWN_TIER_WEIGHTS.values()), k=1)[0]
    return random.choice(SPAWN_TIER_POOLS[tier])


async def fetch_random_pokemon():
    pid = _roll_pokedex_id()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://pokeapi.co/api/v2/pokemon/{pid}", timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status != 200: return None
                data = await response.json()
        return {"id": pid, "name": data["name"], "display": data["name"].title()}
    except Exception:
        return None


# ── Pokédex image view ───────────────────────────────────────────────
COLS, CELL_W, CELL_H, PAD, GAP, SPRITE_SZ = 3, 112, 162, 14, 10, 84
BG_COLOR, CARD_COLOR, SHADOW_CLR = (32,34,37), (47,49,54), (22,23,25)
WHITE, SUBTEXT = (255,255,255), (148,155,164)


def _load_font(size: int, bold: bool = False):
    suffix = "-Bold" if bold else ""
    candidates = [
        f"/usr/share/fonts/truetype/dejavu/DejaVuSans{suffix}.ttf",
        f"/usr/share/fonts/truetype/liberation/LiberationSans{suffix}.ttf",
        f"/usr/share/fonts/truetype/freefont/FreeSans{'Bold' if bold else ''}.ttf",
        f"C:/Windows/Fonts/{'arialbd' if bold else 'arial'}.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for path in candidates:
        try: return ImageFont.truetype(path, size)
        except Exception: pass
    return ImageFont.load_default()


def _draw_centered(draw, cx, y, text, font, fill):
    bbox = draw.textbbox((0,0), text, font=font)
    draw.text((cx - (bbox[2]-bbox[0]) // 2, y), text, fill=fill, font=font)


async def _fetch_sprite(session, name):
    try:
        async with session.get(sprite_url(name), timeout=aiohttp.ClientTimeout(total=6)) as r:
            if r.status != 200: return None
            return Image.open(io.BytesIO(await r.read())).convert("RGBA")
    except Exception:
        return None


async def build_dex_image(rows):
    n_rows = math.ceil(len(rows) / COLS)
    iw = PAD + COLS * CELL_W + (COLS - 1) * GAP + PAD
    ih = PAD + n_rows * CELL_H + (n_rows - 1) * GAP + PAD
    img = Image.new("RGBA", (iw, ih), BG_COLOR)
    draw = ImageDraw.Draw(img)
    font_name, font_id = _load_font(12, True), _load_font(11)
    font_unk, font_rarity = _load_font(30, True), _load_font(9)
    async with aiohttp.ClientSession() as sess:
        sprites = await asyncio.gather(*[_fetch_sprite(sess, r["name"]) for r in rows])
    for i, (row, spr) in enumerate(zip(rows, sprites)):
        col, ri = i % COLS, i // COLS
        x, y = PAD + col * (CELL_W + GAP), PAD + ri * (CELL_H + GAP)
        rarity, accent = get_rarity(row["pokedex_id"]), RARITY_COLORS[get_rarity(row["pokedex_id"])]
        draw.rounded_rectangle([x+3,y+3,x+CELL_W+3,y+CELL_H+3], radius=12, fill=SHADOW_CLR)
        draw.rounded_rectangle([x,y,x+CELL_W,y+CELL_H], radius=12, fill=CARD_COLOR)
        draw.rounded_rectangle([x+8,y+5,x+CELL_W-8,y+9], radius=4, fill=accent)
        sprite_top = y + 16
        if spr:
            spr.thumbnail((SPRITE_SZ, SPRITE_SZ), Image.LANCZOS)
            sw, sh = spr.size
            img.paste(spr, (x+(CELL_W-sw)//2, sprite_top+(SPRITE_SZ-sh)//2), spr)
        else:
            _draw_centered(draw, x+CELL_W//2, sprite_top+SPRITE_SZ//2-18, "?", font_unk, SUBTEXT)
        ty, cx = sprite_top + SPRITE_SZ + 7, x + CELL_W//2
        label = row["display"] if len(row["display"]) <= 13 else row["display"][:12] + "…"
        _draw_centered(draw, cx, ty, label, font_name, WHITE)
        _draw_centered(draw, cx, ty+17, f"#{row['pokedex_id']:03}", font_id, SUBTEXT)
        if rarity != "common": _draw_centered(draw, cx, ty+31, RARITY_LABELS[rarity], font_rarity, accent)
    buf = io.BytesIO(); img.save(buf, "PNG"); buf.seek(0)
    return buf


def sort_rows(rows, mode):
    if mode == "rarity": return sorted(rows, key=lambda r: (RARITY_ORDER[get_rarity(r["pokedex_id"])], r["pokedex_id"]))
    return sorted(rows, key=lambda r: r["pokedex_id"])


_SORT_DEFS = [("dex", "🔢 Dex #"), ("rarity", "⭐ Rarity")]
_SORT_DISPLAY = dict(_SORT_DEFS)


class DexView(discord.ui.View):
    def __init__(self, rows, target):
        super().__init__(timeout=120)
        self._all_rows, self.target, self.sort_mode, self.page, self.msg = rows, target, "dex", 0, None
        self._apply_sort(); self._rebuild_buttons()

    def _apply_sort(self):
        self.rows = sort_rows(self._all_rows, self.sort_mode)
        self.pages = [self.rows[i:i+9] for i in range(0, len(self.rows), 9)]
        self.page = min(self.page, max(0, len(self.pages)-1))

    def _rebuild_buttons(self):
        self.clear_items()
        prev = discord.ui.Button(emoji="⬅️", style=discord.ButtonStyle.secondary, row=0, disabled=self.page == 0)
        prev.callback = self._cb_prev; self.add_item(prev)
        counter = discord.ui.Button(label=f"{self.page+1} / {len(self.pages)}", style=discord.ButtonStyle.primary, row=0, disabled=True)
        counter.callback = self._cb_noop; self.add_item(counter)
        nxt = discord.ui.Button(emoji="➡️", style=discord.ButtonStyle.secondary, row=0, disabled=self.page >= len(self.pages)-1)
        nxt.callback = self._cb_next; self.add_item(nxt)
        for mode, label in _SORT_DEFS:
            btn = discord.ui.Button(label=label, style=discord.ButtonStyle.success if mode == self.sort_mode else discord.ButtonStyle.secondary, row=1)
            btn.callback = self._make_sort_cb(mode); self.add_item(btn)

    async def _cb_noop(self, interaction): await interaction.response.defer()
    async def _cb_prev(self, interaction): self.page = max(0, self.page-1); await self._refresh(interaction)
    async def _cb_next(self, interaction): self.page = min(len(self.pages)-1, self.page+1); await self._refresh(interaction)

    def _make_sort_cb(self, mode):
        async def _cb(interaction):
            if self.sort_mode == mode: await interaction.response.defer(); return
            self.sort_mode, self.page = mode, 0; self._apply_sort(); await self._refresh(interaction)
        return _cb

    async def _refresh(self, interaction):
        self._rebuild_buttons(); embed, file = await self.build()
        await interaction.response.edit_message(embed=embed, attachments=[file], view=self)

    async def build(self):
        buf = await build_dex_image(self.pages[self.page]); file = discord.File(buf, filename="dex.png")
        counts = {}
        for r in self._all_rows:
            tier = get_rarity(r["pokedex_id"]); counts[tier] = counts.get(tier, 0) + 1
        legend = [f"{RARITY_LABELS[t]} ×{counts[t]}" for t in ("mythical","legendary","ultra_beast","pseudo") if counts.get(t)]
        embed = discord.Embed(title=f"📖  {self.target.display_name}'s Pokédex", color=0x5865F2)
        embed.set_author(name=f"{len(self._all_rows)} Pokémon in collection", icon_url=self.target.display_avatar.url)
        if legend: embed.add_field(name="✨ Rare catches", value="  ·  ".join(legend), inline=False)
        embed.set_image(url="attachment://dex.png")
        embed.set_footer(text=f"Page {self.page+1} of {len(self.pages)}  |  Sorted by {_SORT_DISPLAY[self.sort_mode]}  |  .pokemon sell <name> <price> to trade")
        return embed, file

    async def on_timeout(self):
        for child in self.children: child.disabled = True
        if self.msg:
            try: await self.msg.edit(view=self)
            except Exception: pass


active_spawns = {}


class PokemonSpawn(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.spawn_loop.start()

    def cog_unload(self): self.spawn_loop.cancel()

    @tasks.loop(minutes=1)
    async def spawn_loop(self):
        if db is None: return
        for doc in db.pokemon_spawn_channels.find():
            try: channel = self.bot.get_channel(int(doc["channel_id"]))
            except (KeyError, ValueError, TypeError): continue
            if channel: await self.do_spawn(channel)

    @spawn_loop.before_loop
    async def before_spawn(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(60)

    async def do_spawn(self, channel):
        poke = await fetch_random_pokemon()
        if not poke: return
        rarity = get_rarity(poke["id"])
        active_spawns[str(channel.id)] = {**poke, "caught": False}
        embed = discord.Embed(
            title="A wild Pokémon appeared! 🌿",
            description=("**Who's that Pokémon?** 🤔\n\n"
                         "Type `.catch pb/ub/mb <pokemon name>` to catch it!\n"
                         "First trainer to guess correctly wins!\n\n"
                         "⚠️ You can only catch each species **once!**" + RARITY_SPAWN_EXTRA[rarity]),
            color=RARITY_EMBED_COLORS[rarity],
        )
        embed.set_image(url=gif_url(poke["name"]))
        embed.set_footer(text="Be fast! Only one trainer can catch it.")
        await channel.send(embed=embed)

    @commands.command(name="forcespawn", aliases=["spawntest"])
    @commands.has_permissions(manage_guild=True)
    async def force_spawn(self, ctx):
        await self.do_spawn(ctx.channel)

    @commands.command(name="catch")
    async def catch(self, ctx, ball_type=None, *, guess=None):
        cid, spawn = str(ctx.channel.id), active_spawns.get(str(ctx.channel.id))
        if ball_type is None or guess is None:
            await ctx.send(embed=discord.Embed(title="Invalid Catch Format", description=(
                "To catch Pokémon, you must use a ball.\n\nExamples:\n"
                "`.catch pb pikachu`\n`.catch ub rayquaza`\n`.catch mb mew`\n\n"
                "<:pb:1517998351227031632> pb = Poké Ball\n<:ub:1517997681564324114> ub = Ultra Ball\n"
                "<a:mb:1517997721288704111> mb = Master Ball\n\nBuy balls from the shop first!"), color=0xED4245)); return
        ball_type = ball_type.lower()
        if ball_type not in BALLS: await ctx.send("❌ Valid balls are: `pb`, `ub`, `mb`"); return
        balls = get_balls(ctx.author.id); ball_db_name = BALLS[ball_type]["db"]
        ball_name, ball_emoji = BALLS[ball_type]["name"], BALL_EMOJI[ball_type]
        if balls.get(ball_db_name, 0) <= 0:
            await ctx.send(embed=discord.Embed(title="No Balls Available!", description=(
                f"You don't have any **{ball_name}s**.\n\nBuy some from the shop first.\n\n"
                "<:pb:1517998351227031632> Poké Ball - 10,000\n<:ub:1517997681564324114> Ultra Ball - 25,000\n"
                "<a:mb:1517997721288704111> Master Ball - 50,000"), color=0xED4245)); return
        if spawn is None or spawn["caught"]:
            await ctx.send(embed=discord.Embed(description="There's no wild Pokémon here right now!", color=0xED4245)); return
        if guess.strip().lower() != spawn["name"].lower():
            await ctx.send(embed=discord.Embed(description=f"❌ That's not right, **{ctx.author.display_name}**! Keep trying!", color=0xED4245), delete_after=4); return
        uid = str(ctx.author.id)
        if db.pokemon_collection.find_one({"user_id": uid, "name": spawn["name"]}):
            await ctx.send(embed=discord.Embed(title="Already caught! 🚫", description=(
                f"**{ctx.author.display_name}**, you already own a **{spawn['display']}**!\nEach trainer can only catch one of each species.\n\nLet someone else catch it! 🎯"), color=0xFFA500), delete_after=8); return
        spawn["caught"] = True
        rarity, catch_rate = get_rarity(spawn["id"]), CATCH_RATES[ball_type][get_rarity(spawn["id"])]
        msg = await ctx.send(embed=discord.Embed(description=f"{ball_emoji} **{ctx.author.display_name}** threw a **{ball_name}**!", color=0x5865F2))
        shake = ""
        for _ in range(3):
            await asyncio.sleep(1); shake += "✨ Shake...\n"
            try: await msg.edit(embed=discord.Embed(description=f"{ball_emoji} **{ctx.author.display_name}** threw a **{ball_name}**!\n\n{shake}", color=0x5865F2))
            except discord.HTTPException: pass
        await asyncio.sleep(1); remove_ball(ctx.author.id, ball_db_name, 1)
        if not (ball_type == "mb" or random.uniform(0,100) < catch_rate):
            fail = discord.Embed(title="💨 Oh no!", description=(f"**{spawn['display']}** broke free!\n*{random.choice(FAILURE_FLAVOR_TEXT)}*\n\nYour **{ball_name}** was lost."), color=0xED4245)
            fail.set_footer(text=f"Catch chance was {catch_rate}% with {ball_name}")
            try: await msg.edit(embed=fail)
            except discord.HTTPException: await ctx.send(embed=fail)
            return
        if random.random() < EMIEL_STEAL_CHANCE:
            log_emiel_event("steal", user_id=uid, pokemon_display=spawn["display"], rarity=rarity)
            character_name = get_character_name(ctx.guild.id)
            steal = discord.Embed(title=f"<:emoji_11:1515736255097471006> {character_name.upper()} APPEARED!", description=(
                f"{character_name} snatched your **{spawn['display']}** and disappeared into the shadows!\n\n*Your {ball_name} is gone, and so is the Pokémon...*"), color=0x2B2D31)
            steal.set_thumbnail(url=gif_url(spawn["name"])); steal.set_footer(text="Better luck next time — check .diddy for the global feed")
            try: await msg.edit(embed=steal)
            except discord.HTTPException: await ctx.send(embed=steal)
            return
        db.pokemon_collection.insert_one({"user_id": uid, "name": spawn["name"], "display": spawn["display"], "pokedex_id": spawn["id"], "moves": [], "caught_at": datetime.datetime.utcnow()})
        caught = discord.Embed(title="🎉 GOTCHA!", description=(f"**{spawn['display']}** was caught!\n*{RARITY_LABELS[rarity]}*\n\nUse `.team` to add it, `.moves` to teach it moves!\nWant to sell? Use `.diddy sell {spawn['display']}"), color=RARITY_EMBED_COLORS[rarity])
        caught.set_image(url=gif_url(spawn["name"])); caught.set_footer(text=f"Pokédex #{spawn['id']} · {RARITY_LABELS[rarity]}")
        try: await msg.edit(embed=caught)
        except discord.HTTPException: await ctx.send(embed=caught)

    @commands.command(name="pokemons", aliases=["pc", "collection"])
    async def pokemon_collection(self, ctx, member=None):
        target = member or ctx.author
        if isinstance(member, str):
            try: target = await commands.MemberConverter().convert(ctx, member)
            except commands.BadArgument: target = ctx.author
        rows = list(db.pokemon_collection.find({"user_id": str(target.id)}).sort("caught_at", -1))
        if not rows:
            await ctx.send(embed=discord.Embed(title="📖  Empty Pokédex", description=(f"**{target.display_name}** hasn't caught any Pokémon yet!\n\nPokémon spawn every 1 minute — type `.catch <name>` when one appears!"), color=0xED4245)); return
        view = DexView(rows, target); embed, file = await view.build(); msg = await ctx.send(embed=embed, file=file, view=view); view.msg = msg

    @commands.command(name="setspawnchannel")
    @commands.has_permissions(manage_guild=True)
    async def set_spawn_channel(self, ctx):
        channel_id = str(ctx.channel.id); existing = db.pokemon_spawn_channels.find_one({"channel_id": channel_id})
        if existing:
            db.pokemon_spawn_channels.delete_one({"channel_id": channel_id}); active_spawns.pop(channel_id, None)
            await ctx.send(embed=discord.Embed(description=f"🛑 Pokémon spawning has been disabled in {ctx.channel.mention}.", color=0xED4245)); return
        db.pokemon_spawn_channels.delete_many({"guild_id": str(ctx.guild.id)})
        db.pokemon_spawn_channels.insert_one({"channel_id": channel_id, "guild_id": str(ctx.guild.id)})
        await ctx.send(embed=discord.Embed(description=f"✅ Pokémon will now spawn in {ctx.channel.mention} every 1 minute!", color=0x57F287))


async def setup(bot):
    await bot.add_cog(PokemonSpawn(bot))