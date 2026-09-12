from discord.ext import commands
import discord
import random
import asyncio

from utils.economy import (
    create_account,
    get_cash,
    add_cash,
    remove_cash,
    format_cash
)
from utils.stats import (
    add_stats,
    update_biggest_win
)
from utils.achievement_checker import (
    check_achievements
)


# ─────────────────────────
# PARSE MONEY
# ─────────────────────────

def parse_amount(amount: str):
    amount = amount.lower()
    multipliers = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}
    try:
        if amount[-1] in multipliers:
            return int(float(amount[:-1]) * multipliers[amount[-1]])
        return int(amount)
    except Exception:
        return None


# ─────────────────────────
# CONFIG
# ─────────────────────────

# Your animated slot emoji — spins itself in Discord while unrevealed
SPINNING = "<a:slots:1514761192193789982>"

PAYOUTS = {
    "🍒": 1.1,
    "🍋": 1.4,
    "🍀": 2.0,
    "🔔": 3.5,
    "💎": 4.0,
    "👑": 7.0,
}

# REBALANCED ECONOMY:
# Old table paid out 124% of every bet on average (positive EV, no house
# edge), which let a single player mint unlimited money by going all-in
# repeatedly. This table pays out ~87% on average (a normal casino-style
# house edge) so the house wins over time instead of bleeding money.
OUTCOMES = {
    "lose":    50,
    "cherry":  22,
    "lemon":   11,
    "clover":   4,
    "bell":     3,
    "diamond":  2,
    "jackpot":  3,
    "troll":    5,
}

MAX_BET = 5_000_000

# Embed colors per state
COLOR_SPIN    = 0x5865F2   # blurple — spinning
COLOR_WIN     = 0x57F287   # green   — won
COLOR_JACKPOT = 0xF1C40F   # gold    — jackpot
COLOR_LOSE    = 0xED4245   # red     — lost
COLOR_TROLL   = 0x36393F   # dark    — troll


# ─────────────────────────
# BUILD EMBED
# ─────────────────────────

def build_embed(
    r0, r1, r2,
    author: discord.Member,
    bet: int,
    *,
    color: int = COLOR_SPIN,
    result_line: str = "",
) -> discord.Embed:
    """
    Single embed used for every state (spinning + final result).

    Layout:
      Title      🎰  S L O T S
      Description  the three reels, large and centred
      Fields     Bet | Result (only shown when result_line is set)
      Footer     avatar + username
    """
    # Reels row — spaced out so they look big and centred
    reels_row = f"╔══════════════╗\n║  {r0}  {r1}  {r2}  ║\n╚══════════════╝"

    embed = discord.Embed(
        title="🎰  S L O T S",
        description=reels_row,
        color=color,
    )

    # Always show bet
    embed.add_field(name="Bet", value=f"🪙 **{format_cash(bet)}**", inline=True)

    # Result field — blank placeholder keeps layout stable while spinning
    if result_line:
        embed.add_field(name="Result", value=result_line, inline=True)
    else:
        embed.add_field(name="Result", value="*Spinning…*", inline=True)

    embed.set_footer(
        text=author.display_name,
        icon_url=author.display_avatar.url,
    )

    return embed


