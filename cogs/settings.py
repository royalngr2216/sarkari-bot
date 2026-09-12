import discord
from discord.ext import commands

from utils.branding import (
    get_server_name,
    get_user_name,
    set_server_name,
    set_user_name,
)


class Settings(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    # ─────────────────────────────────────────────────────────
    # .servername <name>
    # ─────────────────────────────────────────────────────────

    @commands.command(name="servername")
    @commands.has_guild_permissions(administrator=True)
    async def servername(self, ctx, *, name: str = None):

        if not name:
            current = get_server_name(ctx.guild.id)

            embed = discord.Embed(
                title="⚙️ Server Name",
                description=(
                    f"Current name: **{current}**\n\n"
                    f"Usage: `.servername <name>`"
                ),
                color=0x5865F2,
            )

            await ctx.send(embed=embed)
            return

        name = name.strip()

        if len(name) > 100:
            await ctx.send(
                "❌ Server name must be 100 characters or less."
            )
            return

        set_server_name(ctx.guild.id, name)

        embed = discord.Embed(
            title="✅ Server Name Updated",
            description=f"Server branding is now **{name}**.",
            color=0x57F287,
        )

        embed.set_footer(text=name)

        await ctx.send(embed=embed)

    # ─────────────────────────────────────────────────────────
    # .setuser <name>
    # ─────────────────────────────────────────────────────────

    @commands.command(name="setuser")
    @commands.has_guild_permissions(administrator=True)
    async def setuser(self, ctx, *, name: str = None):

        if not name:
            current = get_user_name(ctx.guild.id)

            embed = discord.Embed(
                title="⚙️ Character Name",
                description=(
                    f"Current character name: **{current}**\n\n"
                    f"Usage: `.setuser <name>`"
                ),
                color=0x5865F2,
            )

            await ctx.send(embed=embed)
            return

        name = name.strip()

        if len(name) > 50:
            await ctx.send(
                "❌ Character name must be 50 characters or less."
            )
            return

        set_user_name(ctx.guild.id, name)

        embed = discord.Embed(
            title="✅ Character Name Updated",
            description=f"The character is now called **{name}**.",
            color=0x57F287,
        )

        embed.set_footer(
            text=f"{get_server_name(ctx.guild.id)}  •  {name}"
        )

        await ctx.send(embed=embed)

    # ─────────────────────────────────────────────────────────
    # ERROR HANDLER
    # ─────────────────────────────────────────────────────────

    @servername.error
    @setuser.error
    async def settings_error(self, ctx, error):

        if isinstance(error, commands.MissingPermissions):
            await ctx.send(
                "❌ You need **Administrator** permission to change bot settings."
            )


async def setup(bot):
    await bot.add_cog(Settings(bot))
