from discord.ext import commands
import discord
from datetime import datetime
from utils.pokemon_db import add_ball, get_balls

from utils.economy import (
    economy_collection,
    get_cash,
    remove_cash,
    format_cash,
    create_account
)


PADLOCK_PRICE = 250000
WORKER_PRICE = 5000000
LOCK_AND_KEY_PRICE = 2500000
SHOVEL_PRICE = 3000000


# ─────────────────────────
# POKÉ MART CONFIG
# ─────────────────────────
# Single source of truth for ball metadata. Mirrors the BALLS dict in
# cogs/pokemon_spawn.py (key -> db field name) so catch rates / future
# features (Emiel theft, sell command, etc.) can key off the same "pb"/
# "ub"/"mb" codes without duplicating logic.

POKE_MART_ITEMS = {
    "pb": {
        "name": "Poké Ball",
        "emoji": "<:pb:1517998351227031632>",
        "db": "pokeball",
        "price": 5_000,
    },
    "ub": {
        "name": "Ultra Ball",
        "emoji": "<:ub:1517997681564324114>",
        "db": "ultraball",
        "price": 75_000,
    },
    "mb": {
        "name": "Master Ball",
        "emoji": "<a:mb:1517997721288704111>",
        "db": "masterball",
        "price": 750_000,
    },
}

BALL_QUANTITIES = [1, 5, 10, 25, 50]


# ─────────────────────────
# SHOP VIEW
# ─────────────────────────

