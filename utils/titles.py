from utils.economy import economy_collection, get_cash, remove_cash, format_cash

# ─────────────────────────────────────────────────────────────────
# TITLES — a permanent, purely cosmetic money sink
# ─────────────────────────────────────────────────────────────────
# The economy previously had nowhere for big money to *go* except
# gambling (which is now negative-EV) or hoarding. Titles give rich
# players a reason to actually spend: a one-time, permanent badge
# that shows next to their name on .cash, .leaderboard, and .profile.
# Buying one destroys the cash spent — it's not paid to anyone, so
# it's a pure sink that drains the economy instead of recirculating it.

TITLES = {
    "i'm not into girls": {"label": "i'm not into girls", "price": 50_000_000,     "emoji": "🥉", "color": 0xCD7F32},
    "rapist": {"label": "Rapist", "price": 100_000_000,     "emoji": "🥈", "color": 0xB0B0B8},
    "azure fucker":  {"label": "Azure Fucker",  "price": 250_000_000,    "emoji": "🥇", "color": 0xFFD700},
    "madhav fucker":   {"label": "Madhav Fucker",   "price": 500_000_000,    "emoji": "💎", "color": 0x20D2D2},
    "emiel fucker":  {"label": "Emiel Fucker",  "price": 750_000_000,  "emoji": "👑", "color": 0xA349E8},
    "qeight fucker":   {"label": "Qeight Fucker",   "price": 1_000_000_000, "emoji": "✨", "color": 0xED4A6B},
}

# Ordering used for display (cheapest -> most prestigious)
TITLE_ORDER = ["i'm not into girls", "rapist", "azure fucker", "madhav fucker", "emiel fucker", "qeight fucker"]


def _user(user_id):
    return economy_collection.find_one({"user_id": str(user_id)}) or {}


def get_owned(user_id) -> list[str]:
    return _user(user_id).get("titles_owned", [])


def get_equipped(user_id) -> str | None:
    return _user(user_id).get("title_equipped")


def title_badge(user_id) -> str:
    """Returns 'emoji Label ' (with trailing space) for the equipped title, or ''."""
    key = get_equipped(user_id)
    if not key or key not in TITLES:
        return ""
    t = TITLES[key]
    return f"{t['emoji']} {t['label']} "


def buy_title(user_id, key: str) -> tuple[bool, str]:
    """Attempt to purchase a title. Returns (success, message)."""
    key = key.lower()

    if key not in TITLES:
        return False, f"❌ No title called **{key}**. Use `.titles` to see the list."

    owned = get_owned(user_id)
    if key in owned:
        return False, f"❌ You already own **{TITLES[key]['label']}**."

    price = TITLES[key]["price"]
    cash = get_cash(user_id)

    if cash < price:
        return False, f"❌ You need **{format_cash(price)}** — you have **{format_cash(cash)}**."

    remove_cash(user_id, price)

    economy_collection.update_one(
        {"user_id": str(user_id)},
        {
            "$addToSet": {"titles_owned": key},
            "$set": {"title_equipped": key},
        },
        upsert=True,
    )

    return True, f"✅ Purchased and equipped **{TITLES[key]['emoji']} {TITLES[key]['label']}**!"


def equip_title(user_id, key: str) -> tuple[bool, str]:
    key = key.lower()

    if key not in TITLES:
        return False, f"❌ No title called **{key}**."

    if key not in get_owned(user_id):
        return False, f"❌ You don't own **{TITLES[key]['label']}** yet. Buy it with `.titles buy {key}`."

    economy_collection.update_one(
        {"user_id": str(user_id)},
        {"$set": {"title_equipped": key}},
        upsert=True,
    )

    return True, f"✅ Equipped **{TITLES[key]['emoji']} {TITLES[key]['label']}**."


def unequip_title(user_id) -> tuple[bool, str]:
    economy_collection.update_one(
        {"user_id": str(user_id)},
        {"$set": {"title_equipped": None}},
        upsert=True,
    )
    return True, "✅ Title unequipped."
