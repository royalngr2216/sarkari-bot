import discord

# ─────────────────────────────────────────────────────────────────
# SHARED BRAND FOOTER
# ─────────────────────────────────────────────────────────────────
# A handful of cogs (e.g. rob.py) already stamp "ECHLEON" in their
# footer, most don't. This makes it consistent everywhere without
# stomping on footers that already carry useful info (timers, page
# counts, etc.) — those get "ECHLEON  •  <existing text>" instead.

BRAND = "ECHLEON"


def brand(embed: discord.Embed, extra: str | None = None) -> discord.Embed:
    """Stamp the ECHLEON footer on an embed, preserving any existing footer text."""
    existing = embed.footer.text if embed.footer else None
    parts = [BRAND]
    if extra:
        parts.append(extra)
    elif existing:
        parts.append(existing)
    embed.set_footer(text="  •  ".join(parts))
    return embed
