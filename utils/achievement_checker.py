import discord

from utils.achievements import (
    COMMON_ACHIEVEMENTS,
    RARE_ACHIEVEMENTS,
    LEGENDARY_ACHIEVEMENTS
)

from utils.stats import get_profile

from utils.economy import (
    economy_collection,
    add_cash,
    format_cash
)

from utils.items import ALL_ITEMS

from utils.workers import (
    WORKER_VALUES
)


# ─────────────────────────
# ALL ACHIEVEMENTS
# ─────────────────────────

ALL_ACHIEVEMENTS = {

    **COMMON_ACHIEVEMENTS,

    **RARE_ACHIEVEMENTS,

    **LEGENDARY_ACHIEVEMENTS
}


# ─────────────────────────
# CHECK ACHIEVEMENTS
# ─────────────────────────

async def check_achievements(bot, user):

    user_data = economy_collection.find_one({

        "user_id": str(user.id)

    })

    if not user_data:

        return


    stats = get_profile(user.id)

    claimed = user_data.get(
        "claimed_achievements",
        []
    )


    # ─────────────────────────
    # LOOP
    # ─────────────────────────

    for achievement_id, achievement in ALL_ACHIEVEMENTS.items():

        # already claimed

        if achievement_id in claimed:

            continue


        achievement_type = achievement["type"]

        required = achievement["required"]


        # ─────────────────────────
        # CURRENT VALUE
        # ─────────────────────────

        if achievement_type == "workers_owned":

            current = len(
                user_data.get(
                    "workers",
                    {}
                )
            )


        elif achievement_type == "inventory_value":

            inventory = user_data.get(
                "inventory",
                {}
            )

            current = 0

            for item_name, amount in inventory.items():

                if item_name in ALL_ITEMS:

                    current += (

                        ALL_ITEMS[item_name]["price"]

                        * amount
                    )


        elif achievement_type == "networth":

            inventory = user_data.get(
                "inventory",
                {}
            )

            inventory_value = 0

            for item_name, amount in inventory.items():

                if item_name in ALL_ITEMS:

                    inventory_value += (

                        ALL_ITEMS[item_name]["price"]

                        * amount
                    )

            cash = user_data.get(
                "cash",
                0
            )

            workers = user_data.get(
                "workers",
                {}
            )

            workers_value = 0

            for worker in workers.values():

                level = worker.get(
                    "level",
                    1
                )

                workers_value += (
                    WORKER_VALUES[level]
                )

            current = (

                cash

                + inventory_value

                + workers_value
            )

        else:

            current = stats.get(
                achievement_type,
                0
            )


        # ─────────────────────────
        # NOT COMPLETE
        # ─────────────────────────

        if current < required:

            continue


        # ─────────────────────────
        # SAVE CLAIM
        # ─────────────────────────

        economy_collection.update_one(

            {
                "user_id": str(user.id)
            },

            {
                "$push": {

                    "claimed_achievements": achievement_id
                }
            }
        )


        # ─────────────────────────
        # REWARD
        # ─────────────────────────

        reward = achievement["reward"]

        reward_text = ""


        if isinstance(reward, int):

            add_cash(
                user.id,
                reward
            )

            reward_text = (
                f"💰 {format_cash(reward)}"
            )

        else:

            if reward not in user_data.get("pets", []):

                economy_collection.update_one(

                    {
                        "user_id": str(user.id)
                    },

                    {
                        "$push": {

                            "pets": reward
                        }
                    }
                )

            reward_text = (
                f"🐾 {reward.replace('_', ' ').title()}"
            )


        # ─────────────────────────
        # RARITY COLOR
        # ─────────────────────────

        rarity = achievement["rarity"]

        if rarity == "common":

            color = 0x95A5A6

        elif rarity == "rare":

            color = 0x9B59B6

        else:

            color = 0xF1C40F


        # ─────────────────────────
        # EMBED
        # ─────────────────────────

        embed = discord.Embed(

            title="🏆 ACHIEVEMENT COMPLETED",

            description=(

                f"{user.mention}\n\n"

                f"## {achievement['name']}\n"

                f"{achievement['description']}\n\n"

                f"🎁 Reward:\n"
                f"{reward_text}"

            ),

            color=color
        )


        embed.add_field(

            name="Rarity",

            value=rarity.title(),

            inline=True
        )


        embed.set_thumbnail(
            url=user.display_avatar.url
        )


        # ─────────────────────────
        # SEND
        # ─────────────────────────

        channel = bot.get_channel(
            710894803721912350
        )

        try:

            if channel:

                await channel.send(
                    embed=embed
                )

            else:

                print(
                    "Achievement channel not found."
                )

        except Exception as e:

            print(
                f"Achievement send error: {e}"
            )
