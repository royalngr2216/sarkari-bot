import discord

from utils.pokemon_db import db

# ─────────────────────────────────────────────────────────────────
# SHARED BRANDING
# ─────────────────────────────────────────────────────────────────

DEFAULT_SERVER_NAME = "Sarkari Adda"
DEFAULT_CHARACTER_NAME = "Neel"

settings_collection = db["bot_settings"]


def _get_settings(guild_id):
    return settings_collection.find_one({
        "guild_id": str(guild_id)
    }) or {}


def get_server_name(guild_id):
    """Get the custom server/brand name for a guild."""
    settings = _get_settings(guild_id)
    return settings.get("server_name", DEFAULT_SERVER_NAME)


def get_character_name(guild_id):
    """Get the custom character name for a guild."""
    settings = _get_settings(guild_id)
    return settings.get("character_name", DEFAULT_CHARACTER_NAME)


def set_server_name(guild_id, name):
    """Save a custom server/brand name for a guild."""
    name = name.strip()

    if not name:
        raise ValueError("Server name cannot be empty.")

    settings_collection.update_one(
        {"guild_id": str(guild_id)},
        {"$set": {"server_name": name}},
        upsert=True
    )


def set_character_name(guild_id, name):
    """Save a custom character name for a guild."""
    name = name.strip()

    if not name:
        raise ValueError("Character name cannot be empty.")

    settings_collection.update_one(
        {"guild_id": str(guild_id)},
        {"$set": {"character_name": name}},
        upsert=True
    )


def brand(
    embed: discord.Embed,
    guild_id: int,
    extra: str | None = None
) -> discord.Embed:
    """
    Stamp the dynamic server name onto an embed footer while
    preserving useful existing footer text.
    """

    existing = embed.footer.text if embed.footer else None

    parts = [get_server_name(guild_id)]

    if extra:
        parts.append(extra)
    elif existing:
        parts.append(existing)

    embed.set_footer(text="  •  ".join(parts))

    return embed