class ShopView(discord.ui.View):

    def __init__(self, ctx):

        super().__init__(timeout=60)

        self.ctx = ctx


    @discord.ui.select(

        placeholder="Choose an item to purchase",

        options=[

            discord.SelectOption(

                label="Padlock",

                description="250K NGR • 1 day protection",

                emoji="🛡"

            ),

            discord.SelectOption(

                label="Worker",

                description="5M NGR • Passive income worker",

                emoji="⚒"

            ),

            discord.SelectOption(

                label="Lock and Key",

                description="2.5M NGR • 20 rob attempts",

                emoji="🔐"

            ),

            discord.SelectOption(

                label="Shovel",

                emoji="⛏",

                description="3M NGR • Unlock mining"
            )
        ]
    )

    async def select_callback(

        self,
        interaction: discord.Interaction,
        select: discord.ui.Select

    ):

        if interaction.user != self.ctx.author:

            await interaction.response.send_message(

                "❌ This menu is not for you.",

                ephemeral=True
            )

            return


        create_account(interaction.user.id)

        user_data = economy_collection.find_one({

            "user_id": str(interaction.user.id)

        })


        workers = user_data.get(
            "workers",
            {}
        )


        # ─────────────────────────
        # PADLOCK
        # ─────────────────────────

        if select.values[0] == "Padlock":

            cash = get_cash(
                interaction.user.id
            )

            if cash < PADLOCK_PRICE:

                embed = discord.Embed(

                    description=(

                        "❌ You don't have enough cash.\n\n"

                        f"Required: **{format_cash(PADLOCK_PRICE)}**"

                    ),

                    color=0xED4245
                )

                await interaction.response.send_message(

                    embed=embed,
                    ephemeral=True
                )

                return


            remove_cash(
                interaction.user.id,
                PADLOCK_PRICE
            )


            current_time = int(
                datetime.now().timestamp()
            )


            current_padlock = user_data.get(
                "padlock_until",
                0
            )


            if current_padlock < current_time:

                current_padlock = current_time


            new_time = current_padlock + 86400


            economy_collection.update_one(

                {
                    "user_id": str(interaction.user.id)
                },

                {
                    "$set": {
                        "padlock_until": new_time
                    }
                }
            )


            remaining_days = (

                new_time - current_time

            ) // 86400


            embed = discord.Embed(

                title="🛡 PADLOCK PURCHASED",

                description=(

                    "Your account is now protected from robbing.\n\n"

                    f"⏰ Total Protection:\n"
                    f"**{remaining_days} Days**"

                ),

                color=0x5865F2
            )

            embed.set_footer(

                text="Protection activates instantly"
            )

            await interaction.response.send_message(

                embed=embed
            )

            return


        # ─────────────────────────
        # WORKER
        # ─────────────────────────

        if select.values[0] == "Worker":

            owned_workers = len(workers)

            if owned_workers >= 5:

                embed = discord.Embed(

                    description=(

                        "❌ You already own the maximum number of workers."

                    ),

                    color=0xED4245
                )

                await interaction.response.send_message(

                    embed=embed,
                    ephemeral=True
                )

                return


            cash = get_cash(
                interaction.user.id
            )

            if cash < WORKER_PRICE:

                embed = discord.Embed(

                    description=(

                        "❌ You don't have enough cash.\n\n"

                        f"Required: **{format_cash(WORKER_PRICE)}**"

                    ),

                    color=0xED4245
                )

                await interaction.response.send_message(

                    embed=embed,
                    ephemeral=True
                )

                return


            remove_cash(
                interaction.user.id,
                WORKER_PRICE
            )


            worker_name = (
                f"worker-{owned_workers + 1}"
            )


            workers[worker_name] = {

                "level": 1,

                "stored": 0,

                "total_earned": 0,

                "last_claim": int(
                    datetime.now().timestamp()
                )

            }


            economy_collection.update_one(

                {
                    "user_id": str(interaction.user.id)
                },

                {
                    "$set": {
                        "workers": workers
                    }
                }
            )


            embed = discord.Embed(

                title="⚒ WORKER PURCHASED",

                description=(

                    f"Purchased **{worker_name}**\n\n"

                    "💰 Income:\n"
                    "**200K NGR / Day**\n\n"

                    "📈 Upgradeable up to Level 5"

                ),

                color=0x57F287
            )

            embed.set_footer(

                text="Use .workers to manage workers"
            )

            await interaction.response.send_message(

                embed=embed
            )

            return


        # ─────────────────────────
        # LOCK AND KEY
        # ─────────────────────────

        if select.values[0] == "Lock and Key":

            if user_data.get("lock_and_key"):

                embed = discord.Embed(

                    description=(

                        "❌ You already own "
                        "**Lock and Key**."

                    ),

                    color=0xED4245
                )

                await interaction.response.send_message(

                    embed=embed,
                    ephemeral=True
                )

                return


            cash = get_cash(
                interaction.user.id
            )


            if cash < LOCK_AND_KEY_PRICE:

                embed = discord.Embed(

                    description=(

                        "❌ You don't have enough cash.\n\n"

                        f"Required: **{format_cash(LOCK_AND_KEY_PRICE)}**"

                    ),

                    color=0xED4245
                )

                await interaction.response.send_message(

                    embed=embed,
                    ephemeral=True
                )

                return


            remove_cash(
                interaction.user.id,
                LOCK_AND_KEY_PRICE
            )


            economy_collection.update_one(

                {
                    "user_id": str(interaction.user.id)
                },

                {
                    "$set": {
                        "lock_and_key": True
                    }
                }
            )


            embed = discord.Embed(

                title="🔐 LOCK AND KEY PURCHASED",

                description=(

                    "Your rob attempts have increased.\n\n"

                    "📈 Rob Attempts:\n"
                    "**10 → 20**"

                ),

                color=0x57F287
            )

            embed.set_footer(

                text="Permanent Upgrade"
            )

            await interaction.response.send_message(

                embed=embed
            )

            return


        # ─────────────────────────
        # SHOVEL
        # ─────────────────────────

        if select.values[0] == "Shovel":

            cash = get_cash(
                interaction.user.id
            )


            if cash < SHOVEL_PRICE:

                embed = discord.Embed(

                    description=(

                        "❌ You don't have enough cash.\n\n"

                        f"Required: "
                        f"**{format_cash(SHOVEL_PRICE)}**"

                    ),

                    color=0xED4245
                )

                await interaction.response.send_message(

                    embed=embed,
                    ephemeral=True
                )

                return


            if user_data.get("shovel", False):

                embed = discord.Embed(

                    description=(

                        "❌ You already own a shovel."

                    ),

                    color=0xED4245
                )

                await interaction.response.send_message(

                    embed=embed,
                    ephemeral=True
                )

                return


            remove_cash(
                interaction.user.id,
                SHOVEL_PRICE
            )


            economy_collection.update_one(

                {
                    "user_id": str(interaction.user.id)
                },

                {
                    "$set": {
                        "shovel": True
                    }
                }
            )


            embed = discord.Embed(

                title="⛏ SHOVEL PURCHASED",

                description=(

                    "You purchased a shovel.\n\n"

                    "⛏ You can now use `.mine`"

                ),

                color=0x57F287
            )


            await interaction.response.send_message(
                embed=embed
            )

            return


    # ─────────────────────────
    # POKÉ MART DROPDOWN
    # ─────────────────────────

    @discord.ui.select(

        placeholder="Pokemart — Buy Pokeballs",

        options=[

            discord.SelectOption(

                label="Poké Ball",

                description="5K NGR each",

                emoji="<:pb:1517998351227031632>",

                value="pb"
            ),

            discord.SelectOption(

                label="Ultra Ball",

                description="75K NGR each",

                emoji="<:ub:1517997681564324114>",

                value="ub"
            ),

            discord.SelectOption(

                label="Master Ball",

                description="750K NGR each",

                emoji="<a:mb:1517997721288704111>",

                value="mb"
            )
        ]
    )

    async def pokemart_callback(

        self,
        interaction: discord.Interaction,
        select: discord.ui.Select

    ):

        if interaction.user != self.ctx.author:

            await interaction.response.send_message(

                "❌ This menu is not for you.",

                ephemeral=True
            )

            return


        ball_key = select.values[0]
        item = POKE_MART_ITEMS[ball_key]


        embed = discord.Embed(

            title=f"{item['emoji']} {item['name']}",

            description=(

                f"Select a quantity to purchase.\n\n"

                f"💵 Price per ball:\n"
                f"**{format_cash(item['price'])}**"

            ),

            color=0x5865F2
        )

        embed.set_footer(

            text="Prices scale automatically with quantity"
        )

        await interaction.response.send_message(

            embed=embed,

            view=BallQuantityView(self.ctx, ball_key),

            ephemeral=True
        )

        return


