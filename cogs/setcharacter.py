from discord.ext import commands
import discord

from utils.pokemon_db import (
    get_character_name,
    set_character_name,
    DEFAULT_CHARACTER_NAME,
)


class SetCharacter(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="setcharacter")
    @commands.has_permissions(manage_guild=True)
    async def setcharacter(self, ctx, *, name: str = None):
        """Rename the character who steals catches, fish, and donations."""

        current = get_character_name(ctx.guild.id)

        if not name:
            embed = discord.Embed(
                description=(
                    f"Current name: **{current}**\n\n"
                    "**Usage:** `.setcharacter <name>`\n"
                    "**Example:** `.setcharacter Neel`"
                ),
                color=0xED4245,
            )
            await ctx.send(embed=embed)
            return

        name = name.strip()

        if len(name) > 32:
            await ctx.send(embed=discord.Embed(
                description="❌ Name must be 32 characters or fewer.",
                color=0xED4245,
            ))
            return

        set_character_name(ctx.guild.id, name)

        embed = discord.Embed(
            title="✅ CHARACTER RENAMED",
            description=(
                f"**{current}** is now **{name}**.\n\n"
                f"{name} will now show up in `.diddy`, catches, "
                f"`.fish`, `.mines`, `.slots`, and `.donate`."
            ),
            color=0x57F287,
        )
        await ctx.send(embed=embed)

    @setcharacter.error
    async def setcharacter_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(embed=discord.Embed(
                description="❌ Only server admins (Manage Server) can change this.",
                color=0xED4245,
            ))


async def setup(bot):
    await bot.add_cog(SetCharacter(bot))
