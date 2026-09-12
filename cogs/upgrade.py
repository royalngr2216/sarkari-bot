from discord.ext import commands
import discord

from utils.economy import (
    economy_collection,
    get_cash,
    remove_cash,
    format_cash,
    create_account
)

from utils.achievement_checker import (
    check_achievements
)

UPGRADE_COSTS = {

    2: 6000000,
    3: 7000000,
    4: 8000000,
    5: 10000000

}


INCOME_LEVELS = {

    1: 100000,
    2: 125000,
    3: 150000,
    4: 200000,
    5: 250000

}


class Upgrade(commands.Cog):

    def __init__(self, bot):

        self.bot = bot


    # ─────────────────────────
    # UPGRADE
    # ─────────────────────────

    @commands.command(name="upgrade")
    async def upgrade(
        self,
        ctx,
        worker_name: str
    ):

        create_account(ctx.author.id)

        user_data = economy_collection.find_one({

            "user_id": str(ctx.author.id)

        })


        workers = user_data.get(
            "workers",
            {}
        )


        worker_name = worker_name.lower()


        if worker_name not in workers:

            embed = discord.Embed(

                description="❌ Worker not found.",

                color=0xED4245
            )

            await ctx.send(embed=embed)

            return


        worker = workers[worker_name]

        current_level = worker.get(
            "level",
            1
        )


        # MAX LEVEL

        if current_level >= 5:

            embed = discord.Embed(

                description=(

                    "❌ This worker is already max level."

                ),

                color=0xED4245
            )

            await ctx.send(embed=embed)

            return


        next_level = current_level + 1

        upgrade_cost = UPGRADE_COSTS[next_level]


        cash = get_cash(ctx.author.id)

        if cash < upgrade_cost:

            embed = discord.Embed(

                description=(

                    "❌ You don't have enough cash.\n\n"

                    f"Required: "
                    f"**{format_cash(upgrade_cost)}**"

                ),

                color=0xED4245
            )

            await ctx.send(embed=embed)

            return


        remove_cash(
            ctx.author.id,
            upgrade_cost
        )


        worker["level"] = next_level


        economy_collection.update_one(

            {
                "user_id": str(ctx.author.id)
            },

            {
                "$set": {
                    "workers": workers
                }
            }
        )


        new_income = INCOME_LEVELS[next_level]


        embed = discord.Embed(

            title="⬆ WORKER UPGRADED",

            description=(

                f"⚒ Worker:\n"
                f"**{worker_name}**\n\n"

                f"📈 New Level:\n"
                f"**{next_level}**\n\n"

                f"💰 New Income:\n"
                f"**{format_cash(new_income)} / day**"

            ),

            color=0x57F287
        )


        embed.add_field(

            name="💸 Upgrade Cost",

            value=f"**{format_cash(upgrade_cost)}**",

            inline=False
        )


        await ctx.send(embed=embed)


        # ─────────────────────────
        # ACHIEVEMENTS
        # ─────────────────────────

        await check_achievements(
            self.bot,
            ctx.author
        )


async def setup(bot):

    await bot.add_cog(
        Upgrade(bot)
    )