class Slots(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="slots", aliases=["slot", "s"])
    async def slots(self, ctx, amount: str = None):

        create_account(ctx.author.id)

        # ── No argument ──────────────────────────────────────────────────
        if amount is None:
            embed = discord.Embed(
                title="🎰 Slots",
                description=(
                    "You need to enter a bet amount.\n\n"
                    "**Usage:** `.slots <amount>`\n"
                    "**Example:** `.slots 100k`  •  `.slots all`"
                ),
                color=COLOR_LOSE,
            )
            await ctx.send(embed=embed)
            return

        # ── Parse bet ────────────────────────────────────────────────────
        cash = get_cash(ctx.author.id)

        if amount.lower() == "all":
            amount = cash
        else:
            amount = parse_amount(amount)
            if amount is None:
                await ctx.send(
                    embed=discord.Embed(
                        title="🎰 Slots",
                        description="❌ That's not a valid amount.",
                        color=COLOR_LOSE,
                    )
                )
                return

        if amount <= 0:
            await ctx.send(
                embed=discord.Embed(
                    title="🎰 Slots",
                    description="❌ Bet must be greater than 0.",
                    color=COLOR_LOSE,
                )
            )
            return

        if cash < amount:
            await ctx.send(
                embed=discord.Embed(
                    title="🎰 Slots",
                    description=f"❌ You only have 🪙 **{format_cash(cash)}** — not enough to bet that.",
                    color=COLOR_LOSE,
                )
            )
            return

        if amount > MAX_BET:
            await ctx.send(
                embed=discord.Embed(
                    title="🎰 Slots",
                    description=f"❌ Max bet is 🪙 **{format_cash(MAX_BET)}**.",
                    color=COLOR_LOSE,
                )
            )
            return

        # ── Deduct bet ───────────────────────────────────────────────────
        remove_cash(ctx.author.id, amount)
        add_stats(ctx.author.id, games_played=1, total_gambled=amount)

        # ── Determine outcome ────────────────────────────────────────────
        roll = random.randint(1, 100)
        current = 0
        outcome = "lose"
        for name_key, chance in OUTCOMES.items():
            current += chance
            if roll <= current:
                outcome = name_key
                break

        # ── Build result reels ───────────────────────────────────────────
        outcome_reels = {
            "cherry":  ["🍒", "🍒", "🍒"],
            "lemon":   ["🍋", "🍋", "🍋"],
            "clover":  ["🍀", "🍀", "🍀"],
            "bell":    ["🔔", "🔔", "🔔"],
            "diamond": ["💎", "💎", "💎"],
            "jackpot": ["👑", "👑", "👑"],
            "troll":   ["💀", "💀", "💀"],
        }

        if outcome in outcome_reels:
            result = outcome_reels[outcome]
        else:
            lose_patterns = [
                ["🍒", "💎", "🍋"],
                ["👑", "🍀", "🍒"],
                ["💀", "🍋", "💎"],
                ["🔔", "🍒", "💀"],
                ["💎", "🍋", "🍀"],
                ["👑", "💀", "🍒"],
                ["👑", "👑", "🍒"],   # near-miss
                ["💎", "💎", "🍋"],   # near-miss
            ]
            result = random.choice(lose_patterns)

        near_miss = (result[0] == result[1]) and (outcome == "lose")

        # ── ANIMATION ────────────────────────────────────────────────────
        #
        # 3-edit chain (same as OwO's setTimeout approach).
        # The animated emoji self-animates in Discord — no loop needed.
        #
        #   send        →  🌀 🌀 🌀   spinning…
        #   +1.0 s      →  r0 🌀 🌀
        #   +0.7 s      →  r0 r1 🌀
        #   +1.0 s      →  r0 r1 r2  + result

        S = SPINNING

        # Step 0 — send, all spinning
        embed = build_embed(S, S, S, ctx.author, amount)
        msg = await ctx.send(embed=embed)

        # Step 1 — reel 0 lands
        await asyncio.sleep(1.0)
        embed = build_embed(result[0], S, S, ctx.author, amount)
        await msg.edit(embed=embed)

        # Step 2 — reel 1 lands
        await asyncio.sleep(0.7)
        embed = build_embed(result[0], result[1], S, ctx.author, amount)
        await msg.edit(embed=embed)

        # Step 3 — reel 2 lands (longer wait on near-miss for suspense)
        await asyncio.sleep(2.0 if near_miss else 1.0)

        # ── Final embed ──────────────────────────────────────────────────

        # TROLL
        if outcome == "troll":
            embed = build_embed(
                result[0], result[1], result[2],
                ctx.author, amount,
                color=COLOR_TROLL,
                result_line=f"☠️ EMIEL entered the casino and <a:sex:1514766414248939610> you.\n💸 Lost **{format_cash(amount)}**",
            )
            await msg.edit(embed=embed)
            return

        # LOSE
        if outcome == "lose":
            result_line = (
                f"<:komedi:1482793353748680956> **So close!**\n-🪙 {format_cash(amount)}"
                if near_miss
                else f"<:dealer:1519037377769640140> Better luck next time!\n"
            )
            embed = build_embed(
                result[0], result[1], result[2],
                ctx.author, amount,
                color=COLOR_LOSE,
                result_line=result_line,
            )
            await msg.edit(embed=embed)
            return

        # WIN
        symbol     = result[0]
        multiplier = PAYOUTS[symbol]
        winnings   = int(amount * multiplier)
        profit     = winnings - amount

        add_cash(ctx.author.id, winnings)
        update_biggest_win(ctx.author.id, winnings)

        if outcome == "jackpot":
            result_line = (
                f"<:dealer:1519037377769640140> **JACKPOT!** `{multiplier}x`\n"
                f"+🪙 {format_cash(profit)}"
            )
            color = COLOR_JACKPOT
        else:
            result_line = (
                f"<:dealer:1519037377769640140> **You won!** `{multiplier}x`\n"
                f"+🪙 {format_cash(profit)}"
            )
            color = COLOR_WIN

        embed = build_embed(
            result[0], result[1], result[2],
            ctx.author, amount,
            color=color,
            result_line=result_line,
        )
        await msg.edit(embed=embed)
        await check_achievements(self.bot, ctx.author)


async def setup(bot):
    await bot.add_cog(Slots(bot))
    
