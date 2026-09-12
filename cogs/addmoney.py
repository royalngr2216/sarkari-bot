from discord.ext import commands
import discord

from utils.economy import (
    add_cash,
    get_cash,
    format_cash,
    parse_amount,
    create_account
)


class AddMoney(commands.Cog):

    def __init__(self, bot):

        self.bot = bot


    @commands.command(name="addmoney")
    @commands.is_owner()
    async def addmoney(
        self,
        ctx,
        member: discord.Member,
        amount
    ):

        create_account(member.id)

        parsed = parse_amount(
            amount,
            get_cash(member.id)
        )

        if parsed is None or parsed <= 0:

            await ctx.send(
                "Invalid amount."
            )

            return

        add_cash(
            member.id,
            parsed
        )

        embed = discord.Embed(
            title="💰 MONEY ADDED",
            description=(
                f"Added **{format_cash(parsed)}** "
                f"to {member.mention}'s account.\n\n"
                f"New Balance: **{format_cash(get_cash(member.id))}**"
            ),
            color=discord.Color.green()
        )

        await ctx.send(embed=embed)


    @addmoney.error
    async def addmoney_error(self, ctx, error):

        if isinstance(error, commands.NotOwner):

            await ctx.send(
                "❌ Only the bot owner can use this command."
            )

            return

        if isinstance(error, commands.MemberNotFound):

            await ctx.send(
                "❌ Couldn't find that user."
            )

            return

        raise error


async def setup(bot):

    await bot.add_cog(
        AddMoney(bot)
    )
