from discord.ext import commands
import discord

from datetime import datetime
import pytz

from utils.economy import (
    get_cash,
    add_cash,
    remove_cash,
    format_cash,
    parse_amount,
    economy_collection
)

IST = pytz.timezone("Asia/Kolkata")

GIVE_LIMIT = 5_000_000


class GiveView(discord.ui.View):

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


        user_data = economy_collection.find_one({

            "user_id": str(self.sender.id)

        })


        current_time = int(
            datetime.now(IST).timestamp()
        )


        last_reset = user_data.get(
            "give_reset",
            0
        )


        if current_time >= last_reset:

            economy_collection.update_one(

                {
                    "user_id": str(self.sender.id)
                },

                {
                    "$set": {

                        "give_sent_today": 0,

                        "give_reset": current_time + 86400
                    }
                }
            )

            user_data["give_sent_today"] = 0


        sent_today = user_data.get(

            "give_sent_today",

            0
        )


        if sent_today + self.amount > GIVE_LIMIT:

            embed = discord.Embed(

                description=(

                    "❌ Daily gift limit exceeded.\n\n"

                    f"Daily Limit: "
                    f"**{format_cash(GIVE_LIMIT)}**"

                ),

                color=discord.Color.red()
            )

            await interaction.response.edit_message(

                embed=embed,
                view=None
            )

            return


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


        remove_cash(

            self.sender.id,
            self.amount
        )


        add_cash(

            self.receiver.id,
            self.amount
        )


        economy_collection.update_one(

            {
                "user_id": str(self.sender.id)
            },

            {
                "$inc": {

                    "give_sent_today": self.amount
                }
            }
        )


        embed = discord.Embed(

            title="💸 CASH SENT",

            description=(

                f"{self.sender.mention} sent\n"
                f"**{format_cash(self.amount)}**\n"
                f"to {self.receiver.mention}"

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

            description="❌ Transfer cancelled.",

            color=discord.Color.red()
        )


        await interaction.response.edit_message(
            embed=embed,
            view=None
        )


class Give(commands.Cog):

    def __init__(self, bot):

        self.bot = bot


    @commands.command(name="give")
    async def give(
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


        embed = discord.Embed(

            title="💸 Confirm Transfer",

            description=(

                f"Send "
                f"**{format_cash(amount)}**\n"
                f"to {member.mention}?"

            ),

            color=discord.Color.blurple()
        )


        view = GiveView(

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
        Give(bot)
    )
