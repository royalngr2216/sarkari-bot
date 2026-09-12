from discord.ext import commands
import discord
from datetime import datetime

from utils.stats import get_profile
from utils.economy import (
    economy_collection,
    format_cash
)
from utils.items import ALL_ITEMS

from utils.workers import (
    WORKER_LEVELS,
    WORKER_VALUES
)
from utils.achievements import (
    COMMON_ACHIEVEMENTS,
    RARE_ACHIEVEMENTS,
    LEGENDARY_ACHIEVEMENTS
)
from utils.titles import get_equipped
from utils.leaderboard_render import render_leaderboard

# ─────────────────────────
# ROLE UPDATE
# ─────────────────────────

async def update_roles(member, matches):
    return


# ─────────────────────────
# HELP CATEGORIES
# ─────────────────────────

HELP_CATEGORIES = {

    "💰 Economy": (
        "**.cash [user]**\n"
        "View balances.\n\n"
        "**.daily**\n"
        "Claim daily reward.\n\n"
        "**.weekly**\n"
        "Claim weekly reward.\n\n"
        "**.monthly**\n"
        "Claim monthly reward.\n\n"
        "**.give @user amount**\n"
        "Transfer money but has limits.\n\n"
        "**.donate @user amount**\n"
        "Donates money.\n\n"
        "**.rob @user**\n"
        "Attempt a robbery."
    ),

    "🎒 Items": (
        "**.shop**\n"
        "Open the item shop, including the Poké Mart for buying balls.\n\n"
        "**.inventory**\n"
        "View collected items.\n\n"
        "**.sell item amount**\n"
        "Sell inventory items.\n"
        ".sell all all for selling all.\n\n"
        "**.padlock**\n"
        "View protection status."
    ),

    "⚒ Workers": (
        "**.workers**\n"
        "View all workers.\n\n"
        "**.claim**\n"
        "Claim worker earnings.\n\n"
        "**.upgrade worker-1**\n"
        "Upgrade a worker."
    ),

    "🌎 Activities": (
        "**.job**\n"
        "Work for money.\n\n"
        "**.fish**\n"
        "Go fishing for rewards.\n\n"
        "**.hunt**\n"
        "Go hunting for rewards.\n\n"
        "**.mine**\n"
        "Go mining for very high rewards."
    ),

    "🎮 Games": (
        "**.randoms @user bo amount**\n"
        "Pokémon random battle.\n\n"
        "**.deathroll @user bo amount**\n"
        "Start a deathroll match.\n\n"
        "**.crack @user bo amount**\n"
        "Guess the hidden number."
    ),

    "🎲 Casino": (
        "**.cf h/t amount**\n"
        "Coinflip heads or tails.\n\n"
        "**.blackjack amount**\n"
        "Play a blackjack game with hit/stand/double.\n\n"
        "**.crash amount**\n"
        "Play a plane crash game, higher risk = higher payout.\n\n"
        "**.guessnumber amount**\n"
        "The faster you guess, the better rewards.\n\n"
        "**.mines amount**\n"
        "Play Original Mines Game, has better rewards.\n\n"
        "**.highlow amount**\n"
        "Bet by guessing higher or lower number next turn.\n\n"
        "**.lottery amount**\n"
        "Takes part in the lottery, higher amount = more chances of winning.\n\n"
        "**.slots amount**\n"
        "Play the slot machine."
    ),

    "🐉 Pokemon": (
        "**.catch <pb/ub/mb> <name>**\n"
        "Catch the wild Pokémon currently in the channel using a Poké/Ultra/Master Ball.\n\n"
        "**.balls [user]**\n"
        "View your (or another trainer's) Poké Ball inventory.\n\n"
        "**.pokemons [user]**\n"
        "View your (or another trainer's) Pokémon collection.\n\n"
        "**.team [p1, p2, ...]**\n"
        "View or set your active battle team (up to 6 Pokémon).\n\n"
        "**.moves <pokémon> <m1, m2...>**\n"
        "Teach a Pokémon up to 4 moves from its official learnset.\n\n"
        "**.moveset <pokémon> [user]**\n"
        "View a Pokémon's current assigned moveset.\n\n"
        "**.battle @user [amount]**\n"
        "Challenge a trainer to a Pokémon battle (with an optional cash wager).\n\n"
        "**.pokemart**\n"
        "Browse the global Pokémon marketplace for active listings.\n\n"
        "**.pokecheck @user**\n"
        "View all market listings posted by a specific trainer.\n\n"
        "**.pokemon sell <pokemon> <price>**\n"
        "List one of your Pokémon for sale in the market.\n\n"
        "**.pokemon buy @user <pokemon>**\n"
        "Buy a listed Pokémon from another trainer.\n\n"
        "**.diddy**\n"
        "View the collector's global activity feed (recent steals and sales).\n\n"
        "**.diddy sell <pokemon>**\n"
        "Instantly sell a Pokémon to the collector for a rarity-based payout."
    ),

    "📊 Profile": (
        "**.profile [user]**\n"
        "View player stats.\n\n"
        "**.leaderboard**\n"
        "View richest players.\n\n"
        "**.quests**\n"
        "View all quests and rewards."
    ),

    "🛠️ Admin": (
        "**.setcharacter <name>**\n"
        "Admin: Rename the character who steals catches, fish, and donations.\n\n"
        "**.setspawnchannel**\n"
        "Admin: Set/toggle the automatic Pokémon spawn channel.\n\n"
        "**.forcespawn**\n"
        "Admin: Immediately spawn one Pokémon in the current channel.\n\n"
        "**.spawntest**\n"
        "Admin: Force a wild Pokémon to spawn immediately.\n\n"
        "**.ping**\n"
        "Utility: View bot latency.\n\n"
        "**.stop**\n"
        "Utility: Force stop an active game."
    ),
}


# ─────────────────────────
# HELP DROPDOWN
# ─────────────────────────

class HelpDropdown(discord.ui.Select):

    def __init__(self):
        options = [
            discord.SelectOption(
                label=category,
                description=f"View {category} commands",
            )
            for category in HELP_CATEGORIES
        ]
        super().__init__(
            placeholder="Select a command category...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        category = self.values[0]
        embed = discord.Embed(
            title=f"📚 {category}",
            description=HELP_CATEGORIES[category],
            color=0x5865F2,
        )
        await interaction.response.edit_message(embed=embed, view=self.view)


class HelpView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(HelpDropdown())


class System(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="help")
    async def help(self, ctx):
        embed = discord.Embed(
            title="📚 Sarkari Adda Help",
            description=(
                "Select a category below to view available commands.\n\n"
                "Some commands may require permissions."
            ),
            color=0x5865F2,
        )
        await ctx.send(embed=embed, view=HelpView())


async def setup(bot):
    await bot.add_cog(System(bot))
