from discord.ext import commands
import discord
import random
import asyncio
import time

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
from utils.crash_math import duration_for_crash, mult_at_time, time_for_mult
from utils.crash_gif import build_crash_gif
from utils.crash_render import render_crash


# ─────────────────────────
# CRASH POINT GENERATION
# ─────────────────────────

INSTANT_CRASH_CHANCE = 0.05     # flat chance to crash at exactly 1.00x
REDIRECT_LOW = 1.10             # crashes that would land in [REDIRECT_LOW, REDIRECT_HIGH)
REDIRECT_HIGH = 1.50            # have a chance to get pulled down below REDIRECT_LOW instead
REDIRECT_CHANCE = 0.5           # how often that pull-down happens


def generate_crash_point():
    """
    Generates a crash point. Two things stack the deck against
    "spam-bet a tiny 1.05x-1.1x cashout every round" farming:

    1. The instant-crash (1.00x) chance is bumped up.
    2. A chunk of runs that would have landed in the 1.10x-1.50x band
       get pulled back down under 1.10x instead.

    Cashout targets of 2x and above are left essentially untouched —
    this only tightens the low-risk end of the curve.
    """
    if random.random() < INSTANT_CRASH_CHANCE:
        return 1.00

    crash = 1.00 / (1.0 - random.random())
    crash = round(crash, 2)

    if REDIRECT_LOW <= crash < REDIRECT_HIGH and random.random() < REDIRECT_CHANCE:
        crash = round(random.uniform(1.00, REDIRECT_LOW - 0.01), 2)

    return max(1.0, crash)


def _sample_curve(t_start, t_end, duration_ms, crash_point, n=20):
    """Even multiplier samples between two timestamps, for the static
    post-cashout snapshot image."""
    if t_end <= t_start:
        return [mult_at_time(t_start, duration_ms, crash_point)]
    pts = []
    for i in range(n + 1):
        t = t_start + (t_end - t_start) * (i / n)
        pts.append(mult_at_time(t, duration_ms, crash_point))
    return pts


# ─────────────────────────
# RECENT RESULTS TICKER
# ─────────────────────────

recent_crashes = []


def _push_recent(point):
    recent_crashes.append(point)
    if len(recent_crashes) > 10:
        recent_crashes.pop(0)


def _recent_ticker():
    if not recent_crashes:
        return "No recent games yet — be the first! 🚀"
    parts = []
    for p in recent_crashes[-10:]:
        if p < 1.5:
            parts.append(f"`{p:.2f}×`")
        elif p < 3.0:
            parts.append(f"**{p:.2f}×**")
        else:
            parts.append(f"🔥`{p:.2f}×`")
    return "  ".join(parts)


# ─────────────────────────
# ACTIVE GAMES
# ─────────────────────────

crash_player_games = {}


