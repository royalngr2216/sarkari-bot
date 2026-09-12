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
from utils.game_state import crack_games


class Crack(commands.Cog):

    def __init__(self, bot):

        self.bot = bot


    # ─────────────────────────
    # START GAME
    # ─────────────────────────

    @commands.command(name="crack")
    async def crack(
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
                "Use: `.crack @user 1/3/5/7/9 amount`"
            )

            return


        if ctx.channel.id in crack_games:

            await ctx.send(
                "A crack match is already active."
            )

            return


        # PARSE BET

        amount = amount.lower()


        if amount.endswith("k"):

            bet = int(amount[:-1]) * 1000

        elif amount.endswith("m"):

            bet = int(amount[:-1]) * 1000000

        else:

            bet = int(amount)


        if bet <= 0:

            await ctx.send(
                "Bet must be greater than 0."
            )

            return


        create_account(ctx.author.id)
        create_account(opponent.id)


        if get_cash(ctx.author.id) < bet:

            await ctx.send(
                f"{ctx.author.mention} does not have enough cash."
            )

            return


        if get_cash(opponent.id) < bet:

            await ctx.send(
                f"{opponent.mention} does not have enough cash."
            )

            return


        wins_required = (bo // 2) + 1


        crack_games[ctx.channel.id] = {

            "player1": ctx.author,
            "player2": opponent,

            "bet": bet,

            "bo": bo,

            "wins_required": wins_required,

            "score1": 0,
            "score2": 0,

            "secret": random.randint(1, 100),

            "turn": ctx.author

        }


        embed = discord.Embed(

            title="💥 CRACK",

            description=(

                f"{ctx.author.mention} ⚔️ "
                f"{opponent.mention}\n\n"

                f"💵 Wager: "
                f"**{format_cash(bet)}**\n\n"

                f"🏆 First to "
                f"**{wins_required}** wins\n\n"

                f"🎯 Guess a number between "
                f"**1 and 100**\n\n"

                f"🎮 {ctx.author.mention} goes first\n\n"

                f"Use:\n"
                f"`.guess number`"

            ),

            color=discord.Color.orange()
        )


        await ctx.send(embed=embed)


    # ─────────────────────────
    # GUESS
    # ─────────────────────────

    @commands.command(name="guess")
    async def guess(
        self,
        ctx,
        number: int
    ):

        if ctx.channel.id not in crack_games:

            await ctx.send(
                "No active crack game."
            )

            return


        game = crack_games[ctx.channel.id]


        if ctx.author != game["turn"]:

            await ctx.send(
                "Not your turn."
            )

            return


        if number < 1 or number > 100:

            await ctx.send(
                "Guess between 1 and 100."
            )

            return


        secret = game["secret"]

        p1 = game["player1"]
        p2 = game["player2"]


        # CORRECT

        if number == secret:

            winner = ctx.author


            if winner == p1:

                loser = p2
                game["score1"] += 1

            else:

                loser = p1
                game["score2"] += 1


            embed = discord.Embed(

                title="🏆 ROUND WON",

                description=(

                    f"🎯 Secret Number: "
                    f"**{secret}**\n\n"

                    f"{winner.mention} cracked it.\n\n"

                    f"📊 Score\n"
                    f"**{game['score1']} - {game['score2']}**"

                ),

                color=discord.Color.green()
            )


            await ctx.send(embed=embed)


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

            game["secret"] = random.randint(1, 100)

            game["turn"] = loser


            next_embed = discord.Embed(

                description=(

                    "🎯 New round started.\n\n"

                    f"🎮 {loser.mention} goes first"

                ),

                color=discord.Color.orange()
            )

            await ctx.send(embed=next_embed)

            return


        # WRONG GUESS

        if number < secret:

            hint = "📈 Higher"

        else:

            hint = "📉 Lower"


        # SWITCH TURN

        if game["turn"] == p1:

            game["turn"] = p2

        else:

            game["turn"] = p1


        embed = discord.Embed(

            description=(

                f"{hint}\n\n"

                f"🎮 Turn:\n"
                f"{game['turn'].mention}"

            ),

            color=discord.Color.red()
        )


        await ctx.send(embed=embed)


    # ─────────────────────────
    # END MATCH
    # ─────────────────────────

    async def end_match(self, channel_id):

        game = crack_games[channel_id]


        if game["score1"] > game["score2"]:

            winner = game["player1"]
            loser = game["player2"]

        else:

            winner = game["player2"]
            loser = game["player1"]


        bet = game["bet"]


        # MONEY

        remove_cash(
            loser.id,
            bet
        )

        add_cash(
            winner.id,
            bet
        )


        # STATS

        record_win(
            winner.id,
            bet
        )

        record_loss(
            loser.id,
            bet
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

        embed = discord.Embed(

            title="🏆 CRACK RESULT",

            description=(

                f"{winner.mention} wins the match!\n\n"

                f"📊 Final Score\n"
                f"**{game['score1']} - {game['score2']}**\n\n"

                f"💵 Prize: "
                f"**{format_cash(bet)}**"

            ),

            color=discord.Color.gold()
        )


        channel = self.bot.get_channel(
            channel_id
        )

        await channel.send(embed=embed)


        del crack_games[channel_id]


async def setup(bot):

    await bot.add_cog(
        Crack(bot)
        )
