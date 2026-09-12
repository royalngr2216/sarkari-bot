from discord.ext import commands
import discord
import random
import datetime

from utils.economy import add_cash, format_cash, create_account
from utils.pokemon_db import db, log_emiel_event, get_emiel_log

from cogs.pokemon_spawn import (
    get_rarity,
    RARITY_LABELS,
    RARITY_EMBED_COLORS,
)


# ─────────────────────────────────────────────────────────────────────
# SELL PRICE RANGES (per rarity tier)
# ─────────────────────────────────────────────────────────────────────

SELL_PRICE_RANGES = {
    "common":      (15_000,     25_000),
    "pseudo":      (350_000,   650_000),
    "ultra_beast": (350_000,   650_000),
    "legendary":   (900_000,   1_100_000),
    "mythical":    (1_350_000, 1_650_000),
}

SELL_FLAVOR_TEXT = [
    "This one's has great potential.",
    "I will touch it. For science.",
    "This one asked me not to do that again.",
    "I will touch it a little.",
    "This one still seems upset about the licking.",
    "I've seen its insides.",
    "Collectors will 🍇 over this one.",
    "Rare find. Very Very rare.",
    "Not bad. This one is my type.",
]

EMIEL_COLOR = 0x2B2D31


class Emiel(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    # ─────────────────────────────────────────────
    # .emiel — global activity feed
    # ─────────────────────────────────────────────

    @commands.group(name="emiel", invoke_without_command=True)
    async def emiel(self, ctx):
        """Show Emiel's recent global activity (steals + purchases)."""

        entries = get_emiel_log(limit=10)

        embed = discord.Embed(
            title="📜 EMIEL LOG",
            color=EMIEL_COLOR,
        )

        if not entries:
            embed.description = (
                "🥷 Emiel hasn't made a move yet...\n\n"
                "Stay sharp — he could strike at any catch."
            )
        else:
            lines = []
            for entry in entries:
                lines.append(_format_log_line(entry))

            embed.description = "\n\n".join(lines)

        embed.set_footer(
            text="Catches have a 10% chance of being stolen by Emiel"
        )

        await ctx.send(embed=embed)

    # ─────────────────────────────────────────────
    # .emiel sell <pokemon> — instant sale to Emiel
    # ─────────────────────────────────────────────

    @emiel.command(name="sell")
    async def emiel_sell(self, ctx, *, pokemon_name: str = None):
        """Sell a Pokémon you own directly to Emiel for instant cash."""

        if not pokemon_name:
            await ctx.send(embed=discord.Embed(
                description=(
                    "**Usage:** `.emiel sell <Pokémon>`\n"
                    "**Example:** `.emiel sell Rayquaza`"
                ),
                color=0xED4245,
            ))
            return

        create_account(ctx.author.id)

        uid = str(ctx.author.id)
        pname = pokemon_name.strip().lower()

        poke_doc = db.pokemon_collection.find_one(
            {"user_id": uid, "name": pname}
        )

        if not poke_doc:
            await ctx.send(embed=discord.Embed(
                description=f"❌ You don't own a **{pokemon_name.title()}**.",
                color=0xED4245,
            ))
            return

        display = poke_doc.get("display", pname.title())
        pokedex_id = poke_doc.get("pokedex_id")
        rarity = get_rarity(pokedex_id) if pokedex_id is not None else "common"

        low, high = SELL_PRICE_RANGES.get(rarity, SELL_PRICE_RANGES["common"])
        price = random.randint(low, high)
        flavor = random.choice(SELL_FLAVOR_TEXT)

        # Remove the Pokémon from the seller's collection and (if present)
        # their active team, then pay out.
        db.pokemon_collection.delete_one({"user_id": uid, "name": pname})
        db.pokemon_teams.update_one(
            {"user_id": uid},
            {"$pull": {"team": pname}}
        )

        add_cash(ctx.author.id, price)

        log_emiel_event(
            "sale",
            seller_id=uid,
            pokemon_display=display,
            rarity=rarity,
            price=price,
        )

        embed = discord.Embed(
            title="💰 DEAL COMPLETE",
            color=RARITY_EMBED_COLORS.get(rarity, EMIEL_COLOR),
        )

        embed.add_field(name="Pokémon", value=f"**{display}**", inline=True)
        embed.add_field(
            name="Rarity",
            value=RARITY_LABELS.get(rarity, rarity.title()),
            inline=True,
        )
        embed.add_field(
            name="Price",
            value=f"**{price:,} NGR**",
            inline=False,
        )

        embed.description = f"*\"{flavor}\"*"
        embed.set_footer(text="Your balance has been updated.")

        await ctx.send(embed=embed)


def _format_log_line(entry: dict) -> str:
    """Render a single emiel_log document as a feed line."""

    if entry.get("type") == "steal":
        return (
            f"🥷 Stole **{entry.get('pokemon_display', 'a Pokémon')}** "
            f"from <@{entry.get('user_id')}>"
        )

    # "sale"
    price = entry.get("price", 0)
    return (
        f"💰 Bought **{entry.get('pokemon_display', 'a Pokémon')}** "
        f"from <@{entry.get('seller_id')}>\n"
        f"Paid: **{price:,} NGR**"
    )


async def setup(bot):
    await bot.add_cog(Emiel(bot))
