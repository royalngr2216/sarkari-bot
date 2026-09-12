from discord.ext import commands
import discord
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


# ─────────────────────────
# CARD HELPERS
# ─────────────────────────

SUITS = ["♠", "♥", "♦", "♣"]
RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
RANK_VALUES = {r: i + 2 for i, r in enumerate(RANKS)}  # 2=2, A=14

SUIT_EMOJI = {"♠": "♠️", "♥": "♥️", "♦": "♦️", "♣": "♣️"}

def random_card():
    return random.choice(RANKS), random.choice(SUITS)

def card_str(rank, suit):
    return f"`{rank}{suit}`"

# REBALANCED ECONOMY:
# Lowered the early multipliers so safe players don't farm free money.
# They now have to risk going deeper to get the big payouts.
MULTIPLIERS = [1.0, 1.10, 1.25, 1.50, 2.0, 2.5, 3.0]

def mult_ladder(current_round):
    """Renders multiplier ladder with current position highlighted."""
    lines = []
    icons = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣"]
    for i, (icon, mult) in enumerate(zip(icons, MULTIPLIERS)):
        if i < current_round:
            lines.append(f"✅ {icon} ~~{mult}×~~")
        elif i == current_round:
            lines.append(f"**▶ {icon} {mult}×** ← *you are here*")
        else:
            lines.append(f"⬜ {icon} {mult}×")
    return "\n".join(lines)


# ─────────────────────────
# ACTIVE GAMES
# ─────────────────────────

hl_games = {}


