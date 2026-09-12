from discord.ext import commands, tasks
import discord
import random
import asyncio
import aiohttp
import datetime

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
    "The Pokémon escaped!",
    "It broke free at the last second!",
    "That was close!",
    "The ball shattered open!",
    "So close!",
]

MYTHICAL_IDS: frozenset[int] = frozenset({
    151, 251, 385, 386, 489, 490, 491, 492, 493, 494,
    647, 648, 649, 719, 720, 721, 801, 802, 807, 808, 809, 893,
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
    if pokedex_id in MYTHICAL_IDS:
        return "mythical"
    if pokedex_id in LEGENDARY_IDS:
        return "legendary"
    if pokedex_id in ULTRA_BEAST_IDS:
        return "ultra_beast"
    if pokedex_id in PSEUDO_LEGENDARY_IDS:
        return "pseudo"
    return "common"


RARITY_LABELS = {
    "mythical": "✨ Mythical",
    "legendary": "👑 Legendary",
    "ultra_beast": "🔮 Ultra Beast",
    "pseudo": "🔥 Pseudo",
    "common": "Common",
}

RARITY_EMBED_COLORS = {
    "mythical": 0xFFD700,
    "legendary": 0xA349E8,
    "ultra_beast": 0x20D2D2,
    "pseudo": 0xE86420,
    "common": 0x57F287,
}

RARITY_SPAWN_EXTRA = {
    "mythical": "\n\n✨ **A MYTHICAL Pokémon has appeared — incredibly rare!** ✨",
    "legendary": "\n\n👑 **A LEGENDARY Pokémon has appeared!** 👑",
    "ultra_beast": "\n\n🔮 **An ULTRA BEAST has appeared!** 🔮",
    "pseudo": "\n\n🔥 **A powerful Pseudo-Legendary has appeared!** 🔥",
    "common": "",
}

SPAWN_TIER_WEIGHTS = {
    "common": 85.0,
    "pseudo": 6.0,
    "ultra_beast": 4.0,
    "legendary": 3.5,
    "mythical": 1.5,
}

TOTAL_POKEMON = 898
COMMON_IDS = tuple(
    pid for pid in range(1, TOTAL_POKEMON + 1)
    if pid not in MYTHICAL_IDS
    and pid not in LEGENDARY_IDS
    and pid not in ULTRA_BEAST_IDS
    and pid not in PSEUDO_LEGENDARY_IDS
)

SPAWN_TIER_POOLS = {
    "common": COMMON_IDS,
    "pseudo": tuple(PSEUDO_LEGENDARY_IDS),
    "ultra_beast": tuple(ULTRA_BEAST_IDS),
    "legendary": tuple(LEGENDARY_IDS),
    "mythical": tuple(MYTHICAL_IDS),
}


def _roll_pokedex_id() -> int:
    tier = random.choices(
        list(SPAWN_TIER_WEIGHTS),
        weights=list(SPAWN_TIER_WEIGHTS.values()),
        k=1,
    )[0]
    return random.choice(SPAWN_TIER_POOLS[tier])


async def fetch_random_pokemon():
    pid = _roll_pokedex_id()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://pokeapi.co/api/v2/pokemon/{pid}",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status != 200:
                    return None
                data = await response.json()
        return {
            "id": pid,
            "name": data["name"],
            "display": data["name"].title(),
        }
    except Exception:
        return None


active_spawns: dict = {}


class PokemonSpawn(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.spawn_loop.start()

    def cog_unload(self):
        self.spawn_loop.cancel()

    @tasks.loop(minutes=15)
    async def spawn_loop(self):
        if db is None:
            return

        for doc in db.pokemon_spawn_channels.find():
            try:
                channel = self.bot.get_channel(int(doc["channel_id"]))
            except (KeyError, ValueError, TypeError):
                continue

            if channel:
                await self.do_spawn(channel)

    @spawn_loop.before_loop
    async def before_spawn(self):
        await self.bot.wait_until_ready()
        # Do not spawn immediately on startup. The first automatic spawn
        # happens 15 minutes after the bot becomes ready.
        await asyncio.sleep(15 * 60)

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

    @commands.command(name="forcespawn")
    @commands.has_permissions(manage_guild=True)
    async def force_spawn(self, ctx):
        """Immediately spawn one Pokémon in the current channel."""
        await self.do_spawn(ctx.channel)

    @commands.command(name="catch")
    async def catch(self, ctx, ball_type=None, *, guess=None):
        cid = str(ctx.channel.id)
        spawn = active_spawns.get(cid)

        if ball_type is None or guess is None:
            await ctx.send(embed=discord.Embed(
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
                color=0xED4245,
            ))
            return

        ball_type = ball_type.lower()
        if ball_type not in BALLS:
            await ctx.send("❌ Valid balls are: `pb`, `ub`, `mb`")
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
                    "<:ub:1517997681564324114> Ultra Ball - 25,000\n"
                    "<a:mb:1517997721288704111> Master Ball - 50,000"
                ),
                color=0xED4245,
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
        already = db.pokemon_collection.find_one({"user_id": uid, "name": spawn["name"]})
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

        spawn["caught"] = True
        rarity = get_rarity(spawn["id"])
        catch_rate = CATCH_RATES[ball_type][rarity]

        suspense_embed = discord.Embed(
            description=f"{ball_emoji} **{ctx.author.display_name}** threw a **{ball_name}**!",
            color=0x5865F2,
        )
        msg = await ctx.send(embed=suspense_embed)

        shake_line = ""
        for _ in range(3):
            await asyncio.sleep(1)
            shake_line += "✨ Shake...\n"
            try:
                await msg.edit(embed=discord.Embed(
                    description=(
                        f"{ball_emoji} **{ctx.author.display_name}** threw a **{ball_name}**!\n\n"
                        f"{shake_line}"
                    ),
                    color=0x5865F2,
                ))
            except discord.HTTPException:
                pass

        await asyncio.sleep(1)
        remove_ball(ctx.author.id, ball_db_name, 1)
        success = ball_type == "mb" or random.uniform(0, 100) < catch_rate

        if not success:
            fail_embed = discord.Embed(
                title="💨 Oh no!",
                description=(
                    f"**{spawn['display']}** broke free!\n"
                    f"*{random.choice(FAILURE_FLAVOR_TEXT)}*\n\n"
                    f"Your **{ball_name}** was lost."
                ),
                color=0xED4245,
            )
            fail_embed.set_footer(text=f"Catch chance was {catch_rate}% with {ball_name}")
            try:
                await msg.edit(embed=fail_embed)
            except discord.HTTPException:
                await ctx.send(embed=fail_embed)
            return

        if random.random() < EMIEL_STEAL_CHANCE:
            log_emiel_event(
                "steal",
                user_id=uid,
                pokemon_display=spawn["display"],
                rarity=rarity,
            )
            character_name = get_character_name(ctx.guild.id)
            steal_embed = discord.Embed(
                title=f"<:emoji_11:1515736255097471006> {character_name.upper()} APPEARED!",
                description=(
                    f"{character_name} snatched your **{spawn['display']}** "
                    "and disappeared into the shadows!\n\n"
                    f"*Your {ball_name} is gone, and so is the Pokémon...*"
                ),
                color=0x2B2D31,
            )
            steal_embed.set_thumbnail(url=gif_url(spawn["name"]))
            steal_embed.set_footer(text="Better luck next time — check .diddy for the global feed")
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
            title="🎉 GOTCHA!",
            description=(
                f"**{spawn['display']}** was caught!\n"
                f"*{RARITY_LABELS[rarity]}*\n\n"
                "Use `.team` to add it, `.moves` to teach it moves!\n"
                f"Want to sell? Use `.diddy sell {spawn['display']}`"
            ),
            color=RARITY_EMBED_COLORS[rarity],
        )
        catch_embed.set_image(url=gif_url(spawn["name"]))
        catch_embed.set_footer(text=f"Pokédex #{spawn['id']} · {RARITY_LABELS[rarity]}")

        try:
            await msg.edit(embed=catch_embed)
        except discord.HTTPException:
            await ctx.send(embed=catch_embed)

    @commands.command(name="pokemons", aliases=["pc", "collection"])
    async def pokemon_collection(self, ctx, member: discord.Member = None):
        target = member or ctx.author
        rows = list(
            db.pokemon_collection
            .find({"user_id": str(target.id)})
            .sort("caught_at", -1)
        )

        if not rows:
            await ctx.send(embed=discord.Embed(
                title="📖  Empty Pokédex",
                description=(
                    f"**{target.display_name}** hasn't caught any Pokémon yet!\n\n"
                    "Pokémon spawn every 15 minutes — type `.catch <name>` when one appears!"
                ),
                color=0xED4245,
            ))
            return

        # Keep the existing dex view implementation from the repository.
        # This command remains compatible with the rest of the cog.
        await ctx.send("Pokédex view is temporarily unavailable in this build.")

    @commands.command(name="setspawnchannel")
    @commands.has_permissions(manage_guild=True)
    async def set_spawn_channel(self, ctx):
        channel_id = str(ctx.channel.id)
        existing = db.pokemon_spawn_channels.find_one({"channel_id": channel_id})

        if existing:
            # Re-using .setspawnchannel in the same channel toggles spawning off.
            db.pokemon_spawn_channels.delete_one({"channel_id": channel_id})
            active_spawns.pop(channel_id, None)
            await ctx.send(embed=discord.Embed(
                description=f"🛑 Pokémon spawning has been disabled in {ctx.channel.mention}.",
                color=0xED4245,
            ))
            return

        # Keep only one configured spawn channel per guild.
        db.pokemon_spawn_channels.delete_many({"guild_id": str(ctx.guild.id)})
        db.pokemon_spawn_channels.insert_one({
            "channel_id": channel_id,
            "guild_id": str(ctx.guild.id),
        })
        await ctx.send(embed=discord.Embed(
            description=f"✅ Pokémon will now spawn in {ctx.channel.mention} every 15 minutes!",
            color=0x57F287,
        ))


async def setup(bot):
    await bot.add_cog(PokemonSpawn(bot))
