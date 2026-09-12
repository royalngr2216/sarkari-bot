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
from utils.stats import add_stats, update_biggest_win
from utils.achievement_checker import check_achievements
from utils.items import HUNTING_ITEMS

IST = pytz.timezone("Asia/Kolkata")

HUNT_COOLDOWN = 1800
HUNT_REWARD = 50000


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


# ─────────────────────────
# HUNT ANIMATION FRAMES
# ─────────────────────────

HUNT_FRAMES = [
    ("🌲 **Entering Deep Forest...**",      "👣 You step into the wilderness.",         1),
    ("👣 **Saw some dikprints...**",       "🔍 You followed dikprint trail deeper in.",         3),
    ("🏔️ **Deep in the wild...**",         "🌿 The air felt different. Something nearby.", 4),
    ("🎯 **You spot something!**",              "🏹 You draw your bow...",                  5),
]


class Hunt(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="hunt")
    async def hunt(self, ctx):

        create_account(ctx.author.id)

        user_data = economy_collection.find_one({
            "user_id": str(ctx.author.id)
        })

        last_hunt = user_data.get("last_hunt", 0)
        current_time = int(datetime.now(IST).timestamp())

        # ─── COOLDOWN ───
        if current_time - last_hunt < HUNT_COOLDOWN:
            remaining = HUNT_COOLDOWN - (current_time - last_hunt)
            next_time = current_time + remaining
            embed = discord.Embed(
                description=(
                    "❌ Hunting cooldown active.\n\n"
                    f"⏰ Try again <t:{next_time}:R>"
                ),
                color=0xED4245
            )
            await ctx.send(embed=embed)
            return

        # ─── SAVE TIME ───
        economy_collection.update_one(
            {"user_id": str(ctx.author.id)},
            {"$set": {"last_hunt": current_time}}
        )

        # ─── DETERMINE OUTCOME NOW (before animation) ───
        robbed = random.randint(1, 100) <= 15

        roll = random.randint(1, 100)
        current = 0
        selected_item = HUNTING_ITEMS[0]
        for item in HUNTING_ITEMS:
            current += item["chance"]
            if roll <= current:
                selected_item = item
                break

        # ─── ANIMATION ───
        embed = discord.Embed(
            title="🏹 HUNTING",
            description=(
                f"{HUNT_FRAMES[0][0]}\n"
                f"{HUNT_FRAMES[0][1]}\n\n"
                f"{progress_bar(HUNT_FRAMES[0][2])}"
            ),
            color=0x2ECC71
        )
        embed.set_footer(text="ECHLEON • Activity")
        msg = await ctx.send(embed=embed)

        for i, (title, subtitle, step) in enumerate(HUNT_FRAMES[1:], 1):
            await asyncio.sleep(0.75)
            embed.description = (
                f"{title}\n"
                f"{subtitle}\n\n"
                f"{progress_bar(step)}"
            )
            try:
                await msg.edit(embed=embed)
            except:
                pass

        await asyncio.sleep(0.85)

        # ─── BAD EVENT ───
        if robbed:
            loss = 100000
            cash = get_cash(ctx.author.id)
            if cash < loss:
                loss = cash
            remove_cash(ctx.author.id, loss)

            embed = discord.Embed(
                title="🏹 AMBUSHED!",
                description=(
                    "You were deep in the forest when...\n\n"
                    "**Royal NGR** jumped out from the bushes\n"
                    "and 🍇 you in a cave before you could react <:bj:1492588515253551144>  !"
                ),
                color=0xED4245
            )
            embed.add_field(
                name="💸 Lost",
                value=f"**{format_cash(loss)}**",
                inline=True
            )
            embed.set_footer(text="Better luck next hunt!")
            await msg.edit(embed=embed)
            return

        # ─── SUCCESS ───
        add_cash(ctx.author.id, HUNT_REWARD)

        # ─── FIX: atomic inventory update ───
        economy_collection.update_one(
            {"user_id": str(ctx.author.id)},
            {"$inc": {f"inventory.{selected_item['name']}": 1}}
        )

        rarity_label, rarity_color = get_rarity(selected_item["chance"])

        # ─── LEGENDARY EXTRA SUSPENSE ───
        if selected_item["chance"] <= 2:
            await asyncio.sleep(0.5)
            embed.description = "✨ **Something rare is glowing...**\n\n`[██████████] 100%`"
            embed.color = 0xF1C40F
            try:
                await msg.edit(embed=embed)
            except:
                pass
            await asyncio.sleep(0.8)

        # ─── RESULT EMBED ───
        embed = discord.Embed(
            title="🏹 HUNT SUCCESS",
            color=rarity_color
        )
        embed.add_field(
            name="💰 Earned",
            value=f"**{format_cash(HUNT_REWARD)}**",
            inline=True
        )
        embed.add_field(
            name=f"{selected_item['emoji']} Found",
            value=f"**{selected_item['display']}**",
            inline=True
        )
        embed.add_field(
            name="✨ Rarity",
            value=rarity_label,
            inline=True
        )
        embed.set_footer(text=f"ECHLEON • Hunt  •  Item value: {format_cash(selected_item['price'])}")

        await msg.edit(embed=embed)

        add_stats(ctx.author.id, total_hunts=1)
        await check_achievements(self.bot, ctx.author)


async def setup(bot):
    await bot.add_cog(Hunt(bot))
    
