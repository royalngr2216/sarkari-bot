from discord.ext import commands
import discord

from utils.economy import economy_collection, format_cash
from utils.titles import get_equipped
from utils.leaderboard_render import render_leaderboard


class Leaderboard(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def _user_data(self, user_id):
        try:
            user = self.bot.get_user(int(user_id))
            if user is None:
                user = await self.bot.fetch_user(int(user_id))

            return {
                "user_id": str(user_id),
                "name": user.display_name,
                "avatar_url": user.display_avatar.replace(size=128).url,
                "title_key": get_equipped(int(user_id)),
            }
        except Exception:
            return {
                "user_id": str(user_id),
                "name": f"User {user_id}",
                "avatar_url": "https://cdn.discordapp.com/embed/avatars/0.png",
                "title_key": get_equipped(int(user_id)),
            }

    @commands.command(name="leaderboard", aliases=["lb", "top"])
    async def leaderboard(self, ctx):
        """Show the richest players in the economy."""
        cursor = economy_collection.find(
            {"cash": {"$gt": 0}},
            {"user_id": 1, "cash": 1, "_id": 0},
        ).sort("cash", -1).limit(10)

        rows = list(cursor)
        top_entries = []

        for rank, row in enumerate(rows, start=1):
            data = await self._user_data(row["user_id"])
            data.update({
                "rank": rank,
                "cash": row.get("cash", 0),
            })
            top_entries.append(data)

        requester_entry = None
        requester_id = str(ctx.author.id)
        requester = economy_collection.find_one(
            {"user_id": requester_id},
            {"cash": 1, "_id": 0},
        )

        if requester and requester.get("cash", 0) > 0:
            requester_cash = requester.get("cash", 0)
            requester_rank = economy_collection.count_documents(
                {"cash": {"$gt": requester_cash}}
            ) + 1

            if requester_rank > 10:
                data = await self._user_data(requester_id)
                requester_entry = {
                    **data,
                    "rank": requester_rank,
                    "cash": requester_cash,
                }

        if not top_entries:
            await ctx.send("💸 No players have any NGR yet.")
            return

        async with ctx.typing():
            image = await render_leaderboard(
                top_entries,
                requester_entry,
                format_cash,
            )

        await ctx.send(
            file=discord.File(image, filename="leaderboard.png")
        )


async def setup(bot):
    await bot.add_cog(Leaderboard(bot))
