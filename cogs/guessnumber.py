from discord.ext import commands
import discord
import asyncio
import random

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


# ─────────────────────────
# CONFIG
# ─────────────────────────

MAX_NUMBER = 100
MAX_GUESSES = 6  # Changed to 6

MULT_BY_GUESSES_USED = {
    1: 10.0,   # correct on 1st guess
    2: 5.0,
    3: 2.5,
    4: 1.5,
    5: 1.25,
}

# ─────────────────────────
# HELPERS
# ─────────────────────────

def proximity_hint(guess, secret):
    """Returns a hint string based on the gap between guess and secret."""
    gap = abs(guess - secret)
    direction = "📈 **Higher**" if guess < secret else "📉 **Lower**"

    if gap <= 30:
        warmth = "🔥 **Very close, The number is 30 less or more!**"
    else:
        warmth = "<:dealer:1519037377769640140> **Not even Close...**"

    return direction, warmth, gap

def guess_bar(guesses_left, max_guesses=MAX_GUESSES):
    filled = max_guesses - guesses_left
    bar = "🟥" * filled + "🟩" * guesses_left
    return bar

def mult_display():
    lines = []
    labels = ["1st", "2nd", "3rd", "4th", "5th"]
    mults = [10.0, 5.0, 2.5, 1.5, 1.25]
    icons = ["🏆", "🥇", "🥈", "🎗️" "🥉", "⭐"]
    for label, mult, icon in zip(labels, mults, icons):
        lines.append(f"{icon} `{label} guess` → **{mult}×**")
    return "\n".join(lines)


# ─────────────────────────
# ACTIVE GAMES
# ─────────────────────────

guess_games = {}


