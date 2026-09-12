import os
from pymongo import MongoClient
from datetime import datetime, timedelta
import pytz

MONGO_URI = os.getenv("MONGO_URI")

# ─────────────────────────
# ECONOMY BALANCE CAPS
# ─────────────────────────
# Shared max bet for every player-vs-house gambling command
# (slots, coinflip, crash, mines, blackjack, highlow, guessnumber).
# Prevents any single spin/round from injecting huge amounts of new
# money into the economy. PvP games (deathroll, crack) aren't capped
# here since money there just moves between two players, it isn't created.
MAX_BET = 1_000_000_000

client = MongoClient(MONGO_URI)

db = client["royal_bot"]

economy_collection = db["economy"]

IST = pytz.timezone("Asia/Kolkata")


# ─────────────────────────
# ACCOUNT
# ─────────────────────────

def create_account(user_id):

    user = economy_collection.find_one({
        "user_id": str(user_id)
    })

    if not user:

        economy_collection.insert_one({

            "user_id": str(user_id),

            "cash": 0,

            "daily": 0,
            "weekly": 0,
            "monthly": 0,
            "give_sent_today": 0,
            "give_reset": 0,

            "padlock_until": 0,

            "rob_uses": 0,
            "rob_reset": 0,

            "workers": {},
            "inventory": {},
            "claimed_achievements": [],
            "pets": []

        })


# ─────────────────────────
# CASH
# ─────────────────────────

def get_cash(user_id):

    user = economy_collection.find_one({
        "user_id": str(user_id)
    })

    if not user:

        create_account(user_id)

        return 0

    return user.get("cash", 0)


def add_cash(user_id, amount):

    economy_collection.update_one(

        {
            "user_id": str(user_id)
        },

        {
            "$inc": {
                "cash": amount
            }
        }

    )


def remove_cash(user_id, amount):

    economy_collection.update_one(

        {
            "user_id": str(user_id)
        },

        {
            "$inc": {
                "cash": -amount
            }
        }

    )


# ─────────────────────────
# FORMAT
# ─────────────────────────

def format_cash(amount):

    if amount >= 1_000_000_000:
        return f"{amount/1_000_000_000:.1f}B NGR"

    if amount >= 1_000_000:
        return f"{amount/1_000_000:.1f}M NGR"

    if amount >= 1_000:
        return f"{amount/1_000:.1f}K NGR"

    return f"{amount} NGR"


# ─────────────────────────
# DAILY
# ─────────────────────────

def can_claim_daily(user_id):

    user = economy_collection.find_one({
        "user_id": str(user_id)
    })

    if not user:
        return True

    last = user.get("daily", 0)

    if last == 0:
        return True

    now = datetime.now(IST)

    reset = now.replace(
        hour=5,
        minute=30,
        second=0,
        microsecond=0
    )

    if now < reset:
        reset -= timedelta(days=1)

    return datetime.fromtimestamp(last, IST) < reset


def get_daily_reset():

    now = datetime.now(IST)

    reset = now.replace(
        hour=5,
        minute=30,
        second=0,
        microsecond=0
    )

    if now >= reset:
        reset += timedelta(days=1)

    return int(reset.timestamp())


def update_daily(user_id):

    economy_collection.update_one(

        {
            "user_id": str(user_id)
        },

        {
            "$set": {
                "daily": datetime.now().timestamp()
            }
        }

    )


# ─────────────────────────
# WEEKLY
# ─────────────────────────

def can_claim_weekly(user_id):

    user = economy_collection.find_one({
        "user_id": str(user_id)
    })

    if not user:
        return True

    last = user.get("weekly", 0)

    if last == 0:
        return True

    now = datetime.now(IST)

    current_week = (now.day - 1) // 7

    last_time = datetime.fromtimestamp(last, IST)

    last_week = (last_time.day - 1) // 7

    return (
        now.month != last_time.month
        or current_week != last_week
    )


def get_weekly_reset():

    now = datetime.now(IST)

    if now.day <= 7:
        target_day = 8

    elif now.day <= 14:
        target_day = 15

    elif now.day <= 21:
        target_day = 22

    else:

        target_day = 1

        if now.month == 12:

            return int(datetime(
                now.year + 1,
                1,
                1,
                5,
                30,
                tzinfo=IST
            ).timestamp())

        return int(datetime(
            now.year,
            now.month + 1,
            1,
            5,
            30,
            tzinfo=IST
        ).timestamp())

    return int(datetime(
        now.year,
        now.month,
        target_day,
        5,
        30,
        tzinfo=IST
    ).timestamp())


def update_weekly(user_id):

    economy_collection.update_one(

        {
            "user_id": str(user_id)
        },

        {
            "$set": {
                "weekly": datetime.now().timestamp()
            }
        }

    )


# ─────────────────────────
# MONTHLY
# ─────────────────────────

def can_claim_monthly(user_id):

    user = economy_collection.find_one({
        "user_id": str(user_id)
    })

    if not user:
        return True

    last = user.get("monthly", 0)

    if last == 0:
        return True

    last_time = datetime.fromtimestamp(last, IST)

    now = datetime.now(IST)

    return (
        now.month != last_time.month
        or now.year != last_time.year
    )


def get_monthly_reset():

    now = datetime.now(IST)

    if now.month == 12:

        reset = datetime(
            now.year + 1,
            1,
            1,
            5,
            30,
            tzinfo=IST
        )

    else:

        reset = datetime(
            now.year,
            now.month + 1,
            1,
            5,
            30,
            tzinfo=IST
        )

    return int(reset.timestamp())


def update_monthly(user_id):

    economy_collection.update_one(

        {
            "user_id": str(user_id)
        },

        {
            "$set": {
                "monthly": datetime.now().timestamp()
            }
        }

    )


# ─────────────────────────
# PARSE AMOUNT
# ─────────────────────────

def parse_amount(amount, balance=None):

    amount = str(amount).lower()

    if amount == "all":

        if balance is None:
            return None

        return balance

    try:

        if amount.endswith("k"):
            return int(float(amount[:-1]) * 1000)

        if amount.endswith("m"):
            return int(float(amount[:-1]) * 1_000_000)

        return int(amount)

    except:

        return None