class HigherLower(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=["hl"])
    async def highlow(self, ctx, amount: str = None):
        """Guess if the next card is higher or lower! Chain wins to multiply."""

        if ctx.author.id in hl_games:
            await ctx.send(embed=discord.Embed(
                title="🎴 Game Already Running",
                description="You already have a game running!\nUse the **Higher**, **Lower**, or **Collect** buttons to continue.",
                color=0xED4245
            ))
            return

        if amount is None:
            embed = discord.Embed(
                title="🎴 Higher or Lower",
                description=(
                    "A card is shown — guess if the **next card** is higher or lower!\n"
                    "Chain correct guesses to climb the multiplier ladder!\n\n"
                    "━━━━━━━━━━━━━━━━━━━━━\n"
                    "**🏆 Multiplier Ladder:**\n"
                    f"{mult_ladder(-1)}\n"
                    "━━━━━━━━━━━━━━━━━━━━━\n\n"
                    "💰 **Collect** anytime to take your winnings!\n"
                    "⚠️ **Ties are a LOSS!** If the same card is drawn, you lose.\n\n"
                    "**Usage:** `.highlow <amount>` or `.hl <amount>`"
                ),
                color=0x5865F2
            )
            embed.set_footer(text="Chain 7 correct guesses for 3.0× payout! 🔥")
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
        if bet > MAX_BET:
            await ctx.send(embed=discord.Embed(
                title="❌ Bet Too High",
                description=f"Max bet is **{format_cash(MAX_BET)}**.",
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

        remove_cash(ctx.author.id, bet)
        add_stats(ctx.author.id, games_played=1, total_gambled=bet)

        rank, suit = random_card()
        hl_games[ctx.author.id] = {
            "bet": bet,
            "current_rank": rank,
            "current_suit": suit,
            "round": 0,
        }

        embed, view = self._build(ctx.author.id)
        msg = await ctx.send(embed=embed, view=view)
        hl_games[ctx.author.id]["msg"] = msg

    # ─────────────────────────
    # BUILD EMBED
    # ─────────────────────────

    def _build(self, user_id, status_line=None):
        g = hl_games[user_id]
        bet = g["bet"]
        rnd = g["round"]
        mult = MULTIPLIERS[rnd]
        potential = int(bet * mult)

        next_mult = MULTIPLIERS[rnd + 1] if rnd + 1 < len(MULTIPLIERS) else None
        next_potential = int(bet * next_mult) if next_mult else None

        card_val = RANK_VALUES[g["current_rank"]]
        card_display = card_str(g["current_rank"], g["current_suit"])

        higher_count = sum(1 for v in RANK_VALUES.values() if v > card_val)
        lower_count = sum(1 for v in RANK_VALUES.values() if v < card_val)
        hint = f"📊 `{higher_count}` cards higher · `{lower_count}` cards lower"

        desc_parts = [
            f"**Current Card: {card_display}** (value `{card_val}`)\n",
            hint,
            "\n━━━━━━━━━━━━━━━━━━━━━",
            f"**🏆 Multiplier Ladder:**\n{mult_ladder(rnd)}",
            "━━━━━━━━━━━━━━━━━━━━━",
            f"💰 **Collect now:** {format_cash(potential)}",
        ]
        if next_potential:
            desc_parts.append(f"⬆️ **Keep going:** {format_cash(next_potential)} if correct")

        if status_line:
            desc_parts.insert(0, status_line + "\n")

        embed = discord.Embed(
            title="🎴 Higher or Lower",
            description="\n".join(desc_parts),
            color=0x5865F2
        )
        embed.set_footer(text=f"Bet: {format_cash(bet)}  •  Round {rnd + 1} of {len(MULTIPLIERS)}")

        is_last = (rnd >= len(MULTIPLIERS) - 1)
        view = HlView(user_id=user_id, cog=self, collect_only=is_last)
        return embed, view

    # ─────────────────────────
    # GUESS
    # ─────────────────────────

    async def do_guess(self, interaction, user_id, direction):
        if interaction.user.id != user_id:
            await interaction.response.send_message("🚫 This isn't your game!", ephemeral=True)
            return

        g = hl_games.get(user_id)
        if not g:
            await interaction.response.send_message("No active game found.", ephemeral=True)
            return

        old_rank = g["current_rank"]
        old_val = RANK_VALUES[old_rank]
        new_rank, new_suit = random_card()
        new_val = RANK_VALUES[new_rank]

        # TIES ARE NOW A LOSS. The only way this evaluates to True is if it is strictly higher or strictly lower.
        correct = (
            (direction == "higher" and new_val > old_val) or
            (direction == "lower" and new_val < old_val)
        )

        g["current_rank"] = new_rank
        g["current_suit"] = new_suit
        g["round"] += 1

        if correct:
            if g["round"] >= len(MULTIPLIERS):
                # Max rounds — auto collect
                await self._collect(interaction, user_id, forced=True, last_card=card_str(new_rank, new_suit))
            else:
                arrow = "📈" if direction == "higher" else "📉"
                status = f"✅ **Correct!** {arrow} Next card: {card_str(new_rank, new_suit)} (`{new_val}`)"
                embed, view = self._build(user_id, status_line=status)
                embed.color = 0x57F287
                await interaction.response.edit_message(embed=embed, view=view)
        else:
            # Lost
            del hl_games[user_id]
            bet = g["bet"]
            record_loss(user_id, bet)
            rnd_before = g["round"] - 1
            mult_reached = MULTIPLIERS[rnd_before - 1] if rnd_before > 0 else None
            
            # Check if they lost because of a tie, and mock them for it.
            if new_val == old_val:
                reason = f"The next card was also {card_str(new_rank, new_suit)} (`{new_val}`)!\n**A tie is a loss!** ❌"
            else:
                reason = f"The next card was {card_str(new_rank, new_suit)} (`{new_val}`)\nYou guessed **{direction}** — ❌ Wrong!"

            desc = (
                f"{reason}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"💸 Lost: **{format_cash(bet)}**\n"
            )
            if mult_reached and rnd_before > 0:
                desc += f"*You made it to round {rnd_before} ({mult_reached}×) — should have collected!*"

            embed = discord.Embed(
                title="🎴 Higher or Lower — Wrong!",
                description=desc,
                color=0xED4245
            )
            embed.set_footer(text=f"Bet: {format_cash(bet)}  •  Play again with .hl <amount>")
            await interaction.response.edit_message(embed=embed, view=None)
            await check_achievements(self.bot, interaction.user)

    # ─────────────────────────
    # COLLECT
    # ─────────────────────────

    async def do_collect(self, interaction, user_id):
        if interaction.user.id != user_id:
            await interaction.response.send_message("🚫 This isn't your game!", ephemeral=True)
            return
        await self._collect(interaction, user_id)

    async def _collect(self, interaction, user_id, forced=False, last_card=None):
        g = hl_games.pop(user_id, None)
        if not g:
            return

        bet = g["bet"]
        rnd = g["round"]
        mult = MULTIPLIERS[min(rnd, len(MULTIPLIERS) - 1)]
        payout = int(bet * mult)
        profit = payout - bet

        add_cash(user_id, payout)
        update_biggest_win(user_id, profit)
        record_win(user_id, profit)

        if forced:
            title = "🎴 Higher or Lower — MAXIMUM WIN! 🎉"
            color = 0xFFD700
            banner = "🏆 You beat all 7 rounds! Legendary!"
        else:
            title = "🎴 Higher or Lower — Cashed Out!"
            color = 0x57F287
            banner = f"Smart move — took your winnings at **{mult}×**!"

        desc_parts = [
            f"*{banner}*\n",
            f"━━━━━━━━━━━━━━━━━━━━━",
            f"🎲 Rounds completed: **{rnd}** / {len(MULTIPLIERS)}",
            f"📈 Multiplier: **{mult}×**",
            f"💰 Payout: **{format_cash(payout)}**",
            f"📊 Profit: **+{format_cash(profit)}**",
            f"━━━━━━━━━━━━━━━━━━━━━",
        ]
        if last_card:
            desc_parts.append(f"🃏 Final card: {last_card}")

        embed = discord.Embed(
            title=title,
            description="\n".join(desc_parts),
            color=color
        )
        embed.set_footer(text=f"Bet: {format_cash(bet)}  •  Play again with .hl <amount>")
        await interaction.response.edit_message(embed=embed, view=None)
        await check_achievements(self.bot, interaction.user)

    async def on_timeout_cleanup(self, user_id):
        g = hl_games.pop(user_id, None)
        if g:
            add_cash(user_id, g["bet"])
            try:
                msg = g.get("msg")
                if msg:
                    embed = discord.Embed(
                        title="🎴 Higher or Lower — Timed Out",
                        description=f"⏰ Game timed out. Your bet of **{format_cash(g['bet'])}** has been returned.",
                        color=0x808080
                    )
                    await msg.edit(embed=embed, view=None)
            except Exception:
                pass


# ─────────────────────────
# VIEW
# ─────────────────────────

class HlView(discord.ui.View):

    def __init__(self, user_id, cog, collect_only=False):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.cog = cog
        if collect_only:
            for item in self.children:
                if hasattr(item, "label") and item.label in ["Higher ⬆️", "Lower ⬇️"]:
                    item.disabled = True

    @discord.ui.button(label="Higher ⬆️", style=discord.ButtonStyle.green)
    async def higher(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.do_guess(interaction, self.user_id, "higher")

    @discord.ui.button(label="Lower ⬇️", style=discord.ButtonStyle.red)
    async def lower(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.do_guess(interaction, self.user_id, "lower")

    @discord.ui.button(label="💰 Collect", style=discord.ButtonStyle.blurple)
    async def collect(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.do_collect(interaction, self.user_id)

    async def on_timeout(self):
        await self.cog.on_timeout_cleanup(self.user_id)


async def setup(bot):
    await bot.add_cog(HigherLower(bot))
    
