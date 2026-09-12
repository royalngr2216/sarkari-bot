from discord.ext import commands
import discord

from utils.economy import get_cash, format_cash, create_account
from utils.titles import (
    TITLES,
    TITLE_ORDER,
    get_owned,
    get_equipped,
    buy_title,
    equip_title,
    unequip_title,
)
from utils.branding import brand


class Titles(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.group(name="titles", invoke_without_command=True)
    async def titles(self, ctx):
        """`.titles` — browse titles. `.titles buy/equip/unequip <name>`"""

        create_account(ctx.author.id)

        owned = set(get_owned(ctx.author.id))
        equipped = get_equipped(ctx.author.id)
        cash = get_cash(ctx.author.id)

        lines = []
        for key in TITLE_ORDER:
            t = TITLES[key]
            if key in owned:
                tag = "✅ Equipped" if key == equipped else "☑️ Owned"
            elif cash >= t["price"]:
                tag = "🟢 Affordable"
            else:
                tag = "🔒 Locked"
            lines.append(
                f"{t['emoji']} **{t['label']}** — {format_cash(t['price'])}  ·  {tag}"
            )

        embed = discord.Embed(
            title="🎖 TITLES",
            description=(
                "Permanent cosmetic badges shown on `.cash` and `.leaderboard`.\n"
                "Buying a title is permanent.\n\n"
                + "\n".join(lines)
                + "\n\n`.titles buy <name>` · `.titles equip <name>` · `.titles unequip`"
            ),
            color=0xFFD700,
        )
        brand(embed)
        await ctx.send(embed=embed)

    @titles.command(name="buy")
    async def titles_buy(self, ctx, key: str = None):
        create_account(ctx.author.id)

        if key is None:
            await ctx.send(embed=brand(discord.Embed(
                description="❌ Usage: `.titles buy <name>` (e.g. `.titles buy tycoon`)",
                color=0xED4245,
            )))
            return

        ok, msg = buy_title(ctx.author.id, key)
        await ctx.send(embed=brand(discord.Embed(
            description=msg,
            color=0x57F287 if ok else 0xED4245,
        )))

    @titles.command(name="equip")
    async def titles_equip(self, ctx, key: str = None):
        create_account(ctx.author.id)

        if key is None:
            await ctx.send(embed=brand(discord.Embed(
                description="❌ Usage: `.titles equip <name>`",
                color=0xED4245,
            )))
            return

        ok, msg = equip_title(ctx.author.id, key)
        await ctx.send(embed=brand(discord.Embed(
            description=msg,
            color=0x57F287 if ok else 0xED4245,
        )))

    @titles.command(name="unequip")
    async def titles_unequip(self, ctx):
        create_account(ctx.author.id)
        ok, msg = unequip_title(ctx.author.id)
        await ctx.send(embed=brand(discord.Embed(
            description=msg,
            color=0x57F287,
        )))


async def setup(bot):
    await bot.add_cog(Titles(bot))
