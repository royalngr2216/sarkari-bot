from discord.ext import commands
import discord
import random
import asyncio
from datetime import datetime
import pytz

from utils.economy import (
    economy_collection,
    add_cash,
    remove_cash,
    format_cash,
    create_account,
    get_cash
)
from utils.stats import add_stats
from utils.achievement_checker import check_achievements
from utils.items import FISHING_ITEMS

IST = pytz.timezone("Asia/Kolkata")

FISH_COOLDOWN = 1800
FISH_REWARD   = 50000


# ─────────────────────────
# HELPERS
# ─────────────────────────

def progress_bar(step, total=5):
    filled = int((step / total) * 10)
    bar = "█" * filled + "░" * (10 - filled)
    pct = int((step / total) * 100)
    return f"`[{bar}] {pct}%`"


def get_rarity(chance):
    if chance >= 20:
        return ("⬜ Common",   0x95A5A6)
    if chance >= 8:
        return ("🟩 Uncommon", 0x57F287)
    if chance >= 3:
        return ("🟦 Rare",     0x5865F2)
    return ("🌟 LEGENDARY",    0xF1C40F)


# Bobber animation — alternating water lines
BOBBER_FRAMES = [
    "〰️〰️〰️ 🪝 〰️〰️〰️",
    "〰️〰️ 🪝 〰️〰️〰️〰️",
    "〰️〰️〰️〰️ 🪝 〰️〰️",
    "〰️〰️ 🪝 〰️〰️〰️〰️",
]

FISH_FRAMES = [
    ("🎣 **You trying to Fish...**",         "🌊 Your Rod hitting the water.",              1),
    ("〰️ **Saw Azure Squirting...**",         BOBBER_FRAMES[0],                           3),
    ("〰️ **Still Squrting ...**",             BOBBER_FRAMES[2],                           4),
    ("⚡ **Something's on your hook!**",     "🎣 You shook your hook — SAW SOMETHING!",        5),
]


class Fish(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="fish")
    async def fish(self, ctx):

        create_account(ctx.author.id)

        user_data = economy_collection.find_one({
            "user_id": str(ctx.author.id)
        })

        last_fish = user_data.get("last_fish", 0)
        current_time = int(datetime.now(IST).timestamp())

        # ─── COOLDOWN ───
        if current_time - last_fish < FISH_COOLDOWN:
            remaining = FISH_COOLDOWN - (current_time - last_fish)
            next_time = current_time + remaining
            embed = discord.Embed(
                description=(
                    "❌ Fishing cooldown active.\n\n"
                    f"⏰ Try again <t:{next_time}:R>"
                ),
                color=0xED4245
            )
            await ctx.send(embed=embed)
            return

        # ─── SAVE TIME ───
        economy_collection.update_one(
            {"user_id": str(ctx.author.id)},
            {"$set": {"last_fish": current_time}}
        )

        # ─── DETERMINE OUTCOME NOW ───
        robbed = random.randint(1, 100) <= 10

        roll = random.randint(1, 100)
        current = 0
        selected_item = FISHING_ITEMS[0]
        for item in FISHING_ITEMS:
            current += item["chance"]
            if roll <= current:
                selected_item = item
                break

        # ─── ANIMATION ───
        embed = discord.Embed(
            title="🎣 FISHING",
            description=(
                f"{FISH_FRAMES[0][0]}\n"
                f"{FISH_FRAMES[0][1]}\n\n"
                f"{progress_bar(FISH_FRAMES[0][2])}"
            ),
            color=0x3498DB
        )
        embed.set_footer(text="ECHLEON • Activity")
        msg = await ctx.send(embed=embed)

        # Animate bobber waiting frames
        for i, (title, subtitle, step) in enumerate(FISH_FRAMES[1:], 1):
            delay = 0.85 if i < 3 else 0.7
            await asyncio.sleep(delay)
            embed.description = (
                f"{title}\n"
                f"{subtitle}\n\n"
                f"{progress_bar(step)}"
            )
            # Flash yellow on the bite frame
            if i == 3:
                embed.color = 0xF1C40F
            try:
                await msg.edit(embed=embed)
            except:
                pass

        await asyncio.sleep(0.75)

        # ─── BAD EVENT ───
        if robbed:
            loss = 100000
            cash = get_cash(ctx.author.id)
            if cash < loss:
                loss = cash
            remove_cash(ctx.author.id, loss)

            embed = discord.Embed(
                title="🎣 STOLEN CATCH!",
                description=(
                    "You pulled something big...\n\n"
                    "**EMIEL** swam up and 🍇 your entire catch\n"
                    "before you could even see what it was."
                ),
                color=0xED4245
            )
            embed.add_field(
                name="💸 Lost",
                value=f"**{format_cash(loss)}**",
                inline=True
            )
            embed.set_footer(text="ECHLEON • Better luck next time!")
            await msg.edit(embed=embed)
            return

        # ─── SUCCESS ───
        add_cash(ctx.author.id, FISH_REWARD)

        # ─── FIX: atomic inventory update ───
        economy_collection.update_one(
            {"user_id": str(ctx.author.id)},
            {"$inc": {f"inventory.{selected_item['name']}": 1}}
        )

        rarity_label, rarity_color = get_rarity(selected_item["chance"])

        # ─── LEGENDARY EXTRA SUSPENSE ───
        if selected_item["chance"] <= 2:
            await asyncio.sleep(0.5)
            embed.description = "✨ **The water is glowing... what is this?!**\n\n`[██████████] 100%`"
            embed.color = 0xF1C40F
            try:
                await msg.edit(embed=embed)
            except:
                pass
            await asyncio.sleep(0.9)

        # ─── RESULT ───
        embed = discord.Embed(
            title="🎣 CATCH SUCCESS",
            color=rarity_color
        )
        embed.add_field(
            name="💰 Earned",
            value=f"**{format_cash(FISH_REWARD)}**",
            inline=True
        )
        embed.add_field(
            name=f"{selected_item['emoji']} Caught",
            value=f"**{selected_item['display']}**",
            inline=True
        )
        embed.add_field(
            name="✨ Rarity",
            value=rarity_label,
            inline=True
        )
        embed.set_footer(text=f"ECHLEON • Fish  •  Item value: {format_cash(selected_item['price'])}")

        await msg.edit(embed=embed)

        add_stats(ctx.author.id, total_fishes=1)
        await check_achievements(self.bot, ctx.author)


async def setup(bot):
    await bot.add_cog(Fish(bot))
    
