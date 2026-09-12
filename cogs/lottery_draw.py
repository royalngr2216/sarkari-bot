from discord.ext import commands, tasks
import discord
import random
import time

from utils.economy import (
    add_cash,
    format_cash
)

from utils.lottery import (
    get_lottery,
    get_total_pool,
    reset_lottery
)


LOTTERY_CHANNEL = 710894803721912350


class LotteryDraw(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        self.draw_loop.start()


    def cog_unload(self):

        self.draw_loop.cancel()


    @tasks.loop(minutes=1)
    async def draw_loop(self):

        lottery = get_lottery()

        next_draw = lottery.get(
            "next_draw",
            0
        )

        if int(time.time()) < next_draw:

            return


        participants = lottery.get(
            "participants",
            {}
        )

        if not participants:

            reset_lottery()

            return


        user_ids = []
        weights = []


        for user_id, amount in participants.items():

            user_ids.append(
                int(user_id)
            )

            weights.append(
                amount
            )


        winner_id = random.choices(

            user_ids,

            weights=weights,

            k=1

        )[0]


        total_pool = get_total_pool()

        prize = int(
            total_pool * 0.8
        )

        azure_take = (
            total_pool - prize
        )


        add_cash(
            winner_id,
            prize
        )


        winning_amount = participants[
            str(winner_id)
        ]


        chance = round(

            (
                winning_amount
                /
                total_pool
            ) * 100,

            2
        )


        channel = self.bot.get_channel(
            LOTTERY_CHANNEL
        )

        if channel:

            winner = self.bot.get_user(
                winner_id
            )

            embed = discord.Embed(

                color=0xF1C40F
            )

            embed.description = (

                f"🏆 Winner\n"

                f"{winner.mention}\n\n"

                f"💰 Total Lottery Pot\n"

                f"**{format_cash(total_pool)}**\n\n"

                f"👥 Participants\n"

                f"**{len(participants)}**\n\n"

                f"🎲 Winning Chance\n"

                f"**{chance}%**\n\n"

                f"🧌 Jew Azure saw the lottery\n"

                f"and took "

                f"**{format_cash(azure_take)}** "

                f"before anyone noticed.\n\n"

                f"⏰ Next draw in 6 hours"
            )

            await channel.send(
                embed=embed
            )


        reset_lottery()


async def setup(bot):

    await bot.add_cog(
        LotteryDraw(bot)
    )
