from pymongo import MongoClient
from datetime import datetime
import os

MONGO_URI = os.getenv("MONGO_URI")

client = MongoClient(MONGO_URI)

db = client["royal_bot"]

lottery_collection = db["lottery"]


def get_lottery():

    lottery = lottery_collection.find_one(
        {"_id": "lottery"}
    )

    if not lottery:

        lottery = {

            "_id": "lottery",

            "participants": {},

            "next_draw": int(
                datetime.now().timestamp()
            ) + 21600
        }

        lottery_collection.insert_one(
            lottery
        )

    return lottery


def add_ticket(user_id, amount):

    lottery = get_lottery()

    participants = lottery.get(
        "participants",
        {}
    )

    participants[str(user_id)] = (

        participants.get(
            str(user_id),
            0
        )

        + amount
    )

    lottery_collection.update_one(

        {
            "_id": "lottery"
        },

        {
            "$set": {
                "participants": participants
            }
        }
    )


def get_total_pool():

    lottery = get_lottery()

    return sum(

        lottery.get(
            "participants",
            {}
        ).values()

    )


def reset_lottery():

    lottery_collection.update_one(

        {
            "_id": "lottery"
        },

        {
            "$set": {

                "participants": {},

                "next_draw": int(
                    datetime.now().timestamp()
                ) + 21600
            }
        }
    )
