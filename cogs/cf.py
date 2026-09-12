from discord.ext import commands
import discord
import random
import asyncio

from utils.economy import (
    get_cash,
    add_cash,
    remove_cash,
    parse_amount,
    format_cash,
    MAX_BET
)

from utils.stats import (
    add_stats,
    update_biggest_win
)

from utils.achievement_checker import (
    check_achievements
)


class Coinflip(commands.Cog):

    def __init__(self, bot):
        self.bot = bot


    @commands.command(
        aliases=["cf"]
    )
    async def coinflip(self, ctx, choice: str, amount: str):
        choice = choice.lower()

        if choice not in ["heads", "tails", "h", "t"]:
            await ctx.send("Use: `.cf heads amount`")
            return

        if choice == "h":
            choice = "heads"

        if choice == "t":
            choice = "tails"

        cash = get_cash(ctx.author.id)
        amount = parse_amount(amount, cash)

        if amount is None or amount <= 0:
            await ctx.send("Invalid amount.")
            return

        if cash < amount:
            await ctx.send("You don't have enough cash.")
            return

        if amount > MAX_BET:
            await ctx.send(f"❌ Max bet is **{format_cash(MAX_BET)}**.")
            return

        # Start the suspense animation
        suspense_msg = await ctx.send("Flipping the coin... 🪙")

        suspense_texts = [
            "Flipping. 🪙",
            "Flipping.. 🪙",
            "Flipping... 🪙"
        ]

        # Loops through the text safely with a 1-second delay per frame
        for text in suspense_texts:
            await suspense_msg.edit(content=text)
            await asyncio.sleep(1.0)

        # GIFS
        heads_gif = (
            "https://cdn.discordapp.com/attachments/"
            "1356735875517775995/"
            "1360904053567262883/"
            "VN20250413_143452.gif"
        )

        tails_gif = (
            "https://cdn.discordapp.com/attachments/"
            "1356735875517775995/"
            "1360903389403283496/"
            "VN20250413_142456_2.gif"
        )

        # RESULT
        result = random.choice(["heads", "tails"])

        # PROFILE STATS
        add_stats(
            ctx.author.id,
            games_played=1,
            total_gambled=amount
        )

        if result == "heads":
            gif = heads_gif
        else:
            gif = tails_gif

        # WIN
        if choice == result:
            add_cash(ctx.author.id, amount)
            update_biggest_win(ctx.author.id, amount)
            outcome = f"✅ {ctx.author.mention} won **{format_cash(amount)}**"
            color = discord.Color.green()

        # LOSE
        else:
            remove_cash(ctx.author.id, amount)
            outcome = f"❌ {ctx.author.mention} lost **{format_cash(amount)}**"
            color = discord.Color.red()

        await check_achievements(self.bot, ctx.author)

        embed = discord.Embed(
            title="🪙 Coin Flip Result",
            description=(
                f"🎯 Result: **{result.upper()}**\n\n"
                f"{outcome}"
            ),
            color=color
        )
        embed.set_image(url=gif)

        # Show final results
        await suspense_msg.edit(content=None, embed=embed)


async def setup(bot):
    await bot.add_cog(Coinflip(bot))
    
