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
from utils.blackjack_render import render_blackjack


# ─────────────────────────
# CONFIG
# ─────────────────────────
SHUFFLE_EMOJI = "<a:14722:1519037409579499581>"
DEALER_EMOJI = "<:dealer:1519037377769640140>"

COLOR_SHUFFLE = 0x2B2D31
COLOR_PLAYING = 0x5865F2
COLOR_DEALER = 0xFEE75C
COLOR_WIN = 0x57F287
COLOR_LOSS = 0xED4245


# ─────────────────────────
# CARD HELPERS
# ─────────────────────────

SUITS = ["♠", "♥", "♦", "♣"]
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]


def make_deck():
    return [f"{r}{s}" for s in SUITS for r in RANKS]


def card_value(card):
    rank = card[:-1]
    if rank in ["J", "Q", "K"]:
        return 10
    if rank == "A":
        return 11
    return int(rank)


def hand_total(hand):
    total = sum(card_value(c) for c in hand)
    aces = sum(1 for c in hand if c[:-1] == "A")
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total


def fmt_card(card):
    return f"`{card}`"


# ─────────────────────────
# ACTIVE GAMES
# ─────────────────────────

bj_games = {}


class Blackjack(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    # ─────────────────────────
    # COMMAND
    # ─────────────────────────

    @commands.command(aliases=["bj"])
    async def blackjack(self, ctx, amount: str = None):

        if ctx.author.id in bj_games:
            await ctx.send(
                embed=discord.Embed(
                    title="⚠️ Action Required",
                    description="You already have a blackjack game in progress!\nPlease finish it using the buttons below.",
                    color=COLOR_LOSS
                )
            )
            return

        if amount is None:
            embed = discord.Embed(
                title="🃏 Premium Blackjack",
                description=(
                    "### The Rules\n"
                    "> Beat the dealer to **21** without going over.\n"
                    "> Dealer hits on **16 or below**, stands on **17+**.\n"
                    "> Natural Blackjack pays **1.5×**.\n\n"
                    "### Commands\n"
                    "` .bj <amount> ` or ` .bj all `\n"
                ),
                color=COLOR_PLAYING
            )
            embed.set_footer(text="May the odds be in your favor.")
            await ctx.send(embed=embed)
            return

        cash = get_cash(ctx.author.id)
        bet = parse_amount(amount, cash)

        if bet is None or bet <= 0:
            await ctx.send(embed=discord.Embed(description="❌ **Invalid bet amount.**", color=COLOR_LOSS))
            return
        if cash < bet:
            await ctx.send(embed=discord.Embed(description=f"❌ **Insufficient funds.** You have {format_cash(cash)}.", color=COLOR_LOSS))
            return
        if bet > MAX_BET:
            await ctx.send(embed=discord.Embed(description=f"❌ **Max bet is {format_cash(MAX_BET)}.**", color=COLOR_LOSS))
            return

        remove_cash(ctx.author.id, bet)
        add_stats(ctx.author.id, games_played=1, total_gambled=bet)

        deck = make_deck()
        random.shuffle(deck)

        player = [deck.pop(), deck.pop()]
        dealer = [deck.pop(), deck.pop()]

        bj_games[ctx.author.id] = {
            "player": player,
            "dealer": dealer,
            "deck": deck,
            "bet": bet,
            "done": False
        }

        # --- PHASE 1: SHUFFLE ANIMATION ---
        shuffle_embed = discord.Embed(color=COLOR_SHUFFLE)
        shuffle_embed.set_author(name=f"{ctx.author.display_name}'s Blackjack Table", icon_url=ctx.author.display_avatar.url)
        shuffle_embed.description = f"### Dealing...\n> {SHUFFLE_EMOJI} *The dealer is shuffling the deck and dealing cards...*"

        msg = await ctx.send(embed=shuffle_embed)
        bj_games[ctx.author.id]["msg"] = msg

        await asyncio.sleep(1.5)  # Allow animation to play out

        # Instant natural blackjack check
        if hand_total(player) == 21:
            del bj_games[ctx.author.id]
            if hand_total(dealer) == 21:
                add_cash(ctx.author.id, bet)
                await self._finalize_ui(msg, ctx.author, player, dealer, bet, "push", "Both drew a natural Blackjack. Bet returned.")
            else:
                payout = int(bet * 2.5)
                add_cash(ctx.author.id, payout)
                update_biggest_win(ctx.author.id, payout - bet)
                record_win(ctx.author.id, payout - bet)
                await self._finalize_ui(msg, ctx.author, player, dealer, bet, "bj", f"Natural Blackjack! You won {format_cash(payout - bet)}.")

            await check_achievements(self.bot, ctx.author)
            return

        # Start standard game
        embed, file, view = self._build_embed_view(ctx.author, "It's your turn. What will you do?")
        await msg.edit(embed=embed, attachments=[file], view=view)

    # ─────────────────────────
    # UI BUILDERS
    # ─────────────────────────

    def _build_embed_view(self, user, log_text):
        g = bj_games[user.id]
        player = g["player"]
        dealer = g["dealer"]
        bet = g["bet"]

        ptotal = hand_total(player)

        embed = discord.Embed(color=COLOR_PLAYING)
        embed.set_author(name=f"{user.display_name}'s Blackjack Game", icon_url=user.display_avatar.url)
        embed.description = f"> 👤 *{log_text}*"

        img = render_blackjack(
            player, dealer, ptotal, 0, True, bet, format_cash,
        )
        file = discord.File(img, filename="blackjack.png")
        embed.set_image(url="attachment://blackjack.png")
        embed.set_footer(text="Hit, Stand, or Double")

        cash = get_cash(user.id)
        can_double = cash >= bet and len(player) == 2

        view = BjView(user_id=user.id, can_double=can_double, cog=self)
        return embed, file, view

    def _build_animation_embed(self, user, player, dealer, bet, log_text):
        ptotal = hand_total(player)
        dtotal = hand_total(dealer)

        embed = discord.Embed(color=COLOR_DEALER)
        embed.set_author(name=f"{user.display_name}'s Blackjack Game", icon_url=user.display_avatar.url)
        embed.description = f"> {log_text}"

        img = render_blackjack(
            player, dealer, ptotal, dtotal, False, bet, format_cash,
        )
        file = discord.File(img, filename="blackjack.png")
        embed.set_image(url="attachment://blackjack.png")
        embed.set_footer(text="Dealer's turn...")
        return embed, file

    async def _finalize_ui(self, msg, user, player, dealer, bet, result, log_text, interaction=None):
        ptotal = hand_total(player)
        dtotal = hand_total(dealer)

        if result in ["win", "bj"]:
            color = COLOR_WIN
            icon = "✅"
        elif result == "loss":
            color = COLOR_LOSS
            icon = "❌"
        else:
            color = COLOR_DEALER
            icon = "🤝"

        embed = discord.Embed(color=color)
        embed.set_author(name=f"{user.display_name}'s Blackjack Game", icon_url=user.display_avatar.url)
        embed.description = f"> {icon} **{log_text}**"

        img = render_blackjack(
            player, dealer, ptotal, dtotal, False, bet, format_cash,
            result=result,
        )
        file = discord.File(img, filename="blackjack.png")
        embed.set_image(url="attachment://blackjack.png")
        embed.set_footer(text=f"Total Bet: {format_cash(bet)}  •  Play again: .bj <amount>")

        try:
            if interaction:
                await interaction.edit_original_response(embed=embed, attachments=[file], view=None)
            elif msg:
                await msg.edit(embed=embed, attachments=[file], view=None)
        except Exception:
            pass

    # ─────────────────────────
    # ACTIONS
    # ─────────────────────────

    async def do_hit(self, interaction, user_id):
        if interaction.user.id != user_id:
            await interaction.response.send_message("🚫 This isn't your game!", ephemeral=True)
            return

        g = bj_games.get(user_id)
        if not g:
            await interaction.response.send_message("No active game found.", ephemeral=True)
            return

        card = g["deck"].pop()
        g["player"].append(card)
        ptotal = hand_total(g["player"])

        if ptotal > 21:
            g["done"] = True
            await self._end_game(interaction, user_id, "bust")
        elif ptotal == 21:
            g["done"] = True
            await self._end_game(interaction, user_id, "stand")
        else:
            embed, file, view = self._build_embed_view(interaction.user, f"You hit and received {card}.")
            await interaction.response.edit_message(embed=embed, attachments=[file], view=view)

    async def do_stand(self, interaction, user_id):
        if interaction.user.id != user_id:
            await interaction.response.send_message("🚫 This isn't your game!", ephemeral=True)
            return

        g = bj_games.get(user_id)
        if not g:
            return

        g["done"] = True
        await self._end_game(interaction, user_id, "stand")

    async def do_double(self, interaction, user_id):
        if interaction.user.id != user_id:
            await interaction.response.send_message("🚫 This isn't your game!", ephemeral=True)
            return

        g = bj_games.get(user_id)
        if not g:
            return

        cash = get_cash(user_id)
        if cash < g["bet"]:
            await interaction.response.send_message("❌ Not enough cash to double down!", ephemeral=True)
            return

        remove_cash(user_id, g["bet"])
        add_stats(user_id, total_gambled=g["bet"])
        g["bet"] *= 2
        g["done"] = True

        card = g["deck"].pop()
        g["player"].append(card)

        await self._end_game(interaction, user_id, "double")

    # ─────────────────────────
    # DEALER ANIMATION & ENDING
    # ─────────────────────────

    async def _end_game(self, interaction, user_id, result_type):
        g = bj_games.pop(user_id, None)
        if not g:
            try:
                await interaction.response.defer()
            except Exception:
                pass
            return

        player = g["player"]
        dealer = g["dealer"]
        deck = g["deck"]
        bet = g["bet"]
        msg = g.get("msg")
        user = interaction.user

        ptotal = hand_total(player)

        if result_type == "double" and ptotal > 21:
            result_type = "bust"

        # --- PHASE 2: DEALER TURN ANIMATIONS ---
        if result_type != "bust":
            log_text = f"{DEALER_EMOJI} *Dealer flips the hidden card... it's a {dealer[1]}.*"
            reveal_embed, reveal_file = self._build_animation_embed(user, player, dealer, bet, log_text)

            try:
                await interaction.response.edit_message(embed=reveal_embed, attachments=[reveal_file], view=None)
            except Exception:
                pass

            while hand_total(dealer) < 17:
                await asyncio.sleep(1.2)  # Essential delay to prevent rate limiting
                drawn_card = deck.pop()
                dealer.append(drawn_card)

                log_text = f"{DEALER_EMOJI} *Dealer draws {drawn_card}...*"
                draw_embed, draw_file = self._build_animation_embed(user, player, dealer, bet, log_text)

                try:
                    await interaction.edit_original_response(embed=draw_embed, attachments=[draw_file])
                except Exception:
                    pass

            await asyncio.sleep(1.0)
        else:
            try:
                await interaction.response.defer()
            except Exception:
                pass

        # --- PHASE 3: FINAL PAYOUTS ---
        dtotal = hand_total(dealer)

        if ptotal > 21:
            outcome = "loss"
            final_log = f"You busted! Lost {format_cash(bet)}."
        elif dtotal > 21:
            outcome = "win"
            final_log = f"Dealer busted! You won {format_cash(bet)}."
        elif ptotal > dtotal:
            outcome = "win"
            final_log = f"You beat the dealer! Won {format_cash(bet)}."
        elif ptotal == dtotal:
            outcome = "push"
            final_log = f"It's a tie! Bet of {format_cash(bet)} returned."
        else:
            outcome = "loss"
            final_log = f"Dealer wins. Lost {format_cash(bet)}."

        if outcome == "win":
            add_cash(user_id, bet * 2)
            update_biggest_win(user_id, bet)
            record_win(user_id, bet)
        elif outcome == "push":
            add_cash(user_id, bet)
        else:
            record_loss(user_id, bet)

        await self._finalize_ui(msg, user, player, dealer, bet, outcome, final_log, interaction)

        try:
            await check_achievements(self.bot, ctx_user=user)
        except Exception:
            pass


# ─────────────────────────
# VIEW (BUTTONS)
# ─────────────────────────

class BjView(discord.ui.View):

    def __init__(self, user_id, can_double, cog):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.cog = cog
        self._responding = False
        if not can_double:
            for item in self.children:
                if hasattr(item, "label") and item.label == "Double Down":
                    item.disabled = True

    async def _safe_respond(self, interaction, coro):
        if self._responding:
            try:
                await interaction.response.defer()
            except Exception:
                pass
            return
        self._responding = True
        try:
            await coro
        except Exception:
            pass
        finally:
            self._responding = False

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary, emoji="👆")
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._safe_respond(interaction, self.cog.do_hit(interaction, self.user_id))

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.secondary, emoji="✋")
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._safe_respond(interaction, self.cog.do_stand(interaction, self.user_id))

    @discord.ui.button(label="Double Down", style=discord.ButtonStyle.success, emoji="🪙")
    async def double(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._safe_respond(interaction, self.cog.do_double(interaction, self.user_id))

    async def on_timeout(self):
        g = bj_games.pop(self.user_id, None)
        if g:
            add_cash(self.user_id, g["bet"])
            try:
                msg = g.get("msg")
                if msg:
                    embed = discord.Embed(
                        title="⏳ Game Abandoned",
                        description=f"You took too long! Your bet of **{format_cash(g['bet'])}** was returned.",
                        color=COLOR_SHUFFLE
                    )
                    await msg.edit(embed=embed, attachments=[], view=None)
            except Exception:
                pass


async def setup(bot):
    await bot.add_cog(Blackjack(bot))
