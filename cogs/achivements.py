from discord.ext import commands
import discord

from utils.achievements import (
    COMMON_ACHIEVEMENTS,
    RARE_ACHIEVEMENTS,
    LEGENDARY_ACHIEVEMENTS
)

from utils.stats import get_profile

from utils.economy import (
    economy_collection,
    format_cash,
    add_cash
)


# ─────────────────────────
# PROGRESS BAR
# ─────────────────────────

def make_bar(current, required):

    percent = min(current / required, 1)

    filled = int(percent * 10)

    empty = 10 - filled

    return "█" * filled + "░" * empty


# ─────────────────────────
# DROPDOWN
# ─────────────────────────

class AchievementDropdown(discord.ui.Select):

    def __init__(self, member):

        self.member = member

        options = [

            discord.SelectOption(
                label="Common",
                emoji="⚪"
            ),

            discord.SelectOption(
                label="Rare",
                emoji="🟣"
            ),

            discord.SelectOption(
                label="Legendary",
                emoji="🟡"
            )
        ]

        super().__init__(

            placeholder="Select achievement category...",

            min_values=1,

            max_values=1,

            options=options
        )


    async def callback(self, interaction: discord.Interaction):

        category = self.values[0]

        if category == "Common":

            achievements = COMMON_ACHIEVEMENTS

            color = 0x95A5A6

        elif category == "Rare":

            achievements = RARE_ACHIEVEMENTS

            color = 0x9B59B6

        else:

            achievements = LEGENDARY_ACHIEVEMENTS

            color = 0xF1C40F


        stats = get_profile(self.member.id)

        user_data = economy_collection.find_one({

            "user_id": str(self.member.id)

        })

        if not user_data:

            user_data = {}


        embed = discord.Embed(

            title=f"{category.upper()} ACHIEVEMENTS",

            color=color
        )


        text = ""


        for achievement_id, achievement in achievements.items():

            achievement_type = achievement["type"]

            required = achievement["required"]


            # ─────────────────────────
            # CURRENT VALUE
            # ─────────────────────────

            if achievement_type == "workers_owned":

                current = len(
                    user_data.get(
                        "workers",
                        {}
                    )
                )

            elif achievement_type == "inventory_value":

                inventory = user_data.get(
                    "inventory",
                    {}
                )

                current = 0

                from utils.items import ALL_ITEMS

                for item_name, amount in inventory.items():

                    if item_name in ALL_ITEMS:

                        current += (

                            ALL_ITEMS[item_name]["price"]

                            * amount
                        )

            elif achievement_type == "networth":

                inventory = user_data.get(
                    "inventory",
                    {}
                )

                from utils.items import ALL_ITEMS

                inventory_value = 0

                for item_name, amount in inventory.items():

                    if item_name in ALL_ITEMS:

                        inventory_value += (

                            ALL_ITEMS[item_name]["price"]

                            * amount
                        )

                cash = user_data.get(
                    "cash",
                    0
                )

                current = cash + inventory_value

            else:

                current = stats.get(
                    achievement_type,
                    0
                )


            # ─────────────────────────
            # BAR
            # ─────────────────────────

            bar = make_bar(
                current,
                required
            )

            percent = min(
                int((current / required) * 100),
                100
            )


            # ─────────────────────────
            # REWARD
            # ─────────────────────────

            reward = achievement["reward"]

            if isinstance(reward, int):

                reward_text = format_cash(
                    reward
                )

            else:

                reward_text = reward.replace(
                    "_",
                    " "
                ).title()


            claimed = user_data.get(
                "claimed_achievements",
                []
            )

            if achievement_id in claimed:

                completed = "🏆 CLAIMED"

            elif current >= required:

                completed = "✅ READY TO CLAIM"

            else:

                completed = "❌ NOT COMPLETED"
            text += (

    f"**{achievement['name']}**\n"

    f"{achievement['description']}\n\n"

    f"`{bar}` **{percent}%**\n"

    f"**{current:,} / {required:,}**\n\n"

    f"🎁 **Reward:** {reward_text}\n"

    f"{completed}\n\n"

    f"━━━━━━━━━━━━━━━━━━\n\n"
            )


        embed.description = text

        await interaction.response.edit_message(

            embed=embed,

            view=self.view
        )


# ─────────────────────────
# VIEW
# ─────────────────────────

class AchievementView(discord.ui.View):

    def __init__(self, member):

        super().__init__(timeout=180)

        self.add_item(
            AchievementDropdown(member)
        )


# ─────────────────────────
# COG
# ────────────────────────
# ─────────────────────────
# COG
# ─────────────────────────

class Achievements(commands.Cog):

    def __init__(self, bot):

        self.bot = bot


    @commands.command(
        name="quests",
        aliases=["quest"]
    )

    async def achievements(self, ctx):

        embed = discord.Embed(

            title="🏆 QUESTS",

            description=(

                "Complete quests to unlock\n"

                "cash rewards, pets and flex titles.\n\n"

                "Select a category below."
            ),

            color=0x5865F2
        )


        await ctx.send(

            embed=embed,

            view=AchievementView(ctx.author)
        )


async def setup(bot):

    await bot.add_cog(
        Achievements(bot)
    )
