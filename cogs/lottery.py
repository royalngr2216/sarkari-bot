from discord.ext import commands
import discord
import time

from utils.economy import (
    get_cash,
    remove_cash,
    format_cash,
    parse_amount
)

from utils.lottery import (
    get_lottery,
    add_ticket,
    get_total_pool
)


class Lottery(commands.Cog):

    def __init__(self, bot):

        self.bot = bot


    @commands.command(name="lottery")
    async def lottery(
        self,
        ctx,
        amount=None
    ):

        # BUY TICKETS

        if amount is not None:

            cash = get_cash(
                ctx.author.id
            )

            amount = parse_amount(
                amount,
                cash
            )

            if amount is None:

                await ctx.send(
                    "❌ Invalid amount."
                )

                return

            if amount < 100_000:

                await ctx.send(
                    "❌ Minimum lottery entry is 100K."
                )

                return

            if cash < amount:

                await ctx.send(
                    "❌ Not enough cash."
                )

                return

            remove_cash(
                ctx.author.id,
                amount
            )

            add_ticket(
                ctx.author.id,
                amount
            )

        # SHOW LOTTERY

        lottery = get_lottery()

        participants = lottery.get(
            "participants",
            {}
        )

        total_pool = get_total_pool()

        next_draw = lottery.get(
            "next_draw",
            int(time.time()) + 21600
        )

        remaining = max(
            0,
            next_draw - int(time.time())
        )

        hours = remaining // 3600

        minutes = (
            remaining % 3600
        ) // 60

        participant_text = ""

        sorted_users = sorted(

            participants.items(),

            key=lambda x: x[1],

            reverse=True
        )

        for index, (user_id, value) in enumerate(
            sorted_users[:10]
        ):

            user = self.bot.get_user(
                int(user_id)
            )

            if user:

                name = user.name

            else:

                name = f"User {user_id}"

            chance = 0

            if total_pool > 0:

                chance = round(
                    (value / total_pool) * 100,
                    2
                )

            medals = [
                "🥇",
                "🥈",
                "🥉"
            ]

            if index < 3:

                rank = medals[index]

            else:

                rank = f"#{index + 1}"

            participant_text += (

                f"{rank} {name}\n\n"

                f"🎟 **{format_cash(value)}**\n"

                f"📊 **{chance}%**\n\n"
            )

        if participant_text == "":

            participant_text = (

                "❌ No participants yet.\n\n"
            )

        embed = discord.Embed(
            color=0xF1C40F
        )

        embed.description = (

            f"💰 Current Lottery\n\n"

            f"**{format_cash(total_pool)}**\n\n"

            f"━━━━━━━━━━━━━━━━━━\n\n"

            f"{participant_text}"

            f"━━━━━━━━━━━━━━━━━━\n\n"

            f"⏰ Next Draw\n\n"

            f"**{hours}h {minutes}m**\n\n"

            f"━━━━━━━━━━━━━━━━━━\n\n"

            f"💡 Type **`.lottery amount`**\n"

            f"to buy tickets."
        )

        await ctx.send(embed=embed)


async def setup(bot):

    await bot.add_cog(
        Lottery(bot)
              )
