import re
import discord
from discord import app_commands
from discord.ext import commands

EMOJI_RE = re.compile(r"<(a?):([a-zA-Z0-9_]{2,32}):(\d+)>")


class GuildSelect(discord.ui.Select):

    def __init__(self, cog, emoji_name, emoji_bytes, animated, guilds):

        self.cog = cog
        self.emoji_name = emoji_name
        self.emoji_bytes = emoji_bytes
        self.animated = animated

        options = [
            discord.SelectOption(
                label=g.name[:100],
                description=f"{g.member_count} members",
                value=str(g.id),
            )
            for g in guilds[:25]
        ]

        super().__init__(
            placeholder="Choose a server to steal this emoji into...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):

        guild = self.cog.bot.get_guild(int(self.values[0]))

        if guild is None:
            await interaction.response.edit_message(
                content="❌ That server isn't reachable anymore.",
                embed=None,
                view=None,
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            new_emoji = await guild.create_custom_emoji(
                name=self.emoji_name,
                image=self.emoji_bytes,
                reason=f"Stolen by {interaction.user} via /steal",
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ I don't have permission to manage emojis in that server anymore.",
                ephemeral=True,
            )
            return
        except discord.HTTPException as e:
            await interaction.followup.send(
                f"❌ Failed to add emoji: `{e.text if hasattr(e, 'text') else e}`\n"
                f"(likely the emoji slots for that server are full)",
                ephemeral=True,
            )
            return

        done_embed = discord.Embed(
            title="✅ Emoji Stolen",
            description=(
                f"Added {new_emoji} as **:{new_emoji.name}:** to **{guild.name}**."
            ),
            color=discord.Color.green(),
        )
        done_embed.set_thumbnail(url=new_emoji.url)

        await interaction.followup.send(embed=done_embed, ephemeral=True)

        target_channel = None

        if guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
            target_channel = guild.system_channel
        else:
            for ch in guild.text_channels:
                if ch.permissions_for(guild.me).send_messages:
                    target_channel = ch
                    break

        if target_channel is not None:
            public_embed = discord.Embed(
                description=f"🎉 **{interaction.user.mention} stole {new_emoji} successfully!**",
                color=discord.Color.gold(),
            )
            public_embed.set_thumbnail(url=new_emoji.url)

            try:
                await target_channel.send(embed=public_embed)
            except discord.Forbidden:
                pass


class GuildSelectView(discord.ui.View):

    def __init__(self, cog, emoji_name, emoji_bytes, animated, guilds):

        super().__init__(timeout=60)
        self.add_item(GuildSelect(cog, emoji_name, emoji_bytes, animated, guilds))


class Steal(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        # Ensures the slash command tree knows about this command.
        # Safe to call repeatedly — Discord dedupes on sync.
        try:
            synced = await self.bot.tree.sync()
            print(f"[steal.py] Synced {len(synced)} global command(s).")
        except Exception as e:
            print(f"[steal.py] Slash command sync FAILED: {e}")

    @commands.command(name="synccmds")
    @commands.is_owner()
    async def synccmds(self, ctx):
        """Manual fallback: run .synccmds (owner only) to force a resync
        and see any error directly in the channel."""
        try:
            synced = await self.bot.tree.sync()
            await ctx.send(f"✅ Synced {len(synced)} global command(s).")
        except Exception as e:
            await ctx.send(f"❌ Sync failed: `{e}`")

    @app_commands.command(
        name="steal",
        description="Steal a custom emoji and add it to a server you manage",
    )
    @app_commands.describe(emoji="Paste or pick the custom emoji you want to steal")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def steal(self, interaction: discord.Interaction, emoji: str):

        match = EMOJI_RE.search(emoji)

        if not match:
            await interaction.response.send_message(
                "❌ That's not a custom emoji I can steal — only server "
                "emojis (not default unicode emojis) can be stolen.",
                ephemeral=True,
            )
            return

        animated, name, emoji_id = match.groups()
        animated = bool(animated)
        ext = "gif" if animated else "png"
        url = f"https://cdn.discordapp.com/emojis/{emoji_id}.{ext}?size=512"

        async with self.bot.http._HTTPClient__session.get(url) as resp:
            if resp.status != 200:
                await interaction.response.send_message(
                    "❌ Couldn't download that emoji, it may have been deleted.",
                    ephemeral=True,
                )
                return
            emoji_bytes = await resp.read()

        eligible_guilds = []

        for guild in self.bot.guilds:
            member = guild.get_member(interaction.user.id)
            if member is None:
                continue
            perms = member.guild_permissions
            if not (perms.manage_expressions or perms.manage_emojis or perms.administrator):
                continue
            if not guild.me.guild_permissions.manage_expressions and not guild.me.guild_permissions.manage_emojis:
                continue
            eligible_guilds.append(guild)

        if not eligible_guilds:
            await interaction.response.send_message(
                "❌ I couldn't find any server where **both** you and I have "
                "Manage Emoji permissions. I can only add emojis to servers "
                "I'm actually a member of.",
                ephemeral=True,
            )
            return

        preview_embed = discord.Embed(
            title="🕵️ Steal Emoji",
            description=(
                f"Found **`:{name}:`**{' (animated)' if animated else ''}.\n"
                f"Pick which server to add it to below."
            ),
            color=discord.Color.blurple(),
        )
        preview_embed.set_thumbnail(url=url)
        preview_embed.set_footer(
            text=f"Eligible servers: {len(eligible_guilds)} (capped at 25)"
        )

        view = GuildSelectView(self, name, emoji_bytes, animated, eligible_guilds)

        await interaction.response.send_message(
            embed=preview_embed, view=view, ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(Steal(bot))
