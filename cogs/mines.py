import discord
from discord.ext import commands
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
    update_biggest_win,
    record_win,
    record_loss
)

from utils.achievement_checker import check_achievements

# --- Constants ---

BOARD_CONTENTS = (
    ["diamond"] * 6 +
    ["mine"] * 2 +
    ["emiel"]
)

EMIEL = "<:dealer:1519037377769640140>"
DIAMOND = "💎"
MINE = "💣"

MULTIPLIERS = {
    0: 1.00,
    1: 1.10,
    2: 1.5,
    3: 2.0,
    4: 3.0,
    5: 5.00,
    6: 10.00,
}

EMIEL_MESSAGES = [
    "Emiel was hiding there and raped you.",
    "Emiel raped you and ran away.",
    "Emiel fucked you behind the minefield.",
    "You found Emiel. Unfortunately, he got your ass.",
    "Emiel stole your cash and disappeared."
]

COLOR_PLAYING = 0x5865F2
COLOR_WIN = 0x57F287
COLOR_LOSE = 0xED4245


class TileButton(discord.ui.Button):
    def __init__(self, x: int, y: int, index: int):
        super().__init__(style=discord.ButtonStyle.secondary, label="\u200b", row=y)
        self.index = index

    async def callback(self, interaction: discord.Interaction):
        view: "MinesView" = self.view
        
        # Anti double-click and state protection
        if view.is_processing or view.is_finished():
            return
        
        view.is_processing = True
        await view.process_click(interaction, self)
        view.is_processing = False