# ─────────────────────────
# POKÉ MART — QUANTITY VIEW
# ─────────────────────────

class BallQuantityView(discord.ui.View):

    def __init__(self, ctx, ball_key):

        super().__init__(timeout=60)

        self.ctx = ctx
        self.ball_key = ball_key

        item = POKE_MART_ITEMS[ball_key]

        for qty in BALL_QUANTITIES:

            total_price = item["price"] * qty

            button = discord.ui.Button(

                label=f"×{qty} — {format_cash(total_price)}",

                style=discord.ButtonStyle.secondary,

                custom_id=str(qty)
            )

            button.callback = self._make_callback(qty)

            self.add_item(button)


    def _make_callback(self, qty):

        async def callback(interaction: discord.Interaction):

            await self._purchase(interaction, qty)

        return callback


    async def _purchase(self, interaction: discord.Interaction, qty: int):

        if interaction.user != self.ctx.author:

            await interaction.response.send_message(

                "❌ This menu is not for you.",

                ephemeral=True
            )

            return


        item = POKE_MART_ITEMS[self.ball_key]

        total_price = item["price"] * qty


        create_account(interaction.user.id)

        cash = get_cash(interaction.user.id)


        if cash < total_price:

            embed = discord.Embed(

                description=(

                    "❌ You don't have enough cash.\n\n"

                    f"Required: **{format_cash(total_price)}**\n"
                    f"You have: **{format_cash(cash)}**"

                ),

                color=0xED4245
            )

            await interaction.response.send_message(

                embed=embed,
                ephemeral=True
            )

            return


        remove_cash(interaction.user.id, total_price)

        add_ball(interaction.user.id, item["db"], qty)


        remaining_balance = get_cash(interaction.user.id)
        balls = get_balls(interaction.user.id)


        embed = discord.Embed(

            title="<a:mb:1517997721288704111> PURCHASE COMPLETE",

            description=(

                f"{item['emoji']} **{item['name']} ×{qty}**\n\n"

                f"💵 Cost:\n"
                f"**{format_cash(total_price)}**\n\n"

                f"💰 Remaining Balance:\n"
                f"**{format_cash(remaining_balance)}**"

            ),

            color=0x57F287
        )

        embed.add_field(

            name="📦 Updated Inventory",

            value=(

                f"<:pb:1517998351227031632> Poké Ball: **{balls.get('pokeball', 0)}**\n"
                f"<:ub:1517997681564324114> Ultra Ball: **{balls.get('ultraball', 0)}**\n"
                f"<a:mb:1517997721288704111> Master Ball: **{balls.get('masterball', 0)}**"

            ),

            inline=False
        )

        embed.set_footer(

            text="Use .catch pb/ub/mb <pokemon> to start catching"
        )


        for child in self.children:
            child.disabled = True

        self.stop()


        await interaction.response.edit_message(

            embed=embed,
            view=self
        )

        return


