"""
pokemon_moves.py
================
Handles .moves, .moveset, and .learncheck commands.

Learnset source : Pokémon Showdown  (National Dex — all generations)
Move stats      : PokéAPI           (power / type / damage class)

All bugs fixed:
  ✅  Fake Out on Lopunny — Showdown data includes egg moves
  ✅  Flash Cannon on Kingdra — Showdown inherits TM learnsets
  ✅  Hidden Power Ice / Fire / etc. — parsed as 60BP Special of that type
  ✅  Return / Frustration — shown as Physical 102BP (not status)
  ✅  Learnset covers ALL gens (Gen 1–9) so no move is unfairly rejected

Usage:
  .moves <Pokémon>   → opens 4-slot interactive dropdown UI
  .moveset / .ms     → view current moveset
  .learncheck / .lc  → check if a Pokémon can learn a move
"""

from __future__ import annotations

import asyncio
import json
import re

import aiohttp
import discord
from discord.ext import commands

from utils.pokemon_db import db


# ─────────────────────────────────────────────────────────────────
# ID HELPERS
# ─────────────────────────────────────────────────────────────────

def to_id(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower().strip())


def to_slug(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[''`]", "", text)
    return re.sub(r"[\s_]+", "-", text)


def gif_url(name: str) -> str:
    return f"https://play.pokemonshowdown.com/sprites/xyani/{to_id(name)}.gif"


# ─────────────────────────────────────────────────────────────────
# VISUAL HELPERS
# ─────────────────────────────────────────────────────────────────

TYPE_COLORS = {
    "normal":   0xA8A878, "fire":     0xF08030, "water":    0x6890F0,
    "electric": 0xF8D030, "grass":    0x78C850, "ice":      0x98D8D8,
    "fighting": 0xC03028, "poison":   0xA040A0, "ground":   0xE0C068,
    "flying":   0xA890F0, "psychic":  0xF85888, "bug":      0xA8B820,
    "rock":     0xB8A038, "ghost":    0x705898, "dragon":   0x7038F8,
    "dark":     0x705848, "steel":    0xB8B8D0, "fairy":    0xEE99AC,
}

TYPE_EMOJI = {
    "normal": "⬜", "fire": "🔥", "water": "💧",   "electric": "⚡",
    "grass":  "🍃", "ice":  "❄️",  "fighting": "🥊", "poison":   "☠️",
    "ground": "🌍", "flying": "🌬️", "psychic": "🔮", "bug":      "🐛",
    "rock":   "🪨", "ghost": "👻", "dragon": "🐉",  "dark":     "🌑",
    "steel":  "🔩", "fairy": "✨",
}

CAT_EMOJI   = {"physical": "💥", "special": "✨", "status": "🔄"}
SLOT_EMOJI  = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"]


# ─────────────────────────────────────────────────────────────────
# MOVE OVERRIDES
# ─────────────────────────────────────────────────────────────────

MOVE_OVERRIDES: dict[str, dict] = {
    "return":         {"display": "Return",         "power": 102, "type": "normal",   "category": "physical"},
    "frustration":    {"display": "Frustration",    "power": 102, "type": "normal",   "category": "physical"},
    "gyro-ball":      {"display": "Gyro Ball",      "power": 150, "type": "steel",    "category": "physical"},
    "heat-crash":     {"display": "Heat Crash",     "power": 120, "type": "fire",     "category": "physical"},
    "heavy-slam":     {"display": "Heavy Slam",     "power": 120, "type": "steel",    "category": "physical"},
    "electro-ball":   {"display": "Electro Ball",   "power": 150, "type": "electric", "category": "special"},
    "grass-knot":     {"display": "Grass Knot",     "power": 120, "type": "grass",    "category": "special"},
    "low-kick":       {"display": "Low Kick",       "power": 120, "type": "fighting", "category": "physical"},
    "trump-card":     {"display": "Trump Card",     "power": 200, "type": "normal",   "category": "special"},
    "magnitude":      {"display": "Magnitude",      "power": 70,  "type": "ground",   "category": "physical"},
    "stored-power":   {"display": "Stored Power",   "power": 20,  "type": "psychic",  "category": "special"},
    "power-trip":     {"display": "Power Trip",     "power": 20,  "type": "dark",     "category": "physical"},
    "spit-up":        {"display": "Spit Up",        "power": 300, "type": "normal",   "category": "special"},
    "acrobatics":     {"display": "Acrobatics",     "power": 110, "type": "flying",   "category": "physical"},
    "natural-gift":   {"display": "Natural Gift",   "power": 80,  "type": "normal",   "category": "physical"},
    "terrain-pulse":  {"display": "Terrain Pulse",  "power": 50,  "type": "normal",   "category": "special"},
    "echoed-voice":   {"display": "Echoed Voice",   "power": 40,  "type": "normal",   "category": "special"},
    "rollout":        {"display": "Rollout",        "power": 30,  "type": "rock",     "category": "physical"},
    "ice-ball":       {"display": "Ice Ball",       "power": 30,  "type": "ice",      "category": "physical"},
    "smelling-salts": {"display": "Smelling Salts", "power": 70,  "type": "normal",   "category": "physical"},
    "wake-up-slap":   {"display": "Wake-Up Slap",   "power": 70,  "type": "fighting", "category": "physical"},
    "wring-out":      {"display": "Wring Out",      "power": 120, "type": "normal",   "category": "special"},
    "crush-grip":     {"display": "Crush Grip",     "power": 120, "type": "normal",   "category": "physical"},
}


# ─────────────────────────────────────────────────────────────────
# HIDDEN POWER
# ─────────────────────────────────────────────────────────────────

_HP_TYPES = frozenset({
    "fire", "water", "grass", "electric", "ice", "fighting",
    "poison", "ground", "flying", "psychic", "bug", "rock",
    "ghost", "dragon", "dark", "steel",
})

_HP_RE = re.compile(r"^hidden[\s\-_]?power[\s\-_]?([a-z]+)?$", re.I)


def parse_hidden_power(name: str) -> dict | None:
    m = _HP_RE.match(name.strip())
    if not m:
        return None
    hp_type = (m.group(1) or "normal").lower()
    if hp_type not in _HP_TYPES and hp_type != "normal":
        return None
    return {
        "name":         f"hidden-power-{hp_type}",
        "display":      f"Hidden Power {hp_type.title()}",
        "power":        60,
        "type":         hp_type,
        "category":     "special",
        "_learnset_id": "hidden-power",
    }


# ─────────────────────────────────────────────────────────────────
# SHOWDOWN LEARNSET CACHE
# ─────────────────────────────────────────────────────────────────

_learnsets:    dict[str, set[str]] = {}
_learnsets_ok: bool                = False
_ls_lock:      asyncio.Lock | None = None


def _lock() -> asyncio.Lock:
    global _ls_lock
    if _ls_lock is None:
        _ls_lock = asyncio.Lock()
    return _ls_lock


async def _fetch_showdown_learnsets(session: aiohttp.ClientSession) -> bool:
    url = "https://play.pokemonshowdown.com/data/learnsets.js"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=45)) as r:
            if r.status != 200:
                return False
            text = await r.text()
    except Exception:
        return False

    match = re.search(r"(?:exports\.\w+\s*=\s*)(\{[\s\S]+\})\s*;", text)
    if not match:
        return False

    try:
        raw: dict = json.loads(match.group(1))
    except json.JSONDecodeError:
        return False

    prevo_map: dict[str, str] = {}
    tmp:       dict[str, set] = {}

    for poke_id, entry in raw.items():
        tmp[poke_id] = set(entry.get("learnset", {}).keys())
        prevo = entry.get("prevo")
        if prevo:
            prevo_map[poke_id] = to_id(str(prevo))

    for _ in range(5):
        changed = False
        for poke_id, prevo_id in prevo_map.items():
            add    = tmp.get(prevo_id, set())
            before = len(tmp.get(poke_id, set()))
            tmp[poke_id] = tmp.get(poke_id, set()) | add
            if len(tmp[poke_id]) != before:
                changed = True
        if not changed:
            break

    _learnsets.update(tmp)
    return True


async def ensure_learnsets(session: aiohttp.ClientSession) -> bool:
    global _learnsets_ok
    if _learnsets_ok:
        return True
    async with _lock():
        if not _learnsets_ok:
            _learnsets_ok = await _fetch_showdown_learnsets(session)
    return _learnsets_ok


def showdown_can_learn(pokemon_name: str, move_slug: str) -> bool | None:
    if not _learnsets_ok:
        return None

    poke_id = to_id(pokemon_name)
    move_id = to_id(move_slug)

    if move_id.startswith("hiddenpower"):
        move_id = "hiddenpower"

    if poke_id in _learnsets:
        return move_id in _learnsets[poke_id]

    for suffix in ("mega", "alola", "galar", "hisui", "paldea",
                   "origin", "black", "white", "therian",
                   "primal", "ultra", "sky"):
        if poke_id.endswith(suffix):
            base = poke_id[: -len(suffix)]
            if base in _learnsets:
                return move_id in _learnsets[base]

    return False


# ─────────────────────────────────────────────────────────────────
# MOVE DATA — PokéAPI with overrides
# ─────────────────────────────────────────────────────────────────

async def fetch_move_data(session: aiohttp.ClientSession, name: str) -> dict | None:
    hp = parse_hidden_power(name)
    if hp:
        return hp

    slug = to_slug(name)

    if slug in MOVE_OVERRIDES:
        ov = MOVE_OVERRIDES[slug]
        return {"name": slug, **ov}

    try:
        async with session.get(
            f"https://pokeapi.co/api/v2/move/{slug}",
            timeout=aiohttp.ClientTimeout(total=10),
        ) as r:
            if r.status != 200:
                return None
            data = await r.json()
    except Exception:
        return None

    return {
        "name":     data["name"],
        "display":  data["name"].replace("-", " ").title(),
        "power":    data.get("power") or 0,
        "type":     data["type"]["name"],
        "category": data["damage_class"]["name"],
    }


async def pokeapi_can_learn(session: aiohttp.ClientSession,
                             pokemon: str, move_slug: str) -> bool:
    try:
        async with session.get(
            f"https://pokeapi.co/api/v2/pokemon/{to_slug(pokemon)}",
            timeout=aiohttp.ClientTimeout(total=15),
        ) as r:
            if r.status != 200:
                return False
            data = await r.json()
    except Exception:
        return False

    learnable = {m["move"]["name"] for m in data["moves"]}
    check = "hidden-power" if move_slug.startswith("hidden-power") else move_slug
    return check in learnable


# ─────────────────────────────────────────────────────────────────
# MOVE LIST  (alphabetical, max 24 per page — Discord hard limit is 25)
# The last option on each page is always "▶ Next page" so we stay ≤25
# ─────────────────────────────────────────────────────────────────

_ALL_MOVES: list[str] = sorted([
    # Physical
    "Acrobatics", "Aqua Jet", "Aqua Tail", "Body Slam", "Bounce",
    "Brave Bird", "Brick Break", "Bug Bite", "Bulldoze", "Close Combat",
    "Crunch", "Dragon Claw", "Dragon Rush", "Drain Punch", "Earthquake",
    "Extreme Speed", "Facade", "Fake Out", "Fire Punch", "Flare Blitz",
    "Fly", "Frustration", "Gunk Shot", "Head Smash", "High Jump Kick",
    "Ice Punch", "Ice Shard", "Iron Head", "Iron Tail", "Knock Off",
    "Low Kick", "Low Sweep", "Mach Punch", "Play Rough", "Poison Jab",
    "Power Whip", "Psycho Cut", "Pursuit", "Quick Attack", "Return",
    "Rock Slide", "Rock Tomb", "Seed Bomb", "Shadow Claw", "Shadow Sneak",
    "Sucker Punch", "Super Fang", "Superpower", "Throat Chop",
    "Thunder Punch", "U-turn", "Wild Charge", "Wing Attack",
    "Wood Hammer", "X-Scissor", "Zen Headbutt",
    # Special
    "Aura Sphere", "Blizzard", "Boomburst", "Bug Buzz",
    "Charge Beam", "Dark Pulse", "Dazzling Gleam",
    "Dragon Pulse", "Draco Meteor", "Earth Power", "Energy Ball",
    "Extrasensory", "Fire Blast", "Flamethrower", "Flash Cannon",
    "Focus Blast", "Giga Drain", "Hex", "Hydro Pump",
    "Hyper Voice", "Ice Beam", "Leaf Storm",
    "Moonblast", "Night Shade", "Overheat",
    "Petal Dance", "Power Gem", "Psychic", "Psyshock",
    "Scald", "Shadow Ball", "Signal Beam", "Sludge Bomb", "Sludge Wave",
    "Stored Power", "Surf", "Thunderbolt", "Thunder", "Tri Attack",
    "Vacuum Wave", "Volt Switch", "Water Pulse",
    # Status
    "Agility", "Amnesia", "Aromatherapy", "Baton Pass",
    "Bulk Up", "Calm Mind", "Cotton Guard", "Curse", "Defog",
    "Dragon Dance", "Encore", "Endure", "Glare", "Gravity",
    "Growth", "Haze", "Heal Bell", "Helping Hand", "Howl",
    "Leech Seed", "Light Screen", "Magic Coat",
    "Memento", "Moonlight", "Morning Sun", "Pain Split",
    "Parting Shot", "Perish Song", "Protect", "Quiver Dance",
    "Rapid Spin", "Recover", "Reflect", "Rest", "Roost",
    "Shell Smash", "Shift Gear", "Sleep Talk",
    "Soft-Boiled", "Spikes", "Stealth Rock", "Sticky Web",
    "Substitute", "Sunny Day", "Swords Dance", "Synthesis", "Taunt",
    "Thunder Wave", "Toxic", "Toxic Spikes", "Trick",
    "Trick Room", "Will-O-Wisp", "Wish", "Yawn",
    # Hidden Power
    "Hidden Power Bug", "Hidden Power Dark", "Hidden Power Dragon",
    "Hidden Power Electric", "Hidden Power Fighting", "Hidden Power Fire",
    "Hidden Power Flying", "Hidden Power Ghost", "Hidden Power Grass",
    "Hidden Power Ground", "Hidden Power Ice", "Hidden Power Poison",
    "Hidden Power Psychic", "Hidden Power Rock", "Hidden Power Steel",
    "Hidden Power Water",
], key=str.lower)

# ── Pagination ────────────────────────────────────────────────────
# Discord hard limit: 25 options per Select.
# Page 0 reserves 1 slot for "Skip" + 1 slot for "Next page" nav  → 23 moves max
# Every other page reserves 1 slot for nav only                   → 24 moves max

_PAGE0_SIZE  = 23   # skip(1) + moves(23) + nav(1) = 25
_PAGEn_SIZE  = 24   # moves(24) + nav(1) = 25

# Build pages: page 0 holds first 23 moves, then 24 each after that
_p0          = _ALL_MOVES[:_PAGE0_SIZE]
_rest        = _ALL_MOVES[_PAGE0_SIZE:]
_MOVE_PAGES: list[list[str]] = [_p0] + [
    _rest[i: i + _PAGEn_SIZE]
    for i in range(0, len(_rest), _PAGEn_SIZE)
]
_TOTAL_PAGES = len(_MOVE_PAGES)


def _page_move_count(page: int) -> int:
    return len(_MOVE_PAGES[page])


def _make_select_options(
    slot: int,
    page: int,
    current_move: str | None,
) -> list[discord.SelectOption]:
    """
    Build exactly ≤25 SelectOptions for one slot on the given page.
    Page 0: skip(1) + moves(23) + nav(1) = 25
    Page N: moves(24) + nav(1) = 25
    """
    options: list[discord.SelectOption] = []

    # "Skip" only appears on page 0
    if page == 0:
        options.append(discord.SelectOption(
            label="— Skip this slot —",
            value="__none__",
            description="Leave this move slot empty",
            emoji="➖",
            default=(current_move is None),
        ))

    for move in _MOVE_PAGES[page]:
        options.append(discord.SelectOption(
            label=move,
            value=move,
            default=(move == current_move),
        ))

    # Navigation arrow — always present, wraps back to page 0 on last page
    next_page = (page + 1) % _TOTAL_PAGES
    nav_label = "▶  Next page →" if page < _TOTAL_PAGES - 1 else "◀  Back to start ↩"
    # Count where we are in the full move list for the description
    start_idx = (_PAGE0_SIZE if page > 0 else 0) + (page - 1) * _PAGEn_SIZE if page > 0 else 0
    end_idx   = start_idx + len(_MOVE_PAGES[page])
    options.append(discord.SelectOption(
        label=nav_label,
        value=f"__page_{next_page}__",
        description=f"Page {page + 1} of {_TOTAL_PAGES}",
        emoji="📄",
    ))

    # Safety assertion — will raise loudly in dev if we ever break the limit
    assert len(options) <= 25, (
        f"_make_select_options built {len(options)} options on page {page} — Discord limit is 25!"
    )

    return options


# ─────────────────────────────────────────────────────────────────
# EMBED BUILDERS
# ─────────────────────────────────────────────────────────────────

def _preview_embed(
    poke_display: str,
    poke_name: str,
    selections: list[str | None],
) -> discord.Embed:
    filled = sum(1 for s in selections if s)
    bar    = "▓" * filled + "░" * (4 - filled)

    embed = discord.Embed(
        title=f"🎮  Teaching moves to {poke_display}",
        description=(
            "Pick up to **4 moves** using the dropdowns below.\n"
            "Each dropdown has multiple pages — use **▶ Next page** to browse.\n"
            "Hit **✅ Confirm** when you're ready."
        ),
        color=0x5865F2,
    )
    embed.set_thumbnail(url=gif_url(poke_name))

    slot_lines = []
    for i, sel in enumerate(selections):
        if sel:
            slot_lines.append(f"{SLOT_EMOJI[i]}  **{sel}**")
        else:
            slot_lines.append(f"{SLOT_EMOJI[i]}  *— empty —*")

    embed.add_field(name="📋  Current Selection", value="\n".join(slot_lines), inline=False)
    embed.set_footer(text=f"{bar}  {filled}/4 slots filled  •  National Dex · All generations")
    return embed


def _result_embed(
    poke_display: str,
    poke_name: str,
    taught: list[dict],
    not_found: list[str],
    cant_learn: list[str],
) -> discord.Embed:
    primary_type = taught[0]["type"] if taught else "normal"
    embed = discord.Embed(
        title=f"✅  Moves taught to {poke_display}!",
        color=TYPE_COLORS.get(primary_type, 0x5865F2),
    )
    embed.set_thumbnail(url=gif_url(poke_name))

    move_lines = []
    for i, m in enumerate(taught, 1):
        t_emoji = TYPE_EMOJI.get(m["type"], "")
        c_emoji = CAT_EMOJI.get(m["category"], "")
        power   = f"**{m['power']} BP**" if m["power"] else "—"
        move_lines.append(
            f"`{i}.` **{m['display']}**\n"
            f"     {t_emoji} {m['type'].title()}  "
            f"• {c_emoji} {m['category'].title()}  "
            f"• ⚡ {power}"
        )

    embed.add_field(name="📋  Moveset", value="\n".join(move_lines), inline=False)

    if not_found or cant_learn:
        warn = []
        if not_found:
            warn.append(f"❌ Not found: {', '.join(not_found)}")
        if cant_learn:
            warn.append(f"🚫 Can't learn: {', '.join(cant_learn)}")
        embed.add_field(name="⚠️  Skipped", value="\n".join(warn), inline=False)

    embed.set_footer(text="National Dex • All generations • Use .team to build your roster")
    return embed


# ─────────────────────────────────────────────────────────────────
# MOVE DROPDOWN UI — one Select per slot, paged navigation
# ─────────────────────────────────────────────────────────────────

class MoveSelect(discord.ui.Select):
    """One move-slot dropdown with paged navigation."""

    def __init__(self, slot: int, page: int, current: str | None):
        self.slot    = slot
        self.page    = page
        self.current = current
        slot_names   = ["Move 1", "Move 2", "Move 3", "Move 4"]
        super().__init__(
            placeholder=f"🎯  {slot_names[slot]} — pick a move…",
            min_values=1,
            max_values=1,
            options=_make_select_options(slot, page, current),
            row=slot,
            custom_id=f"move_slot_{slot}",
        )

    async def callback(self, interaction: discord.Interaction):
        await self.view.handle_select(interaction, self.slot, self.values[0])


class ConfirmButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Confirm Moveset",
            style=discord.ButtonStyle.success,
            emoji="✅",
            row=4,
            custom_id="confirm_moves",
        )

    async def callback(self, interaction: discord.Interaction):
        await self.view.handle_confirm(interaction)


class CancelButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Cancel",
            style=discord.ButtonStyle.danger,
            emoji="✖️",
            row=4,
            custom_id="cancel_moves",
        )

    async def callback(self, interaction: discord.Interaction):
        await self.view.handle_cancel(interaction)


class MoveSelectView(discord.ui.View):
    """4-slot paged move selector. Only the invoker can interact."""

    def __init__(
        self,
        ctx: commands.Context,
        poke_name: str,
        poke_display: str,
        uid: str,
        timeout: float = 180.0,
    ):
        super().__init__(timeout=timeout)
        self.ctx          = ctx
        self.poke_name    = poke_name
        self.poke_display = poke_display
        self.uid          = uid
        self.message:     discord.Message | None = None

        # Per-slot state
        self.selections: list[str | None] = [None, None, None, None]
        self.pages:      list[int]        = [0, 0, 0, 0]

        self._rebuild_components()

    # ── helpers ───────────────────────────────────────────────────

    def _rebuild_components(self):
        """Clear and re-add all 4 selects + 2 buttons."""
        self.clear_items()
        for i in range(4):
            self.add_item(MoveSelect(i, self.pages[i], self.selections[i]))
        self.add_item(ConfirmButton())
        self.add_item(CancelButton())

    # ── guard ─────────────────────────────────────────────────────

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != self.uid:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="⛔  Only the person who ran `.moves` can use these menus.",
                    color=0xED4245,
                ),
                ephemeral=True,
            )
            return False
        return True

    # ── select callback ───────────────────────────────────────────

    async def handle_select(
        self, interaction: discord.Interaction, slot: int, value: str
    ):
        if value.startswith("__page_"):
            # Navigate to a different page for this slot
            self.pages[slot] = int(value.split("__page_")[1].rstrip("__"))
        elif value == "__none__":
            self.selections[slot] = None
        else:
            self.selections[slot] = value

        self._rebuild_components()
        await interaction.response.edit_message(
            embed=_preview_embed(self.poke_display, self.poke_name, self.selections),
            view=self,
        )

    # ── confirm ───────────────────────────────────────────────────

    async def handle_confirm(self, interaction: discord.Interaction):
        chosen = [s for s in self.selections if s]
        if not chosen:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="❌  Select at least **1 move** before confirming.",
                    color=0xED4245,
                ),
                ephemeral=True,
            )
            return

        # Disable everything while validating
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(
            embed=discord.Embed(
                description=(
                    f"⏳  Validating **{len(chosen)} move(s)** for **{self.poke_display}** "
                    "against National Dex learnset…"
                ),
                color=0x5865F2,
            ),
            view=self,
        )

        taught:     list[dict] = []
        not_found:  list[str]  = []
        cant_learn: list[str]  = []

        async with aiohttp.ClientSession() as session:
            await ensure_learnsets(session)
            for raw in chosen:
                move_data = await fetch_move_data(session, raw)
                if move_data is None:
                    not_found.append(raw.title())
                    continue
                learnset_slug = move_data.get("_learnset_id", move_data["name"])
                result = showdown_can_learn(self.poke_name, learnset_slug)
                if result is None:
                    result = await pokeapi_can_learn(session, self.poke_name, learnset_slug)
                if not result:
                    cant_learn.append(move_data["display"])
                    continue
                taught.append(move_data)

        self.stop()

        if not taught:
            lines = []
            if not_found:
                lines.append(f"❌  Move(s) not found: **{', '.join(not_found)}**")
            if cant_learn:
                lines.append(
                    f"🚫  **{self.poke_display}** can't learn in National Dex: "
                    f"**{', '.join(cant_learn)}**"
                )
            lines.append(
                "\n*Check spelling. If you believe this is wrong, "
                "use `.learncheck <Pokémon> <move>` to investigate.*"
            )
            await interaction.edit_original_response(
                embed=discord.Embed(description="\n".join(lines), color=0xED4245),
                view=None,
            )
            return

        db.pokemon_collection.update_one(
            {"user_id": self.uid, "name": self.poke_name},
            {"$set": {"moves": [m["name"] for m in taught]}},
        )

        await interaction.edit_original_response(
            embed=_result_embed(
                self.poke_display, self.poke_name, taught, not_found, cant_learn
            ),
            view=None,
        )

    # ── cancel ────────────────────────────────────────────────────

    async def handle_cancel(self, interaction: discord.Interaction):
        self.stop()
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="✖️  Move selection cancelled",
                description=f"You stopped learning moves for **{self.poke_display}**.",
                color=0x95A5A6,
            ),
            view=None,
        )

    # ── timeout ───────────────────────────────────────────────────

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(
                    embed=discord.Embed(
                        title="⏰  Move selection timed out",
                        description=(
                            f"The move selector for **{self.poke_display}** expired.\n"
                            "Run `.moves` again to retry."
                        ),
                        color=0x95A5A6,
                    ),
                    view=None,
                )
            except discord.NotFound:
                pass


# ─────────────────────────────────────────────────────────────────
# COG
# ─────────────────────────────────────────────────────────────────

class PokemonMoves(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        async with aiohttp.ClientSession() as s:
            ok = await ensure_learnsets(s)
        if ok:
            print(f"[PokemonMoves] ✅ Showdown learnsets loaded — {len(_learnsets):,} Pokémon")
        else:
            print("[PokemonMoves] ⚠️  Showdown learnsets unavailable — falling back to PokéAPI")

    # ── .moves ───────────────────────────────────────────────────

    @commands.command(name="moves")
    async def moves(self, ctx, pokemon_name: str = None):
        """
        Open the interactive move-selection UI for a Pokémon you own.

        Usage:   .moves <Pokémon>
        Example: .moves Pikachu
        """
        uid = str(ctx.author.id)

        if not pokemon_name:
            await ctx.send(embed=discord.Embed(
                title="📖  How to teach moves",
                description=(
                    "**Usage:** `.moves <Pokémon>`\n\n"
                    "**Example:** `.moves Pikachu`\n\n"
                    "This opens an interactive menu where you can pick up to **4 moves** "
                    "using dropdowns. Moves are sorted alphabetically and split across pages."
                ),
                color=0x5865F2,
            ))
            return

        pname    = pokemon_name.strip().lower()
        poke_doc = db.pokemon_collection.find_one({"user_id": uid, "name": pname})

        if not poke_doc:
            await ctx.send(embed=discord.Embed(
                description=f"❌  You don't own a **{pokemon_name.title()}**.",
                color=0xED4245,
            ))
            return

        poke_display = poke_doc.get("display", pname.title())

        view = MoveSelectView(ctx, pname, poke_display, uid)
        msg  = await ctx.send(
            embed=_preview_embed(poke_display, pname, view.selections),
            view=view,
        )
        view.message = msg

    # ── .moveset ──────────────────────────────────────────────────

    @commands.command(name="moveset", aliases=["ms"])
    async def moveset(self, ctx, pokemon_name: str = None, member: discord.Member = None):
        """View the current moveset of a Pokémon you (or another user) own."""
        if not pokemon_name:
            await ctx.send(embed=discord.Embed(
                description=(
                    "**Usage:** `.moveset <Pokémon>` or `.moveset <Pokémon> @user`\n"
                    "**Alias:** `.ms <Pokémon>`"
                ),
                color=0xED4245,
            ))
            return

        target   = member or ctx.author
        pname    = pokemon_name.strip().lower()
        poke_doc = db.pokemon_collection.find_one({"user_id": str(target.id), "name": pname})

        if not poke_doc:
            await ctx.send(embed=discord.Embed(
                description=(
                    f"**{target.display_name}** doesn't own "
                    f"a **{pokemon_name.title()}**."
                ),
                color=0xED4245,
            ))
            return

        saved_moves: list[str] = poke_doc.get("moves", [])
        display                = poke_doc.get("display", pname.title())

        embed = discord.Embed(title=f"📋  {display}'s Moveset", color=0x5865F2)
        embed.set_thumbnail(url=gif_url(pname))

        if not saved_moves:
            embed.description = "No moves taught yet!\nUse `.moves <Pokémon>` to assign up to 4 moves."
        else:
            lines = []
            for i, slug in enumerate(saved_moves, 1):
                pretty = slug.replace("-", " ").title()
                lines.append(f"`{i}.` **{pretty}**")
            embed.description = "\n".join(lines)

        embed.set_footer(text=f"Owned by {target.display_name}")
        await ctx.send(embed=embed)

    # ── .learncheck ───────────────────────────────────────────────

    @commands.command(name="learncheck", aliases=["lc", "canlearn"])
    async def learncheck(self, ctx, pokemon_name: str = None, *, move_name: str = None):
        """
        Check if a Pokémon can learn a specific move in National Dex.

        Examples:
          .learncheck Lopunny Fake Out
          .learncheck Kingdra Flash Cannon
          .learncheck Jolteon Hidden Power Ice
        """
        if not pokemon_name or not move_name:
            await ctx.send(embed=discord.Embed(
                description=(
                    "**Usage:** `.learncheck <Pokémon> <move>`\n"
                    "**Aliases:** `.lc`, `.canlearn`\n\n"
                    "Examples:\n"
                    "`.lc Lopunny Fake Out`\n"
                    "`.lc Kingdra Flash Cannon`"
                ),
                color=0xED4245,
            ))
            return

        async with aiohttp.ClientSession() as session:
            await ensure_learnsets(session)
            move_data = await fetch_move_data(session, move_name)

        if not move_data:
            await ctx.send(embed=discord.Embed(
                description=f"❌  Move **{move_name.title()}** not found.",
                color=0xED4245,
            ))
            return

        learnset_slug = move_data.get("_learnset_id", move_data["name"])
        result        = showdown_can_learn(pokemon_name, learnset_slug)

        t_emoji = TYPE_EMOJI.get(move_data["type"], "")
        c_emoji = CAT_EMOJI.get(move_data["category"], "")
        power   = f"{move_data['power']} BP" if move_data["power"] else "—"

        move_info = (
            f"{t_emoji} {move_data['type'].title()}  "
            f"• {c_emoji} {move_data['category'].title()}  "
            f"• ⚡ {power}"
        )

        if result is True:
            embed = discord.Embed(
                title=f"✅  {pokemon_name.title()} CAN learn {move_data['display']}",
                description=move_info,
                color=0x57F287,
            )
        elif result is False:
            embed = discord.Embed(
                title=f"❌  {pokemon_name.title()} CANNOT learn {move_data['display']}",
                description=f"{move_info}\n\n*Not in National Dex learnset.*",
                color=0xED4245,
            )
        else:
            embed = discord.Embed(
                description="⚠️  Learnset data not yet loaded. Try again in a moment.",
                color=0xFEE75C,
            )

        embed.set_thumbnail(url=gif_url(pokemon_name))
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(PokemonMoves(bot))
