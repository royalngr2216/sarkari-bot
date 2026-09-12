from discord.ext import commands
import discord

from utils.economy import (
    economy_collection,
    add_cash,
    format_cash,
    create_account
)

from utils.workers import (
    update_workers,
    WORKER_LEVELS
)


class Workers(commands.Cog):

    def __init__(self, bot):

        self.bot = bot


    # ─────────────────────────
    # WORKERS
    # ─────────────────────────

    @commands.command(name="workers")
    async def workers(self, ctx):

        create_account(ctx.author.id)

        update_workers(ctx.author.id)

        user_data = economy_collection.find_one({

            "user_id": str(ctx.author.id)

        })


        workers = user_data.get(
            "workers",
            {}
        )


        if not workers:

            embed = discord.Embed(

                description=(

                    "❌ You do not own any workers.\n\n"

                    "Use `.shop` to purchase one."

                ),

                color=0xED4245
            )

            await ctx.send(embed=embed)

            return


        embed = discord.Embed(

            title="⚒ YOUR WORKERS",

            description=(

                "Passive income overview."

            ),

            color=0x5865F2
        )


        total_unclaimed = 0


        for worker_name, worker in workers.items():

            level = worker.get(
                "level",
                1
            )

            stored = worker.get(
                "stored",
                0
            )

            total_earned = worker.get(
                "total_earned",
                0
            )

            income = WORKER_LEVELS[level]["income"]


            total_unclaimed += stored


            embed.add_field(

                name=f"⚒ {worker_name.upper()}",

                value=(

                    f"📈 Level: **{level}**\n"
                    f"💰 Income: **{format_cash(income)} / day**\n"
                    f"💵 Unclaimed: **{format_cash(stored)}**\n"
                    f"🏦 Lifetime Earned: **{format_cash(total_earned)}**"

                ),

                inline=False
            )


        embed.add_field(

            name="💰 Total Unclaimed",

            value=f"**{format_cash(total_unclaimed)}**",

            inline=False
        )


        embed.set_footer(

            text="Use .claim to collect all worker earnings"
        )


        await ctx.send(embed=embed)


    # ─────────────────────────
    # CLAIM
    # ─────────────────────────

    @commands.command(name="claim")
    async def claim(self, ctx):

        create_account(ctx.author.id)

        update_workers(ctx.author.id)

        user_data = economy_collection.find_one({

            "user_id": str(ctx.author.id)

        })


        workers = user_data.get(
            "workers",
            {}
        )


        if not workers:

            embed = discord.Embed(

                description="❌ You do not own any workers.",

                color=0xED4245
            )

            await ctx.send(embed=embed)

            return


        total_claimed = 0

        claim_text = ""


        for worker_name, worker in workers.items():

            stored = worker.get(
                "stored",
                0
            )


            if stored <= 0:

                continue


            total_claimed += stored


            claim_text += (

                f"{worker_name} → "
                f"**{format_cash(stored)}**\n"

            )


            worker["stored"] = 0


            worker["total_earned"] = (

                worker.get(
                    "total_earned",
                    0
                ) + stored
            )


        if total_claimed <= 0:

            embed = discord.Embed(

                description=(

                    "❌ Your workers have no earnings yet."

                ),

                color=0xED4245
            )

            await ctx.send(embed=embed)

            return


        add_cash(
            ctx.author.id,
            total_claimed
        )


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


        embed = discord.Embed(

            title="💰 WORKER CLAIM",

            description=(

                f"Collected **{format_cash(total_claimed)}**\n\n"

                f"{claim_text}"

            ),

            color=0x57F287
        )


        await ctx.send(embed=embed)


async def setup(bot):

    await bot.add_cog(
        Workers(bot)
    )