# ─────────────────────────
# SHOP COMMAND
# ─────────────────────────

class Shop(commands.Cog):

    def __init__(self, bot):

        self.bot = bot


    @commands.command(name="shop")
    async def shop(self, ctx):

        create_account(ctx.author.id)

        user_data = economy_collection.find_one({

            "user_id": str(ctx.author.id)

        })


        workers = user_data.get(
            "workers",
            {}
        )


        current_time = int(
            datetime.now().timestamp()
        )


        padlock_until = user_data.get(
            "padlock_until",
            0
        )


        active_days = 0

        if padlock_until > current_time:

            active_days = (

                padlock_until - current_time

            ) // 86400


        lock_and_key = user_data.get(
            "lock_and_key",
            False
        )


        shovel_owned = user_data.get(
            "shovel",
            False
        )


        embed = discord.Embed(

            title="🛒 ECHLEON SHOP",

            description=(

                "Purchase upgrades, protection, "
                "and passive income systems.\n\n"

                "Use the dropdown menu below "
                "to buy items."

            ),

            color=0x5865F2
        )


        # PADLOCK

        embed.add_field(

            name="🛡️ Padlock",

            value=(

                "Protects your account from rob attempts.\n\n"

                "• Price: **250K NGR**\n"
                "• Duration: **1 Day**\n"
                f"• Active Time: **{active_days} Days**"

            ),

            inline=False
        )


        # WORKERS

        embed.add_field(

            name="🧌 Workers",

            value=(

                "Passive income generators.\n\n"

                "• Level 1 Income: **200K/day**\n"
                "• Max Level: **5**\n"
                "• Upgradeable: **Yes**\n"
                f"• Owned: **{len(workers)}/5**\n\n"

                "Workers generate money endlessly "
                "until claimed."

            ),

            inline=False
        )


        # LOCK AND KEY

        embed.add_field(

            name="🔐 Lock and Key",

            value=(

                "Increase rob attempts permanently.\n\n"

                "• Price: **2.5M NGR**\n"
                "• Rob Attempts: **10 → 20**\n"
                f"• Owned: **{'Yes' if lock_and_key else 'No'}**"

            ),

            inline=False
        )


        # SHOVEL

        embed.add_field(

            name="🪏 Shovel",

            value=(

                "Unlock the mining system.\n\n"

                "• Price: **3M NGR**\n"
                "• Unlocks: **.mine**\n"
                f"• Owned: **{'Yes' if shovel_owned else 'No'}**"

            ),

            inline=False
        )


        # POKÉ MART

        balls = get_balls(ctx.author.id)

        embed.add_field(

            name="<a:mb:1517997721288704111> Pokemart",

            value=(

                "Buy Poké Balls to catch wild Pokémon.\n\n"

                "• <:pb:1517998351227031632> Poké Ball: **5K NGR**\n"
                "• <:ub:1517997681564324114> Ultra Ball: **75K NGR**\n"
                "• <a:mb:1517997721288704111> Master Ball: **750K NGR**\n\n"

                f"📦 Owned: **{balls.get('pokeball', 0)}** / "
                f"**{balls.get('ultraball', 0)}** / "
                f"**{balls.get('masterball', 0)}**"

            ),

            inline=False
        )


        # TITLES

        embed.add_field(

            name="🎖 Titles",

            value=(

                "Permanent cosmetic badges shown on "
                "`.cash` and `.leaderboard`.\n\n"

                "• Prices: **10M → 10B NGR**\n"
                "• Use `.titles` to browse and buy"

            ),

            inline=False
        )


        embed.set_footer(

            text="ECHLEON Economy System"
        )


        await ctx.send(

            embed=embed,

            view=ShopView(ctx)
        )


async def setup(bot):

    await bot.add_cog(
        Shop(bot)
			)
