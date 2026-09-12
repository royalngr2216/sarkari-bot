from discord.ext import commands
import discord

from utils.economy import (
    get_cash,
    add_cash,
    remove_cash,
    format_cash,
    parse_amount
)


class DonateView(discord.ui.View):

    def __init__(
        self,
        sender,
        receiver,
        amount
    ):

        super().__init__(timeout=30)

        self.sender = sender
        self.receiver = receiver
        self.amount = amount


    @discord.ui.button(
        label="Accept",
        style=discord.ButtonStyle.success
    )
    async def accept(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if interaction.user != self.sender:

            await interaction.response.send_message(
                "❌ Not for you.",
                ephemeral=True
            )

            return


        cash = get_cash(
            self.sender.id
        )


        if cash < self.amount:

            embed = discord.Embed(

                description="❌ Not enough cash.",

                color=discord.Color.red()
            )

            await interaction.response.edit_message(
                embed=embed,
                view=None
            )

            return


        received_amount = self.amount // 2

        stolen_amount = (
            self.amount -
            received_amount
        )


        remove_cash(

            self.sender.id,
            self.amount
        )


        add_cash(

            self.receiver.id,
            received_amount
        )


        embed = discord.Embed(

            title="🎁 DONATION SENT",

            description=(

                f"You tried donating\n"
                f"**{format_cash(self.amount)}** "
                f"to {self.receiver.mention}.\n\n"

                f"Emiel saw the donation\n"
                f"and 🍇 you and stole "
                f"**{format_cash(stolen_amount)}** "
                f"on the way.\n\n"

                f"💰 {self.receiver.mention} received:\n"
                f"**{format_cash(received_amount)}**"

            ),

            color=discord.Color.green()
        )


        await interaction.response.edit_message(
            embed=embed,
            view=None
        )


    @discord.ui.button(
        label="Cancel",
        style=discord.ButtonStyle.danger
    )
    async def cancel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if interaction.user != self.sender:

            await interaction.response.send_message(
                "❌ Not for you.",
                ephemeral=True
            )

            return


        embed = discord.Embed(

            description="❌ Donation cancelled.",

            color=discord.Color.red()
        )


        await interaction.response.edit_message(
            embed=embed,
            view=None
        )


class Donate(commands.Cog):

    def __init__(self, bot):

        self.bot = bot


    @commands.command(
        name="donate",
        aliases=["dn"]
    )
    async def donate(
        self,
        ctx,
        member: discord.Member,
        amount
    ):

        if member.bot:

            return


        if member == ctx.author:

            return


        cash = get_cash(
            ctx.author.id
        )


        amount = parse_amount(
            amount,
            cash
        )


        if amount is None or amount <= 0:

            await ctx.send(
                "Invalid amount."
            )

            return


        if cash < amount:

            embed = discord.Embed(

                description="❌ Not enough cash.",

                color=discord.Color.red()
            )

            await ctx.send(
                embed=embed
            )

            return


        received_amount = amount // 2

        stolen_amount = (
            amount -
            received_amount
        )


        embed = discord.Embed(

            title="🎁 Confirm Donation",

            description=(

                f"Donate "
                f"**{format_cash(amount)}**\n"
                f"to {member.mention}?"

            ),

            color=discord.Color.gold()
        )


        view = DonateView(

            ctx.author,
            member,
            amount
        )


        await ctx.send(

            embed=embed,
            view=view
        )


async def setup(bot):

    await bot.add_cog(
        Donate(bot)
            )
