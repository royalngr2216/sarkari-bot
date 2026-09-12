from discord.ext import commands
import discord
import random
import asyncio
from datetime import datetime
import pytz

from utils.economy import (
    create_account,
    get_cash,
    add_cash,
    remove_cash,
    format_cash,
    economy_collection
)

IST = pytz.timezone("Asia/Kolkata")


# ─────────────────────────
# HEIST FRAMES
# ─────────────────────────

HEIST_FRAMES = [
    ("🕵️ **Casing the target...**",    "👀 You watch their movements from the shadows.",   0x95A5A6),
    ("🔓 **Picking the lock...**",      "🤫 One click... two clicks...",                   0xE67E22),
    ("💨 **Making the move...**",       "🏃 You slip inside. No turning back now.",         0x5865F2),
]


class Rob(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="rob")
    async def rob(self, ctx, member: discord.Member = None):

        # ─── VALIDATION ───

        if member is None:
            await ctx.send(embed=discord.Embed(
                description="❌ Mention someone to rob.",
                color=0xED4245
            ))
            return

        if member.id == ctx.author.id:
            await ctx.send(embed=discord.Embed(
                description="❌ You cannot rob yourself.",
                color=0xED4245
            ))
            return

        if member.bot:
            await ctx.send(embed=discord.Embed(
                description="❌ You cannot rob bots.",
                color=0xED4245
            ))
            return

        create_account(ctx.author.id)
        create_account(member.id)

        robber_cash = get_cash(ctx.author.id)
        victim_cash = get_cash(member.id)

        # ─── PADLOCK CHECK ───
        victim_data = economy_collection.find_one({"user_id": str(member.id)})
        padlock_until = victim_data.get("padlock_until", 0)
        current_time = int(datetime.now().timestamp())

        if padlock_until > current_time:
            remaining = padlock_until - current_time
            days  = remaining // 86400
            hours = (remaining % 86400) // 3600
            await ctx.send(embed=discord.Embed(
                title="🛡️ PADLOCK ACTIVE",
                description=(
                    f"{member.mention} is shielded from robbery.\n\n"
                    f"⏰ Protection remaining: **{days}d {hours}h**"
                ),
                color=0x5865F2
            ))
            return

        # ─── ROB LIMIT ───
        user_data = economy_collection.find_one({"user_id": str(ctx.author.id)})
        rob_uses  = user_data.get("rob_uses", 0)
        rob_reset = user_data.get("rob_reset", 0)
        current_time_ist = int(datetime.now(IST).timestamp())

        if current_time_ist - rob_reset >= 43200:
            rob_uses  = 0
            rob_reset = current_time_ist
            economy_collection.update_one(
                {"user_id": str(ctx.author.id)},
                {"$set": {"rob_uses": 0, "rob_reset": current_time_ist}}
            )

        max_robs = 20 if user_data.get("lock_and_key") else 10

        if rob_uses >= max_robs:
            next_reset = rob_reset + 43200
            await ctx.send(embed=discord.Embed(
                description=(
                    f"❌ You used all {max_robs} rob attempts.\n\n"
                    f"⏰ Reset <t:{next_reset}:R>\n"
                    f"📅 <t:{next_reset}:F>"
                ),
                color=0xED4245
            ))
            return

        # ─── TOO RICH ───
        if robber_cash > 200000:
            await ctx.send(embed=discord.Embed(
                description=(
                    "❌ You are too rich to rob people.\n\n"
                    "Rob is only for users under **200K NGR**."
                ),
                color=0xED4245
            ))
            return

        # ─── VICTIM TOO BROKE ───
        if victim_cash < 100:
            await ctx.send(embed=discord.Embed(
                description="❌ That user is too broke to rob.",
                color=0xED4245
            ))
            return

        # ─── CHARGE ROB USE ───
        economy_collection.update_one(
            {"user_id": str(ctx.author.id)},
            {"$inc": {"rob_uses": 1}, "$set": {"rob_reset": rob_reset}}
        )

        attempts_left = max_robs - (rob_uses + 1)

        # ─────────────────────────
        # HEIST ANIMATION
        # ─────────────────────────

        embed = discord.Embed(
            title=f"🕵️ HEIST — {member.name.upper()}",
            description=(
                f"{HEIST_FRAMES[0][0]}\n"
                f"{HEIST_FRAMES[0][1]}"
            ),
            color=HEIST_FRAMES[0][2]
        )
        embed.set_footer(text=f"ECHLEON  •  Attempts left: {attempts_left}/{max_robs}")
        msg = await ctx.send(embed=embed)

        for title, subtitle, color in HEIST_FRAMES[1:]:
            await asyncio.sleep(0.85)
            embed.description = f"{title}\n{subtitle}"
            embed.color = color
            try:
                await msg.edit(embed=embed)
            except:
                pass

        await asyncio.sleep(0.9)

        # ─────────────────────────
        # OUTCOME
        # ─────────────────────────

        success = random.randint(1, 100) <= 40

        if success:
            stolen = max(1, int(victim_cash * 0.05))
            remove_cash(member.id,        stolen)
            add_cash(ctx.author.id,       stolen)

            embed = discord.Embed(
                title="🦹 HEIST SUCCESSFUL",
                description=(
                    f"You slipped in, grabbed what you could,\n"
                    f"and vanished before {member.mention} noticed."
                ),
                color=0x57F287
            )
            embed.add_field(name="💰 Stolen",               value=f"**{format_cash(stolen)}**",            inline=True)
            embed.add_field(name="📊 Attempts remaining",   value=f"**{attempts_left} / {max_robs}**",     inline=True)
            embed.set_footer(text=f"Victim balance: {format_cash(victim_cash - stolen)} NGR remaining")

        else:
            loss = max(1, int(robber_cash * 0.50))
            remove_cash(ctx.author.id,  loss)
            add_cash(member.id,         loss)

            embed = discord.Embed(
                title="🚔 CAUGHT IN THE ACT",
                description=(
                    f"You tripped an alarm and got pinned down.\n"
                    f"{member.mention} called the guards — you paid the price."
                ),
                color=0xED4245
            )
            embed.add_field(name="💸 Fine paid",             value=f"**{format_cash(loss)}**",              inline=True)
            embed.add_field(name="📊 Attempts remaining",    value=f"**{attempts_left} / {max_robs}**",     inline=True)
            embed.set_footer(text="Plan better next time.")

        await msg.edit(embed=embed)


async def setup(bot):
    await bot.add_cog(Rob(bot))
    
