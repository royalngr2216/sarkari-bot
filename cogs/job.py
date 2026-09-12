from discord.ext import commands
import discord
import random
from datetime import datetime, timedelta
import pytz

from utils.economy import (
    economy_collection,
    add_cash,
    remove_cash,
    format_cash,
    create_account,
    get_cash
)
from utils.stats import (
    add_stats,
    update_biggest_win
)
from utils.achievement_checker import (
    check_achievements
)

IST = pytz.timezone("Asia/Kolkata")

JOB_COOLDOWN = 3600

JOB_REWARD = 100000


class Job(commands.Cog):

    def __init__(self, bot):

        self.bot = bot


    @commands.command(name="job")
    async def job(self, ctx):

        create_account(ctx.author.id)

        user_data = economy_collection.find_one({

            "user_id": str(ctx.author.id)

        })


        last_job = user_data.get(
            "last_job",
            0
        )


        current_time = int(
            datetime.now(IST).timestamp()
        )


        # ─────────────────────────
        # COOLDOWN
        # ─────────────────────────

        if current_time - last_job < JOB_COOLDOWN:

            remaining = (

                JOB_COOLDOWN -

                (current_time - last_job)

            )


            next_time = current_time + remaining


            embed = discord.Embed(

                description=(

                    "❌ Job cooldown active.\n\n"

                    f"⏰ Try again <t:{next_time}:R>"

                ),

                color=0xED4245
            )

            await ctx.send(embed=embed)

            return


        # SAVE TIME

        economy_collection.update_one(

            {
                "user_id": str(ctx.author.id)
            },

            {
                "$set": {
                    "last_job": current_time
                }
            }
        )


        # ─────────────────────────
        # BAD EVENT
        # ─────────────────────────

        robbed = random.randint(1, 100) <= 10


        if robbed:

            loss = 100000

            cash = get_cash(ctx.author.id)

            if cash < loss:

                loss = cash


            remove_cash(
                ctx.author.id,
                loss
            )


            embed = discord.Embed(

                title="💼 JOB FAILED",

                description=(

                    f"You went for work but "
                    f"**FURRY** 🍇 you and "
                    f"took **{format_cash(loss)}**."

                ),

                color=0xED4245
            )

            await ctx.send(embed=embed)

            return

        # ─────────────────────────
        # AZURE EVENT
        # ─────────────────────────

        azure = random.randint(1, 100) <= 5


        if azure:

            embed = discord.Embed(

                title="🧌 ZEW AZURE APPEARED",

                description=(

                    "Jew Azure arrived and stole"
                    "all of your money.\n\n"

                    f"💸 Azure took "
                    f"**{format_cash(JOB_REWARD)}**"

                ),

                color=0xED4245
            )

            await ctx.send(embed=embed)

            return


        # ─────────────────────────
        # SUCCESS
        # ─────────────────────────

        add_cash(
            ctx.author.id,
            JOB_REWARD
        )


        embed = discord.Embed(

            title="💼 JOB COMPLETE",

            description=(

                f"You completed your shift.\n\n"

                f"💰 Earned:\n"
                f"**{format_cash(JOB_REWARD)}**"

            ),

            color=0x57F287
        )

        add_stats(
            ctx.author.id,
            total_jobs=1
        )
        await check_achievements(
            self.bot,
            ctx.author
        )
        await ctx.send(embed=embed)


async def setup(bot):

    await bot.add_cog(
        Job(bot)
          )
