from pymongo import MongoClient
import os

MONGO_URI = os.getenv("MONGO_URI")

client = MongoClient(MONGO_URI)

db = client["royal_bot"]

stats_collection = db["player_stats"]


# ─────────────────────────
# CREATE PROFILE
# ─────────────────────────

def create_profile(user_id):

    user_id = str(user_id)

    user = stats_collection.find_one({
        "user_id": user_id
    })

    if user:

        return


    stats_collection.insert_one({

        "user_id": user_id,

        "wins": 0,
        "losses": 0,

        "total_won": 0,
        "total_lost": 0,

        "streak": 0,
        "best_streak": 0,

        # NEW PROFILE STATS

        "games_played": 0,
        "total_gambled": 0,
        "biggest_win": 0,

        "total_mines": 0,
        "total_fishes": 0,
        "total_hunts": 0,
        "total_jobs": 0
    })


# ─────────────────────────
# ADD STATS
# ─────────────────────────

def add_stats(user_id, **stats):

    create_profile(user_id)

    stats_collection.update_one(

        {
            "user_id": str(user_id)
        },

        {
            "$inc": stats
        }
    )


# ─────────────────────────
# BIGGEST WIN
# ─────────────────────────

def update_biggest_win(user_id, amount):

    create_profile(user_id)

    user = stats_collection.find_one({

        "user_id": str(user_id)

    })


    current = user.get(
        "biggest_win",
        0
    )


    if amount > current:

        stats_collection.update_one(

            {
                "user_id": str(user_id)
            },

            {
                "$set": {
                    "biggest_win": amount
                }
            }
        )


# ─────────────────────────
# WIN
# ─────────────────────────

def record_win(user_id, amount):

    create_profile(user_id)

    if amount is None:

        amount = 0


    user = stats_collection.find_one({
        "user_id": str(user_id)
    })


    streak = user.get(
        "streak",
        0
    ) + 1


    best = max(

        streak,

        user.get(
            "best_streak",
            0
        )

    )


    stats_collection.update_one(

        {
            "user_id": str(user_id)
        },

        {
            "$inc": {

                "wins": 1,

                "total_won": amount

            },

            "$set": {

                "streak": streak,

                "best_streak": best

            }
        }

    )


# ─────────────────────────
# LOSS
# ─────────────────────────

def record_loss(user_id, amount):

    create_profile(user_id)

    if amount is None:

        amount = 0


    stats_collection.update_one(

        {
            "user_id": str(user_id)
        },

        {
            "$inc": {

                "losses": 1,

                "total_lost": amount

            },

            "$set": {

                "streak": 0

            }
        }

    )


# ─────────────────────────
# PROFILE
# ─────────────────────────

def get_profile(user_id):

    create_profile(user_id)

    user = stats_collection.find_one({
        "user_id": str(user_id)
    })


    wins = user.get(
        "wins",
        0
    )

    losses = user.get(
        "losses",
        0
    )

    matches = wins + losses

    winrate = 0


    if matches > 0:

        winrate = round(
            (wins / matches) * 100,
            2
        )


    return {

        "wins": wins,

        "losses": losses,

        "matches": matches,

        "winrate": winrate,

        "total_won": user.get(
            "total_won",
            0
        ),

        "total_lost": user.get(
            "total_lost",
            0
        ),

        "streak": user.get(
            "streak",
            0
        ),

        "best_streak": user.get(
            "best_streak",
            0
        ),

        "games_played": user.get(
            "games_played",
            0
        ),

        "total_gambled": user.get(
            "total_gambled",
            0
        ),

        "biggest_win": user.get(
            "biggest_win",
            0
        ),

        "total_mines": user.get(
            "total_mines",
            0
        ),

        "total_fishes": user.get(
            "total_fishes",
            0
        ),

        "total_hunts": user.get(
            "total_hunts",
            0
        ),

        "total_jobs": user.get(
            "total_jobs",
            0
        )
    }