class GuessNumber(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="guessnumber", aliases=["gn"])
    async def guessnumber(self, ctx, amount: str = None):
        f"""Guess a number 1–100 in {MAX_GUESSES} tries. Fewer guesses = bigger payout!"""

        if ctx.author.id in guess_games:
            await ctx.send(embed=discord.Embed(
                title="🔢 Game Already Running",
                description="You already have a game in progress!\nType a number in the channel to continue, or type `quit` to stop.",
                color=0xED4245
            ))
            return

        if amount is None:
            embed = discord.Embed(
                title="🔢 Guess the Number",
                description=(
                    f"Guess a secret number between **1** and **100** in **{MAX_GUESSES} tries**!\n"
                    "The fewer guesses you use, the more you win.\n\n"
                    "━━━━━━━━━━━━━━━━━━━━━\n"
                    "**💡 Hints after every guess:**\n"
                    "• 🔥 *Very close* — gap of **≤20**\n"
                    "• 🧊 *Warmer...* — gap of **>20**\n"
                    "• Direction: 📈 Higher or 📉 Lower\n"
                    "━━━━━━━━━━━━━━━━━━━━━\n\n"
                    "**🏆 Multipliers:**\n"
                    f"{mult_display()}\n\n"
                    "**Usage:** `.guessnumber <amount>` or `.gn <amount>`"
                ),
                color=0x5865F2
            )
            embed.set_footer(text="Can you guess it on the first try? 🎯")
            await ctx.send(embed=embed)
            return

        cash = get_cash(ctx.author.id)
        bet = parse_amount(amount, cash)

        if bet is None or bet <= 0:
            await ctx.send(embed=discord.Embed(
                title="❌ Invalid Amount",
                description="Please enter a valid bet amount.",
                color=0xED4245
            ))
            return
        if cash < bet:
            await ctx.send(embed=discord.Embed(
                title="❌ Insufficient Funds",
                description=f"You only have **{format_cash(cash)}**.",
                color=0xED4245
            ))
            return
        if bet > MAX_BET:
            await ctx.send(embed=discord.Embed(
                title="❌ Bet Too High",
                description=f"Max bet is **{format_cash(MAX_BET)}**.",
                color=0xED4245
            ))
            return

        remove_cash(ctx.author.id, bet)
        add_stats(ctx.author.id, games_played=1, total_gambled=bet)

        secret = random.randint(1, MAX_NUMBER)
        guess_games[ctx.author.id] = {
            "bet": bet,
            "secret": secret,
            "guesses_left": MAX_GUESSES,
            "guesses_used": 0,
            "history": [],
            "channel_id": ctx.channel.id,
        }

        embed = discord.Embed(
            title="🔢 Guess the Number",
            description=(
                f"I'm thinking of a number between **1** and **{MAX_NUMBER}**.\n\n"
                f"**Type your guess below!**\n"
                f"Type `quit` to surrender and lose your bet.\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"🎯 Guesses remaining: **{MAX_GUESSES}**\n"
                f"{guess_bar(MAX_GUESSES)}\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"💰 Bet: **{format_cash(bet)}**\n"
                f"🏆 1st guess jackpot: **{format_cash(int(bet * 15.0))}**"
            ),
            color=0x5865F2
        )
        embed.set_footer(text="Good luck! 🍀")
        await ctx.send(embed=embed)

        # Wait for guesses
        def check(m):
            return (
                m.author.id == ctx.author.id
                and m.channel.id == ctx.channel.id
                and (m.content.strip().isdigit() or m.content.strip().lower() == "quit")
            )

        while True:
            g = guess_games.get(ctx.author.id)
            if not g:
                return

            try:
                msg = await self.bot.wait_for("message", timeout=60.0, check=check)
            except asyncio.TimeoutError:
                del guess_games[ctx.author.id]
                record_loss(ctx.author.id, g["bet"])
                embed = discord.Embed(
                    title="⏰ Time's Up!",
                    description=(
                        f"You took too long to guess!\n"
                        f"The number was **{g['secret']}**.\n\n"
                        f"💸 Lost **{format_cash(g['bet'])}**"
                    ),
                    color=0xED4245
                )
                embed.set_footer(text="Try again with .gn <amount>")
                await ctx.send(embed=embed)
                return

            content = msg.content.strip().lower()

            if content == "quit":
                del guess_games[ctx.author.id]
                record_loss(ctx.author.id, g["bet"])
                embed = discord.Embed(
                    title="🏳️ Surrendered",
                    description=(
                        f"The number was **{g['secret']}**.\n\n"
                        f"💸 Lost **{format_cash(g['bet'])}**"
                    ),
                    color=0xED4245
                )
                embed.set_footer(text="Better luck next time!")
                await ctx.send(embed=embed)
                return

            guess = int(msg.content.strip())
            if guess < 1 or guess > MAX_NUMBER:
                await ctx.send(embed=discord.Embed(
                    description=f"❌ Number must be between **1** and **{MAX_NUMBER}**.",
                    color=0xED4245
                ), delete_after=5)
                continue

            g["guesses_left"] -= 1
            g["guesses_used"] += 1
            g["history"].append(guess)
            history_str = " → ".join(str(h) for h in g["history"])

            if guess == g["secret"]:
                # WIN
                guesses_used = g["guesses_used"]
                mult = MULT_BY_GUESSES_USED.get(guesses_used, 1.1)
                payout = int(g["bet"] * mult)
                profit = payout - g["bet"]
                add_cash(ctx.author.id, payout)
                update_biggest_win(ctx.author.id, profit)
                record_win(ctx.author.id, profit)
                del guess_games[ctx.author.id]

                if guesses_used == 1:
                    title = "🏆 JACKPOT! First Try!"
                    color = 0xFFD700
                else:
                    title = f"🎉 Correct! Got it in {guesses_used} guess{'es' if guesses_used > 1 else ''}!"
                    color = 0x57F287

                embed = discord.Embed(title=f"🔢 {title}", color=color)
                embed.add_field(
                    name="🎯 The Number",
                    value=f"**{g['secret']}**",
                    inline=True
                )
                embed.add_field(
                    name="🎲 Guesses Used",
                    value=f"**{guesses_used}** / {MAX_GUESSES}",
                    inline=True
                )
                embed.add_field(
                    name="📈 Multiplier",
                    value=f"**{mult}×**",
                    inline=True
                )
                embed.add_field(
                    name="💰 Winnings",
                    value=f"**+{format_cash(profit)}**",
                    inline=False
                )
                embed.set_footer(text=f"Your guesses: {history_str}")
                await ctx.send(embed=embed)
                await check_achievements(self.bot, ctx.author)
                return

            elif g["guesses_left"] == 0:
                # Out of guesses
                del guess_games[ctx.author.id]
                record_loss(ctx.author.id, g["bet"])
                embed = discord.Embed(
                    title="💔 Out of Guesses!",
                    description=(
                        f"The number was **{g['secret']}**!\n\n"
                        f"💸 Lost **{format_cash(g['bet'])}**"
                    ),
                    color=0xED4245
                )
                embed.set_footer(text=f"Your guesses: {history_str}")
                await ctx.send(embed=embed)
                await check_achievements(self.bot, ctx.author)
                return

            else:
                # Hint
                direction, warmth, gap = proximity_hint(guess, g["secret"])
                guesses_left = g["guesses_left"]
                next_mult = MULT_BY_GUESSES_USED.get(g["guesses_used"] + 1, 1.1)

                embed = discord.Embed(
                    title=f"🔢 Guess #{g['guesses_used']} — {warmth}",
                    color=0xFEE75C if gap <= 20 else 0x5865F2
                )
                embed.add_field(
                    name="Your Guess",
                    value=f"`{guess}`",
                    inline=True
                )
                embed.add_field(
                    name="Direction",
                    value=direction,
                    inline=True
                )
                embed.add_field(
                    name="Guesses Left",
                    value=f"**{guesses_left}** {guess_bar(guesses_left)}",
                    inline=False
                )
                embed.add_field(
                    name="📜 History",
                    value=f"`{history_str}`",
                    inline=False
                )
                embed.set_footer(text=f"Next win multiplier: {next_mult}× • Bet: {format_cash(g['bet'])}")
                await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(GuessNumber(bot))
    