class MinesView(discord.ui.View):
    def __init__(self, bot, ctx, bet):
        super().__init__(timeout=60.0)
        self.bot = bot
        self.ctx = ctx
        self.bet = bet
        self.revealed_count = 0
        self.is_processing = False
        self.message = None
        
        # Initialize and randomize board
        self.board = BOARD_CONTENTS.copy()
        random.shuffle(self.board)

        # Add 9 grid tiles
        idx = 0
        for y in range(3):
            for x in range(3):
                self.add_item(TileButton(x, y, idx))
                idx += 1

        # Add Cash Out button
        self.cashout_btn = discord.ui.Button(
            style=discord.ButtonStyle.success, 
            label="Cash Out", 
            row=3
        )
        self.cashout_btn.callback = self.cashout_callback
        self.add_item(self.cashout_btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensures only the command author can click the buttons."""
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(
                "🚫 This isn't your game!", 
                ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        """Handles 60 second timeout: Returns bet and disables board."""
        add_cash(self.ctx.author.id, self.bet)
        
        for child in self.children:
            child.disabled = True
            
        embed = self.get_embed(
            status="timeout", 
            action_msg="⏳ You took too long."
        )
        
        if self.message:
            try:
                await self.message.edit(embed=embed, view=self)
            except discord.HTTPException:
                pass

    def get_embed(self, status: str, action_msg: str, lost: int = 0, won: int = 0) -> discord.Embed:
        """Generates the embedded UI reflecting current game state."""
        if status == "playing":
            color = COLOR_PLAYING
        elif status == "win":
            color = COLOR_WIN
        else:
            color = COLOR_LOSE

        embed = discord.Embed(title="💣 Mines", color=color)
        embed.set_author(
            name=self.ctx.author.display_name, 
            icon_url=self.ctx.author.display_avatar.url
        )

        desc = f"### Action Log\n> {action_msg}\n\n"

        if status == "win":
            profit = won - self.bet
            desc += f"**Won:** {format_cash(won)}\n"
            desc += f"**Profit:** {format_cash(profit)}"
        elif status == "lose":
            desc += f"**Lost:** {format_cash(lost)}"
        elif status == "timeout":
            desc += "Your bet was returned."

        embed.description = desc

        if status == "playing":
            current_mult = MULTIPLIERS[self.revealed_count]
            next_mult = MULTIPLIERS.get(self.revealed_count + 1, current_mult)
            current_val = int(self.bet * current_mult)

            embed.add_field(name="Bet", value=format_cash(self.bet), inline=True)
            embed.add_field(name="Current Cashout", value=f"{format_cash(current_val)} ({current_mult:.2f}x)", inline=True)
            if self.revealed_count < 6:
                embed.add_field(name="Next Multiplier", value=f"{next_mult:.2f}x", inline=True)

        return embed

    def reveal_all(self):
        """Disables buttons and reveals hidden tiles strictly on loss conditions."""
        for child in self.children:
            child.disabled = True
            if isinstance(child, TileButton):
                content = self.board[child.index]
                if content == "diamond":
                    child.emoji = DIAMOND
                    child.style = discord.ButtonStyle.secondary
                elif content == "mine":
                    child.emoji = MINE
                    child.style = discord.ButtonStyle.danger
                elif content == "emiel":
                    child.emoji = EMIEL
                    child.style = discord.ButtonStyle.danger

    async def cashout_callback(self, interaction: discord.Interaction):
        """Cashout button handler."""
        if self.is_processing or self.is_finished():
            return
        self.is_processing = True
        await self.process_win(interaction)
        self.is_processing = False

    async def process_win(self, interaction: discord.Interaction):
        """Calculates win, updates balances, stats, and ends game."""
        self.stop()
        multiplier = MULTIPLIERS[self.revealed_count]
        winnings = int(self.bet * multiplier)
        profit = winnings - self.bet

        add_cash(self.ctx.author.id, winnings)
        
        if profit > 0:
            update_biggest_win(self.ctx.author.id, profit)
        record_win(self.ctx.author.id, profit)

        for child in self.children:
            child.disabled = True

        action_text = f"💵 You cashed out with **{multiplier:.2f}x** multiplier!"
        embed = self.get_embed("win", action_text, won=winnings)
        
        await interaction.response.edit_message(embed=embed, view=self)
        await check_achievements(self.bot, self.ctx.author)

    async def process_click(self, interaction: discord.Interaction, button: TileButton):
        """Core logic applied when an active tile is clicked."""
        content = self.board[button.index]

        if content == "diamond":
            button.emoji = DIAMOND
            button.disabled = True
            button.style = discord.ButtonStyle.success
            self.revealed_count += 1

            if self.revealed_count == 6:
                await self.process_win(interaction)
            else:
                embed = self.get_embed("playing", "Choose a tile...")
                await interaction.response.edit_message(embed=embed, view=self)

        elif content == "mine":
            self.stop()
            self.reveal_all()
            record_loss(self.ctx.author.id, self.bet)
            
            embed = self.get_embed("lose", "💥 You stepped on a mine.", lost=self.bet)
            await interaction.response.edit_message(embed=embed, view=self)

        elif content == "emiel":
            self.stop()
            button.emoji = EMIEL
            button.style = discord.ButtonStyle.danger
            button.disabled = True
            
            # Temporarily disable board interactions during suspense phase
            for child in self.children:
                child.disabled = True

            suspense_embed = self.get_embed("playing", "🤔 Something is hiding behind this tile...")
            await interaction.response.edit_message(embed=suspense_embed, view=self)

            await asyncio.sleep(1.2)

            # Option A: Emiel Double Loss Logic without negative balances
            extra_loss = min(get_cash(self.ctx.author.id), self.bet)
            total_loss = self.bet + extra_loss
            
            if extra_loss > 0:
                remove_cash(self.ctx.author.id, extra_loss)
                
            record_loss(self.ctx.author.id, total_loss)
            self.reveal_all()
            
            action_text = random.choice(EMIEL_MESSAGES)
            final_embed = self.get_embed("lose", f"{EMIEL} {action_text}", lost=total_loss)
            
            await interaction.message.edit(embed=final_embed, view=self)


class MinesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def mines(self, ctx, amount: str):
        """
        Start a game of Mines.
        Usage: .mines <amount> (e.g. .mines 100k, .mines all)
        """
        user_id = ctx.author.id
        
        # Handle 'all' separately to avoid potential parse_amount signature mismatch
        if amount.lower() == "all":
            bet = get_cash(user_id)
        else:
            try:
                bet = parse_amount(amount)
            except TypeError:
                # Fallback if parse_amount specifically requires two arguments
                bet = parse_amount(amount, get_cash(user_id))

        if not bet or bet <= 0:
            return await ctx.send("❌ Invalid bet amount.")

        if get_cash(user_id) < bet:
            return await ctx.send("❌ You don't have enough cash.")

        if bet > MAX_BET:
            return await ctx.send(f"❌ Max bet is **{format_cash(MAX_BET)}**.")

        # Immediate deduction upon start
        remove_cash(user_id, bet)

        # Record standard startup metrics
        add_stats(
            user_id,
            games_played=1,
            total_gambled=bet,
            total_mines=1
        )

        view = MinesView(self.bot, ctx, bet)
        embed = view.get_embed("playing", "Choose a tile...")
        
        message = await ctx.send(embed=embed, view=view)
        view.message = message


async def setup(bot):
    await bot.add_cog(MinesCog(bot))
      
