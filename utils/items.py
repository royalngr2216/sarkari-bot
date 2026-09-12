# ─────────────────────────
# FISHING ITEMS
# ─────────────────────────

FISHING_ITEMS = [

    {
        "name": "smallfish",
        "display": "Small Fish",
        "emoji": "🐟",
        "price": 10000,
        "chance": 30
    },

    {
        "name": "salmon",
        "display": "Salmon",
        "emoji": "🐠",
        "price": 25000,
        "chance": 24
    },

    {
        "name": "crab",
        "display": "Crab",
        "emoji": "🦀",
        "price": 50000,
        "chance": 20
    },

    {
        "name": "lobster",
        "display": "Lobster",
        "emoji": "🦞",
        "price": 100000,
        "chance": 11
    },

    {
        "name": "pearl",
        "display": "Pearl",
        "emoji": "🦪",
        "price": 250000,
        "chance": 8
    },

    {
        "name": "goldenfish",
        "display": "Golden Fish",
        "emoji": "🐡",
        "price": 500000,
        "chance": 5
    },

    {
        "name": "ancientrelic",
        "display": "Ancient Relic",
        "emoji": "⚱️",
        "price": 1000000,
        "chance": 2
    }

]


# ─────────────────────────
# HUNTING ITEMS
# ─────────────────────────

HUNTING_ITEMS = [

    {
        "name": "rabbit",
        "display": "Rabbit",
        "emoji": "🐇",
        "price": 10000,
        "chance": 30
    },

    {
        "name": "deer",
        "display": "Deer",
        "emoji": "🦌",
        "price": 25000,
        "chance": 24
    },

    {
        "name": "wolfpelt",
        "display": "Wolf Pelt",
        "emoji": "🐺",
        "price": 50000,
        "chance": 20
    },

    {
        "name": "bearclaw",
        "display": "Bear Claw",
        "emoji": "🐻",
        "price": 100000,
        "chance": 11
    },

    {
        "name": "eaglefeather",
        "display": "Eagle Feather",
        "emoji": "🦅",
        "price": 250000,
        "chance": 8
    },

    {
        "name": "dragonskull",
        "display": "Dragon Skull",
        "emoji": "☠️",
        "price": 500000,
        "chance": 5
    },

    {
        "name": "mythichorn",
        "display": "Mythic Horn",
        "emoji": "🦄",
        "price": 1000000,
        "chance": 2
    }

]

# ─────────────────────────
# MINING ITEMS
# ─────────────────────────

MINING_ITEMS = [

    {
        "name": "stone",
        "display": "Stone",
        "emoji": "🪨",
        "price": 15000,
        "chance": 35
    },

    {
        "name": "iron",
        "display": "Iron",
        "emoji": "🔩",
        "price": 50000,
        "chance": 25
    },

    {
        "name": "gold",
        "display": "Gold",
        "emoji": "⚜️",
        "price": 100000,
        "chance": 18
    },

    {
        "name": "diamond",
        "display": "Diamond",
        "emoji": "💎",
        "price": 200000,
        "chance": 10
    },

    {
        "name": "emerald",
        "display": "Emerald",
        "emoji": "🔮",
        "price": 500000,
        "chance": 7
    },

    {
        "name": "ruby",
        "display": "Ruby",
        "emoji": "♦️",
        "price": 1000000,
        "chance": 4
    },

    {
        "name": "void_crystal",
        "display": "Void Crystal",
        "emoji": "🌌",
        "price": 5000000,
        "chance": 1
    }

]

# ─────────────────────────
# ALL ITEMS
# ─────────────────────────

ALL_ITEMS = {}

for item in FISHING_ITEMS:

    ALL_ITEMS[item["name"]] = item

for item in HUNTING_ITEMS:

    ALL_ITEMS[item["name"]] = item

for item in MINING_ITEMS:

    ALL_ITEMS[item["name"]] = item
