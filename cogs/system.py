from discord.ext import commands
import discord

HELP_CATEGORIES = {
    "💰 Economy": "**.cash [user]**\nView balances.\n\n**.daily**\nClaim daily reward.\n\n**.weekly**\nClaim weekly reward.\n\n**.monthly**\nClaim monthly reward.\n\n**.give @user amount**\nTransfer money but has limits.\n\n**.donate @user amount**\nDonates money.\n\n**.rob @user**\nAttempt a robbery.",
    "🎒 Items": "**.shop**\nOpen the item shop.\n\n**.inventory**\nView collected items.\n\n**.sell item amount**\nSell inventory items.\n\n**.padlock**\nView protection status.",
    "⚒ Workers": "**.workers**\nView all workers.\n\n**.claim**\nClaim worker earnings.\n\n**.upgrade worker-1**\nUpgrade a worker.",
    "🌎 Activities": "**.job**\nWork for money.\n\n**.fish**\nGo fishing.\n\n**.hunt**\nGo hunting.\n\n**.mine**\nGo mining.",
    "🎮 Games": "**.randoms @user bo amount**\nPokémon random battle.\n\n**.deathroll @user bo amount**\nStart a deathroll match.\n\n**.crack @user bo amount**\nGuess the hidden number.",
    "🎲 Casino": "**.cf h/t amount**\nCoinflip.\n\n**.blackjack amount**\nBlackjack.\n\n**.crash amount**\nCrash.\n\n**.guessnumber amount**\nGuess the number.\n\n**.mines amount**\nMines.\n\n**.highlow amount**\nHigher/lower.\n\n**.lottery amount**\nLottery.\n\n**.slots amount**\nSlots.",
    "🐉 Pokemon": "**.catch <pb/ub/mb> <name>**\nCatch Pokémon.\n\n**.balls [user]**\nView balls.\n\n**.pokemons [user]**\nView Pokémon collection.\n\n**.team [p1, p2, ...]**\nView or set battle team.\n\n**.moves <pokémon> <m1, m2...>**\nTeach moves.\n\n**.moveset <pokémon> [user]**\nView moveset.\n\n**.battle @user [amount]**\nBattle another trainer.\n\n**.pokemart**\nBrowse Pokémon market.\n\n**.pokecheck @user**\nView market listings.\n\n**.pokemon sell <pokemon> <price>**\nList Pokémon for sale.\n\n**.pokemon buy @user <pokemon>**\nBuy a listed Pokémon.\n\n**.diddy**\nView collector activity.\n\n**.diddy sell <pokemon>**\nSell Pokémon to the collector.",
    "📊 Profile": "**.profile [user]**\nView player stats.\n\n**.leaderboard**\nView richest players.\n\n**.quests**\nView quests and rewards.",
    "🛠️ Admin": "**.setcharacter <name>**\nAdmin: Rename the thief character.\n\n**.setspawnchannel**\nAdmin: Set/toggle Pokémon spawn channel.\n\n**.forcespawn**\nAdmin: Immediately spawn a Pokémon.\n\n**.spawntest**\nAdmin: Force a wild Pokémon spawn.\n\n**.ping**\nUtility: View bot latency.\n\n**.stop**\nUtility: Force stop an active game."
}

class HelpDropdown(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label=category, description=f"View {category} commands") for category in HELP_CATEGORIES]
        super().__init__(placeholder="Select a command category...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        category = self.values[0]
        embed = discord.Embed(title=f"📚 {category}", description=HELP_CATEGORIES[category], color=0x5865F2)
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
        embed = discord.Embed(title="📚 Sarkari Adda Help", description="Select a category below to view available commands.\n\nSome commands may require permissions.", color=0x5865F2)
        await ctx.send(embed=embed, view=HelpView())

    @commands.command(name="ping")
    async def ping(self, ctx):
        latency_ms = round(self.bot.latency * 1000)
        embed = discord.Embed(title="🏓 PONG!", color=0x57F287)
        embed.add_field(name="🤖 Bot Latency", value=f"`{latency_ms} ms`", inline=True)
        embed.add_field(name="💬 Message Latency", value="Calculating...", inline=True)
        message = await ctx.send(embed=embed)
        message_latency = round((message.created_at - ctx.message.created_at).total_seconds() * 1000)
        embed.set_field_at(1, name="💬 Message Latency", value=f"`{message_latency} ms`", inline=True)
        await message.edit(embed=embed)

async def setup(bot):
    await bot.add_cog(System(bot))