class Crash(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=["cr"])
    async def crash(self, ctx, amount: str = None, auto_cashout: str = None):
        """
        Bet on a rising multiplier — cash out before it crashes!
        """

        existing = crash_player_games.get(ctx.author.id)
        if existing and existing.get("finished"):
            del crash_player_games[ctx.author.id]

        if ctx.author.id in crash_player_games:
            await ctx.send(embed=discord.Embed(
                title="🚀 Game Already Running",
                description="You already have a crash game in progress!\nPress **💰 Cash Out** to end it first.",
                color=0xED4245
            ))
            return

        if amount is None:
            embed = discord.Embed(
                title="🚀 Crash",
                description=(
                    "**Cash out** before it crashes! 📈\n\n"
                    "━━━━━━━━━━━━━━━━━━━━━\n"
                    "💰 **Manual** — press Cash Out whenever you want\n"
                    "🎯 **Auto** — set a target and cash out automatically\n"
                    "━━━━━━━━━━━━━━━━━━━━━\n\n"
                    "**Usage:**\n"
                    "`.crash <amount>` — manual cashout\n"
                    "`.crash <amount> <target×>` — auto cashout\n\n"
                    "**Example:** `.crash 1000 2.5` → auto cashes at **2.5×**\n\n"
                    "The whole run plays out live — cash out any time before it crashes!"
                ),
                color=0x2B2D31
            )
            embed.add_field(name="Recent Games", value=_recent_ticker(), inline=False)
            embed.set_footer(text="Average crash ~1.03×  •  3% house edge")
            await ctx.send(embed=embed)
            return

        cash = get_cash(ctx.author.id)
        bet = parse_amount(amount, cash)

        if bet is None or bet <= 0:
            await ctx.send(embed=discord.Embed(title="❌ Invalid Amount", description="Please enter a valid bet amount.", color=0xED4245))
            return
        if cash < bet:
            await ctx.send(embed=discord.Embed(title="❌ Insufficient Funds", description=f"You only have **{format_cash(cash)}**.", color=0xED4245))
            return
        if bet > MAX_BET:
            await ctx.send(embed=discord.Embed(title="❌ Bet Too High", description=f"Max bet is **{format_cash(MAX_BET)}**.", color=0xED4245))
            return

        auto_target = None
        if auto_cashout is not None:
            try:
                auto_target = float(auto_cashout.replace("x", "").replace("X", ""))
                if auto_target <= 1.0:
                    await ctx.send(embed=discord.Embed(title="❌ Invalid Target", description="Auto cashout must be above **1.0×**.", color=0xED4245))
                    return
            except ValueError:
                await ctx.send(embed=discord.Embed(title="❌ Invalid Value", description="Please enter a valid auto cashout multiplier, e.g. `2.5`", color=0xED4245))
                return

        remove_cash(ctx.author.id, bet)
        add_stats(ctx.author.id, games_played=1, total_gambled=bet)

        crash_point = generate_crash_point()
        duration_ms = duration_for_crash(crash_point)

        # Render is CPU-bound — keep it off the event loop.
        loop = asyncio.get_event_loop()
        gif_buf = await loop.run_in_executor(None, build_crash_gif, crash_point, duration_ms, bet, format_cash)

        auto_str = f"🎯 Auto cashout target: **{auto_target}×**" if auto_target else "💡 Press **Cash Out** any time before it crashes"
        embed = discord.Embed(title="🚀 Crash — LIVE", description=auto_str, color=0x57F287)
        file = discord.File(gif_buf, filename="crash.gif")
        embed.set_image(url="attachment://crash.gif")
        embed.set_footer(text="Watch the multiplier climb...")

        view = CrashView(user_id=ctx.author.id, cog=self)
        msg = await ctx.send(embed=embed, file=file, view=view)

        game = {
            "bet": bet,
            "crash_point": crash_point,
            "duration_ms": duration_ms,
            "start": time.monotonic(),
            "auto_target": auto_target,
            "cashed_out": False,
            "finished": False,
            "msg": msg,
        }
        crash_player_games[ctx.author.id] = game

        # Auto-resolve at crash time if the player never cashes out.
        game["finalize_task"] = asyncio.create_task(self._finalize_after_delay(ctx.author.id))

        # Auto cashout at the exact moment the curve crosses the target.
        if auto_target is not None and auto_target < crash_point:
            t_auto = time_for_mult(auto_target, duration_ms, crash_point)
            game["auto_task"] = asyncio.create_task(self._auto_cashout_after_delay(ctx.author.id, t_auto))

    # ─────────────────────────
    # TIME-DRIVEN RESOLUTION
    # ─────────────────────────

    async def _finalize_after_delay(self, user_id):
        g = crash_player_games.get(user_id)
        if not g:
            return
        remaining = (g["duration_ms"] - (time.monotonic() - g["start"]) * 1000) / 1000
        if remaining > 0:
            await asyncio.sleep(remaining)

        g = crash_player_games.get(user_id)
        if not g or g["finished"]:
            return
        g["finished"] = True
        del crash_player_games[user_id]
        record_loss(user_id, g["bet"])
        _push_recent(g["crash_point"])

        embed = discord.Embed(
            title="💥 CRASHED!",
            description=f"*{_crash_quip(g['crash_point'])}*",
            color=0xED4245
        )
        embed.set_footer(text=f"Lost {format_cash(g['bet'])}  •  Play again with .crash <amount>")
        try:
            await g["msg"].edit(embed=embed, view=None)
        except Exception:
            pass

        try:
            member = g["msg"].guild.get_member(user_id) if g["msg"].guild else None
            if member:
                await check_achievements(self.bot, member)
        except Exception:
            pass

    async def _auto_cashout_after_delay(self, user_id, t_auto_ms):
        g = crash_player_games.get(user_id)
        if not g:
            return
        remaining = (t_auto_ms - (time.monotonic() - g["start"]) * 1000) / 1000
        if remaining > 0:
            await asyncio.sleep(remaining)

        g = crash_player_games.get(user_id)
        if not g or g["finished"]:
            return
        await self._resolve_cashout(user_id, g["auto_target"], interaction=None, auto=True)

    # ─────────────────────────
    # CASHOUT (manual button or auto)
    # ─────────────────────────

    async def cashout(self, interaction, user_id):
        if interaction.user.id != user_id:
            await interaction.response.send_message("🚫 This isn't your game!", ephemeral=True)
            return

        g = crash_player_games.get(user_id)
        if not g:
            await interaction.response.send_message("❌ No active game found.", ephemeral=True)
            return
        if g["finished"]:
            await interaction.response.send_message("💥 Too late — it already crashed!", ephemeral=True)
            return

        elapsed_ms = (time.monotonic() - g["start"]) * 1000
        if elapsed_ms >= g["duration_ms"]:
            await interaction.response.send_message("💥 Too late — it already crashed!", ephemeral=True)
            return

        current_mult = round(mult_at_time(elapsed_ms, g["duration_ms"], g["crash_point"]), 2)
        await self._resolve_cashout(user_id, current_mult, interaction=interaction, auto=False)

    async def _resolve_cashout(self, user_id, mult, interaction, auto):
        g = crash_player_games.get(user_id)
        if not g or g["finished"]:
            return
        g["finished"] = True
        del crash_player_games[user_id]

        for key in ("finalize_task", "auto_task"):
            t = g.get(key)
            if t and not t.done():
                t.cancel()

        bet = g["bet"]
        crash_point = g["crash_point"]
        duration_ms = g["duration_ms"]
        _push_recent(crash_point)

        payout = int(bet * mult)
        profit = payout - bet
        add_cash(user_id, payout)
        if profit > 0:
            update_biggest_win(user_id, profit)
            record_win(user_id, profit)
        else:
            record_loss(user_id, abs(profit))

        cashout_t = time_for_mult(mult, duration_ms, crash_point) or duration_ms
        history = _sample_curve(0, cashout_t, duration_ms, crash_point, n=16)
        ghost = _sample_curve(cashout_t, duration_ms, duration_ms, crash_point, n=12)[1:]

        color = 0x57F287 if profit >= 0 else 0xED4245
        result_text = f"**+{format_cash(profit)}**" if profit >= 0 else f"**-{format_cash(abs(profit))}**"
        title = "🎯 Auto Cashed Out!" if auto else "✅ Cashed Out!"

        embed = discord.Embed(
            title=title,
            description=f"Cashed out at `{mult}×` — crashed at `{crash_point}×`.\n{result_text} locked in.",
            color=color
        )
        img = render_crash(
            history, "cashed", bet, payout, format_cash,
            cashout_mult=mult, ghost_history=ghost, crash_point=crash_point
        )
        file = discord.File(img, filename="crash_result.png")
        embed.set_image(url="attachment://crash_result.png")
        embed.set_footer(text=f"Payout {format_cash(payout)}  •  Play again with .crash <amount>")

        msg = g["msg"]
        try:
            if interaction is not None:
                await interaction.response.edit_message(embed=embed, attachments=[file], view=None)
            else:
                await msg.edit(embed=embed, attachments=[file], view=None)
        except Exception:
            pass

        try:
            member = msg.guild.get_member(user_id) if msg.guild else None
            user = interaction.user if interaction is not None else member
            if user:
                await check_achievements(self.bot, user)
        except Exception:
            pass


def _crash_quip(crash_point):
    if crash_point == 1.0:
        return "Instant crash. Brutal. 😬"
    elif crash_point < 1.5:
        return "Crashed way too early..."
    elif crash_point < 3.0:
        return "Could've cashed out if you were faster!"
    elif crash_point < 7.0:
        return "That was actually pretty high!"
    else:
        return f"It went to {crash_point}×! You should've cashed out! 🔥"


class CrashView(discord.ui.View):

    def __init__(self, user_id, cog):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.cog = cog

    @discord.ui.button(label="Cash Out", style=discord.ButtonStyle.green, emoji="💰")
    async def cashout(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.cashout(interaction, self.user_id)

    async def on_timeout(self):
        g = crash_player_games.get(self.user_id)
        if g and not g.get("finished"):
            # The finalize task already (or will shortly) resolve the game
            # based on real elapsed time — nothing to do here but let it run.
            pass


async def setup(bot):
    await bot.add_cog(Crash(bot))
