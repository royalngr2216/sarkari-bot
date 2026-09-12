from discord.ext import commands
import discord
import random

from utils.economy import (
    create_account,
    get_cash,
    add_cash,
    remove_cash,
    format_cash
)

from utils.stats import (
    record_win,
    record_loss,
    get_profile
)

from cogs.system import update_roles
from utils.game_state import (
    deathroll_games
)


class Deathroll(commands.Cog):

    def __init__(self, bot):

        self.bot = bot


    # ─────────────────────────
    # START GAME
    # ─────────────────────────

    @commands.command(name="deathroll")
    async def deathroll(
        self,
        ctx,
        opponent: discord.Member,
        bo: int,
        amount: str
    ):

        if opponent == ctx.author:

            await ctx.send(
                "You cannot play yourself."
            )

            return


        if bo not in [1, 3, 5, 7, 9]:

            await ctx.send(
                "Use: `.deathroll @user 1/3/5/7/9 amount`"
            )

            return


        if ctx.channel.id in deathroll_games:

            await ctx.send(
                "A deathroll game is already active."
            )

            return


        amount = amount.lower()


        if amount.endswith("k"):

            amount = int(
                float(amount[:-1]) * 1000
            )

        elif amount.endswith("m"):

            amount = int(
                float(amount[:-1]) * 1000000
            )

        else:

            amount = int(amount)


        if amount <= 0:

            await ctx.send(
                "Amount must be greater than 0."
            )

            return


        create_account(ctx.author.id)
        create_account(opponent.id)


        if get_cash(ctx.author.id) < amount:

            await ctx.send(
                f"{ctx.author.mention} does not have enough cash."
            )

            return


        if get_cash(opponent.id) < amount:

            await ctx.send(
                f"{opponent.mention} does not have enough cash."
            )

            return


        wins_required = (bo // 2) + 1


        deathroll_games[ctx.channel.id] = {

            "player1": ctx.author,
            "player2": opponent,

            "turn": ctx.author,

            "current": 100,

            "bet": amount,

            "bo": bo,

            "wins_required": wins_required,

            "score1": 0,
            "score2": 0
        }


        embed = discord.Embed(

            title="💀 DEATHROLL",

            description=(

                f"{ctx.author.mention} ⚔️ "
                f"{opponent.mention}\n\n"

                f"💵 Wager: "
                f"**{format_cash(amount)}**\n\n"

                f"🏆 First to "
                f"**{wins_required}** wins\n\n"

                f"🎲 Starting Number: "
                f"**100**\n\n"

                f"Use `.roll`"

            ),

            color=discord.Color.red()
        )


        await ctx.send(embed=embed)


    # ─────────────────────────
    # ROLL
    # ─────────────────────────

    @commands.command(name="roll")
    async def roll(self, ctx):

        if ctx.channel.id not in deathroll_games:

            await ctx.send(
                "No active deathroll game."
            )

            return


        game = deathroll_games[
            ctx.channel.id
        ]


        if ctx.author != game["turn"]:

            await ctx.send(
                "It is not your turn."
            )

            return


        rolled = random.randint(
            1,
            game["current"]
        )


        embed = discord.Embed(

            description=(

                f"🎲 {ctx.author.mention} rolled\n"
                f"# **{rolled}**"

            ),

            color=discord.Color.orange()
        )


        await ctx.send(embed=embed)


        # ROUND LOSS

        if rolled == 1:

            loser = ctx.author


            if loser == game["player1"]:

                winner = game["player2"]

                game["score2"] += 1

            else:

                winner = game["player1"]

                game["score1"] += 1


            round_embed = discord.Embed(

                title="🏆 ROUND WON",

                description=(

                    f"{loser.mention} rolled "
                    f"**1**\n\n"

                    f"{winner.mention} wins the round.\n\n"

                    f"📊 Score\n"
                    f"**{game['score1']} - {game['score2']}**"

                ),

                color=discord.Color.green()
            )

            await ctx.send(embed=round_embed)


            # MATCH END

            if (

                game["score1"] >= game["wins_required"]

                or

                game["score2"] >= game["wins_required"]

            ):

                await self.end_match(
                    ctx.channel.id
                )

                return


            # NEXT ROUND

            game["current"] = 100

            game["turn"] = loser


            next_embed = discord.Embed(

                description=(

                    "🎲 New round started.\n\n"

                    f"🎮 {loser.mention} goes first\n\n"

                    f"Starting Number: **100**"

                ),

                color=discord.Color.red()
            )

            await ctx.send(embed=next_embed)

            return


        # CONTINUE

        game["current"] = rolled


        if game["turn"] == game["player1"]:

            game["turn"] = game["player2"]

        else:

            game["turn"] = game["player1"]


    # ─────────────────────────
    # END MATCH
    # ─────────────────────────

    async def end_match(self, channel_id):

        game = deathroll_games[channel_id]


        if game["score1"] > game["score2"]:

            winner = game["player1"]
            loser = game["player2"]

        else:

            winner = game["player2"]
            loser = game["player1"]


        amount = game["bet"]


        # MONEY

        remove_cash(
            loser.id,
            amount
        )

        add_cash(
            winner.id,
            amount
        )


        # STATS

        record_win(
            winner.id,
            amount
        )

        record_loss(
            loser.id,
            amount
        )


        winner_stats = get_profile(
            winner.id
        )

        loser_stats = get_profile(
            loser.id
        )


        await update_roles(
            winner,
            winner_stats["matches"]
        )

        await update_roles(
            loser,
            loser_stats["matches"]
        )


        # RESULT EMBED

        end_embed = discord.Embed(

            title="☠️ DEATHROLL RESULT",

            description=(

                f"{winner.mention} wins the match!\n\n"

                f"📊 Final Score\n"
                f"**{game['score1']} - {game['score2']}**\n\n"

                f"💵 Prize: "
                f"**{format_cash(amount)}**"

            ),

            color=discord.Color.dark_red()
        )


        channel = self.bot.get_channel(
            channel_id
        )

        await channel.send(
            embed=end_embed
        )


        del deathroll_games[
            channel_id
        ]


async def setup(bot):

    await bot.add_cog(
        Deathroll(bot)
    )
