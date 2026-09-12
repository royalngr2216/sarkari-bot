import os
from pymongo import MongoClient

# Import your economy functions as you originally had them
from utils.economy import (
    get_cash,
    add_cash,
    remove_cash,
    format_cash,
    parse_amount
)

# -----------------------------------
# MONGODB CONNECTION SETUP
# -----------------------------------
# It's best practice to connect once globally so MongoDB handles connection pooling
MONGO_URI = os.getenv("MONGO_URI")

if MONGO_URI:
    cluster = MongoClient(MONGO_URI)
    db = cluster["owo_clone"] # You can rename this database
else:
    print("❌ WARNING: MONGO_URI not found in environment variables!")
    db = None

# Define the collections
pokemon_collection = db["pokemon"] if db is not None else None
pokemon_market = db["pokemon_market"] if db is not None else None
pokemon_spawn_channels = db["pokemon_spawn_channels"] if db is not None else None
emiel_log = db["emiel_log"] if db is not None else None
character_names = db["character_names"] if db is not None else None

# -----------------------------------
# CUSTOM CHARACTER NAME (per-server)
# -----------------------------------
# Lets a server rename the "thief" character shown when catches, fish,
# donations, or mines get stolen (e.g. .setcharacter Neel). Falls back
# to the original name if nothing has been set for that guild.

DEFAULT_CHARACTER_NAME = "Emiel"


def get_character_name(guild_id) -> str:
    """Return the custom steal/rob character name set for a guild."""
    if character_names is None or guild_id is None:
        return DEFAULT_CHARACTER_NAME

    doc = character_names.find_one({"guild_id": guild_id})
    return doc["name"] if doc else DEFAULT_CHARACTER_NAME


def set_character_name(guild_id, name: str):
    """Set the custom steal/rob character name for a guild."""
    character_names.update_one(
        {"guild_id": guild_id},
        {"$set": {"name": name}},
        upsert=True
    )


# -----------------------------------
# DATABASE UTILITY FUNCTIONS
# -----------------------------------

def get_pokemon_data(user_id: int) -> dict:
    """Fetches a player's Pokémon document. Creates one if it doesn't exist."""
    user_data = pokemon_collection.find_one({"_id": user_id})
    
    if not user_data:
        user_data = {
    "_id": user_id,
    "team": [],
    "inventory": [],
    "caught_count": 0,

    "balls": {
        "pokeball": 0,
        "ultraball": 0,
        "masterball": 0
    }
        }
        # Insert the default schema into MongoDB
        pokemon_collection.insert_one(user_data)
        
    return user_data

def get_team(user_id: int) -> list:
    data = get_pokemon_data(user_id)
    return data.get("team", [])

def set_team(user_id: int, new_team: list):
    """Updates a user's equipped team."""
    pokemon_collection.update_one(
        {"_id": user_id},
        {"$set": {"team": new_team}},
        upsert=True
    )

def owns_pokemon(user_id: int, pokemon_name: str) -> bool:
    """Checks if a user has a specific Pokémon in their inventory."""
    data = get_pokemon_data(user_id)
    return pokemon_name in data.get("inventory", [])

def add_pokemon(user_id: int, pokemon_name: str):
    """Adds a newly caught Pokémon to the user's inventory."""
    pokemon_collection.update_one(
        {"_id": user_id},
        # $push appends to the array, $inc increments the counter by 1
        {"$push": {"inventory": pokemon_name}, "$inc": {"caught_count": 1}},
        upsert=True
    )

def remove_from_team(user_id: int, pokemon_name: str):
    """Removes a specific Pokémon from the active team array."""
    pokemon_collection.update_one(
        {"_id": user_id},
        {"$pull": {"team": pokemon_name}} # $pull removes items from arrays in MongoDB
    )
def get_balls(user_id):
    data = get_pokemon_data(user_id)

    if "balls" not in data:
        pokemon_collection.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "balls": {
                        "pokeball": 0,
                        "ultraball": 0,
                        "masterball": 0
                    }
                }
            }
        )

        return {
            "pokeball": 0,
            "ultraball": 0,
            "masterball": 0
        }

    return data["balls"]


def add_ball(user_id, ball_type, amount=1):
    pokemon_collection.update_one(
        {"_id": user_id},
        {"$inc": {f"balls.{ball_type}": amount}},
        upsert=True
    )


def remove_ball(user_id, ball_type, amount=1):
    pokemon_collection.update_one(
        {"_id": user_id},
        {"$inc": {f"balls.{ball_type}": -amount}}
    )


def log_emiel_event(event_type: str, **fields):
    """Append an entry to the global Emiel activity log.

    event_type: "steal" or "sale"

    For "steal", pass: user_id, pokemon_display, rarity
    For "sale",  pass: seller_id, pokemon_display, rarity, price
    """
    import datetime as _dt

    entry = {
        "type": event_type,
        "timestamp": _dt.datetime.utcnow(),
        **fields,
    }

    emiel_log.insert_one(entry)


def get_emiel_log(limit: int = 10) -> list:
    """Fetch the most recent Emiel events, newest first."""
    return list(
        emiel_log.find().sort("timestamp", -1).limit(limit)
    )

def transfer_pokemon(seller_id: int, buyer_id: int, pokemon_name: str, price: int) -> tuple:
    """Handles the market logic for trading Pokémon."""
    if not owns_pokemon(seller_id, pokemon_name):
        return False, "The seller does not own this Pokémon."
    
    buyer_cash = get_cash(buyer_id)
    if buyer_cash < price:
        return False, "The buyer does not have enough cash."
        
    # Process economy transfer
    remove_cash(buyer_id, price)
    add_cash(seller_id, price)
    
    # Move the Pokémon in MongoDB
    pokemon_collection.update_one({"_id": seller_id}, {"$pull": {"inventory": pokemon_name}})
    pokemon_collection.update_one({"_id": buyer_id}, {"$push": {"inventory": pokemon_name}}, upsert=True)
    
    return True, "Trade executed successfully!"
    
