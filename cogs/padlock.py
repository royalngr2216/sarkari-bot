from discord.ext import commands
import discord
from datetime import datetime

from utils.economy import (
    economy_collection
)


class Padlock(commands.Cog):

    def __init__(self, bot):

        self.bot = bot


    # ─────────────────────────
    # PADLOCK STATUS
    # ─────────────────────────

    @commands.command(name="padlock")
    async def padlock(self, ctx):

        user_data = economy_collection.find_one({

            "user_id": str(ctx.author.id)

        })


        padlock_until = user_data.get(
            "padlock_until",
            0
        )


        current_time = int(
            datetime.now().timestamp()
        )


        # NO PADLOCK

        if padlock_until <= current_time:

            embed = discord.Embed(

                title="🛡 PADLOCK",

                description=(

                    "No active padlock."

                ),

                color=0xED4245
            )

            await ctx.send(embed=embed)

            return


        # ACTIVE PADLOCK

        remaining = padlock_until - current_time

        days = remaining // 86400

        hours = (remaining % 86400) // 3600


        embed = discord.Embed(

            title="🛡 PADLOCK",

            description=(

                "Protection is active.\n\n"

                f"⏰ Remaining Time:\n"
                f"**{days}d {hours}h**"

            ),

            color=0x5865F2
        )

        await ctx.send(embed=embed)


async def setup(bot):

    await bot.add_cog(
        Padlock(bot)
    )
