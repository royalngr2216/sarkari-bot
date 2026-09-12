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

IST = pytz.timezone("Asia/Kolkata")

MINE_COOLDOWN = 10800
MINE_REWARD   = 150000

ORES = {
    "stone":       {"emoji": "🪨", "chance": 35},
    "iron":        {"emoji": "🔩", "chance": 25},
    "gold":        {"emoji": "⚜️",  "chance": 18},
    "diamond":     {"emoji": "💎", "chance": 10},
    "emerald":     {"emoji": "🔮", "chance":  7},
    "ruby":        {"emoji": "♦️",  "chance":  4},
    "void_crystal":{"emoji": "🌌", "chance":  1},
}


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


class Mine(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="mine")
    async def mine(self, ctx):

        create_account(ctx.author.id)

        user_data = economy_collection.find_one({
            "user_id": str(ctx.author.id)
        })

        # ─── SHOVEL CHECK ───
        if not user_data.get("shovel", False):
            embed = discord.Embed(
                description=(
                    "❌ You need a **Shovel** to use `.mine`\n\n"
                    "Buy one from `.shop`"
                ),
                color=0xED4245
            )
            await ctx.send(embed=embed)
            return

        # ─── COOLDOWN ───
        last_mine = user_data.get("last_mine", 0)
        current_time = int(datetime.now(IST).timestamp())

        if current_time - last_mine < MINE_COOLDOWN:
            remaining = MINE_COOLDOWN - (current_time - last_mine)
            next_time = current_time + remaining
            embed = discord.Embed(
                description=(
                    "❌ Mining cooldown active.\n\n"
                    f"⏰ Try again <t:{next_time}:R>"
                ),
                color=0xED4245
            )
            await ctx.send(embed=embed)
            return

        # ─── SAVE COOLDOWN ───
        economy_collection.update_one(
            {"user_id": str(ctx.author.id)},
            {"$set": {"last_mine": current_time}}
        )

        # ─── DETERMINE OUTCOME NOW ───
        risk_roll = random.randint(1, 100)

        roll = random.randint(1, 100)
        current = 0
        selected_ore = "stone"
        for ore, data in ORES.items():
            current += data["chance"]
            if roll <= current:
                selected_ore = ore
                break

        ore_data = ORES[selected_ore]

        # ─── DRILL ANIMATION ───
        depth = random.randint(38, 72)

        drill_frames = [
            ("⛏️ **Descending into the mine...**",      "🪨 The entrance grows dark behind you.",    1),
            (f"💥 **Drilling... Depth: {depth}m**",       "🔦 Your lantern flickers in the shaft.",    3),
            ("🌋 **Something's down here...**",            "👂 You hear a cracking sound.",             4),
            ("✨ **Struck something!**",                   "🤲 You dig it free with your hands...",     5),
        ]

        embed = discord.Embed(
            title="⛏️ MINING",
            description=(
                f"{drill_frames[0][0]}\n"
                f"{drill_frames[0][1]}\n\n"
                f"{progress_bar(drill_frames[0][2])}"
            ),
            color=0xE67E22
        )
        embed.set_footer(text="ECHLEON • Activity")
        msg = await ctx.send(embed=embed)

        for i, (title, subtitle, step) in enumerate(drill_frames[1:], 1):
            await asyncio.sleep(0.8)
            embed.description = (
                f"{title}\n"
                f"{subtitle}\n\n"
                f"{progress_bar(step)}"
            )
            if i == 3:
                embed.color = 0xF1C40F  # flash gold when "struck"
            try:
                await msg.edit(embed=embed)
            except:
                pass

        await asyncio.sleep(0.75)

        # ─────────────────────────
        # EVENTS
        # ─────────────────────────

        # ─── CAVE COLLAPSE ───
        if risk_roll <= 5:
            loss = random.randint(50000, 150000)
            cash = get_cash(ctx.author.id)
            if loss > cash:
                loss = cash
            remove_cash(ctx.author.id, loss)

            embed = discord.Embed(
                title="⛰️ CAVE COLLAPSE",
                description=(
                    "**CRACK — the ceiling gives way!**\n\n"
                    "Rocks rain down around you.\n"
                    "You sprint for the exit, barely making it out alive.\n\n"
                    "Your tools and pocket change scatter everywhere."
                ),
                color=0xED4245
            )
            embed.add_field(name="💸 Lost while fleeing", value=f"**{format_cash(loss)}**", inline=True)
            embed.set_footer(text="ECHLEON • You survived... barely.")
            await msg.edit(embed=embed)
            return

        # ─── LAVA DISASTER ───
        if risk_roll <= 10:
            add_cash(ctx.author.id, MINE_REWARD)
            embed = discord.Embed(
                title="🌋 LAVA SURGE",
                description=(
                    "You found a rich vein of ore...\n\n"
                    "Then lava burst through the wall and\n"
                    "swallowed everything. You ran.\n\n"
                    "At least you grabbed your cash first."
                ),
                color=0xE67E22
            )
            embed.add_field(name="💰 Escaped with", value=f"**{format_cash(MINE_REWARD)}**", inline=True)
            embed.set_footer(text="ECHLEON • Could've been worse.")
            await msg.edit(embed=embed)
            return

        # ─── ANCIENT MINER ───
        if risk_roll <= 15:
            embed = discord.Embed(
                title="👴 THE ANCIENT MINER",
                description=(
                    "A shadowy figure steps out from the darkness.\n\n"
                    "**\"These mines have belonged to me for 300 years.\"**\n\n"
                    "Before you could react, he vanished —\n"
                    "along with everything you found."
                ),
                color=0xED4245
            )
            embed.set_footer(text="ECHLEON • Some forces are beyond your control.")
            await msg.edit(embed=embed)
            return

        # ─── NORMAL SUCCESS ───
        add_cash(ctx.author.id, MINE_REWARD)

        # FIX: atomic inventory update
        economy_collection.update_one(
            {"user_id": str(ctx.author.id)},
            {"$inc": {f"inventory.{selected_ore}": 1}}
        )

        rarity_label, rarity_color = get_rarity(ore_data["chance"])

        # LEGENDARY EXTRA SUSPENSE
        if ore_data["chance"] <= 2:
            await asyncio.sleep(0.5)
            embed.description = "🌌 **The ore is pulsating with unknown energy...**\n\n`[██████████] 100%`"
            embed.color = 0xF1C40F
            try:
                await msg.edit(embed=embed)
            except:
                pass
            await asyncio.sleep(1.0)

        ore_display = selected_ore.replace("_", " ").title()

        embed = discord.Embed(
            title="⛏️ MINING SUCCESS",
            color=rarity_color
        )
        embed.add_field(
            name="💰 Earned",
            value=f"**{format_cash(MINE_REWARD)}**",
            inline=True
        )
        embed.add_field(
            name=f"{ore_data['emoji']} Found",
            value=f"**{ore_display}**",
            inline=True
        )
        embed.add_field(
            name="✨ Rarity",
            value=rarity_label,
            inline=True
        )
        from utils.items import MINING_ITEMS
        ore_price = next((i["price"] for i in MINING_ITEMS if i["name"] == selected_ore), 0)
        embed.set_footer(text=f"ECHLEON • Mine  •  Ore value: {format_cash(ore_price)}")

        await msg.edit(embed=embed)

        add_stats(ctx.author.id, total_mines=1)
        await check_achievements(self.bot, ctx.author)


async def setup(bot):
    await bot.add_cog(Mine(bot))
    
