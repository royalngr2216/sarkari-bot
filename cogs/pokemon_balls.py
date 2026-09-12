from discord.ext import commands
import discord

from utils.pokemon_db import get_balls


# Shared metadata so the visual style matches the shop / catch system.
BALL_DISPLAY = {
    "pokeball": {
        "name": "Poké Ball",
        "emoji": "<:pb:1517998351227031632>",
        "code": "pb",
        "price": 10_000,
    },
    "ultraball": {
        "name": "Ultra Ball",
        "emoji": "<:ub:1517997681564324114>",
        "code": "ub",
        "price": 75_000,
    },
    "masterball": {
        "name": "Master Ball",
        "emoji": "<a:mb:1517997721288704111>",
        "code": "mb",
        "price": 750_000,
    },
}


class PokemonBalls(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="balls", aliases=["pokeballs", "inv"])
    async def balls(self, ctx, member: discord.Member = None):
        """Show a trainer's current Poké Ball inventory."""

        target = member or ctx.author
        balls = get_balls(target.id)

        total = sum(balls.get(key, 0) for key in BALL_DISPLAY)

        embed = discord.Embed(
            title=f"🎒 {target.display_name}'s Poké Balls",
            color=0x5865F2,
        )

        embed.set_thumbnail(url=target.display_avatar.url)

        if total == 0:
            embed.description = (
                "This bag is empty.\n\n"
                "Head to `.shop` and open the **🎾 Poké Mart** "
                "dropdown to stock up!"
            )
        else:
            lines = []
            for db_key, meta in BALL_DISPLAY.items():
                count = balls.get(db_key, 0)
                bar = _stock_bar(count)
                lines.append(
                    f"{meta['emoji']} **{meta['name']}** "
                    f"`{meta['code']}`\n"
                    f"{bar} **{count:,}**"
                )

            embed.description = "\n\n".join(lines)
            embed.add_field(
                name="📦 Total Balls",
                value=f"**{total:,}**",
                inline=True,
            )

        embed.set_footer(
            text="Catch with .catch pb/ub/mb <pokemon> • Buy more with .shop"
        )

        await ctx.send(embed=embed)


def _stock_bar(count: int, max_segments: int = 10) -> str:
    """Small visual bar so quantities are easier to read at a glance."""
    if count <= 0:
        filled = 0
    elif count >= 50:
        filled = max_segments
    else:
        filled = max(1, round((count / 50) * max_segments))

    return "🟩" * filled + "⬛" * (max_segments - filled)


async def setup(bot):
    await bot.add_cog(PokemonBalls(bot))
