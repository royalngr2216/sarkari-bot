from discord.ext import commands
import discord
import asyncio
import random

from cogs.pokemon_team import get_team, fetch_pokemon_data
from utils.economy import get_cash, add_cash, remove_cash, format_cash
from cogs.battle_renderer import make_battle_file

def gif_url(name: str) -> str:
    clean = name.lower().replace(" ", "").replace(".", "").replace("'", "")
    return f"https://play.pokemonshowdown.com/sprites/xyani/{clean}.gif"

# ─────────────────────────────────────────────────────────────────
# PRIORITY TABLE  (Showdown accurate)
# ─────────────────────────────────────────────────────────────────

PRIORITIES = {
    "helping-hand": 5,
    "protect": 4, "detect": 4, "endure": 4, "kings-shield": 4,
    "spiky-shield": 4, "baneful-bunker": 4,
    "fake-out": 3, "wide-guard": 3, "quick-guard": 3,
    "extreme-speed": 2, "feint": 2, "first-impression": 2,
    "quick-attack": 1, "ice-shard": 1, "mach-punch": 1,
    "bullet-punch": 1, "aqua-jet": 1, "shadow-sneak": 1,
    "sucker-punch": 1, "water-shuriken": 1, "accelerock": 1,
    "vacuum-wave": 1, "bide": 1,
    "trick-room": -7,
    "roar": -6, "whirlwind": -6, "dragon-tail": -6, "circle-throw": -6,
    "counter": -5, "mirror-coat": -5,
    "avalanche": -4, "revenge": -4,
}

def get_priority(move_name: str) -> int:
    return PRIORITIES.get(move_name.lower().replace(" ", "-"), 0)

# ─────────────────────────────────────────────────────────────────
# TYPE CHART  (Gen 6+)
# ─────────────────────────────────────────────────────────────────

TYPE_CHART: dict[str, dict[str, float]] = {
    "normal":   {"rock":0.5,"ghost":0,"steel":0.5},
    "fire":     {"fire":0.5,"water":0.5,"rock":0.5,"dragon":0.5,"grass":2,"ice":2,"bug":2,"steel":2},
    "water":    {"water":0.5,"grass":0.5,"dragon":0.5,"fire":2,"ground":2,"rock":2},
    "grass":    {"fire":0.5,"grass":0.5,"poison":0.5,"flying":0.5,"bug":0.5,"dragon":0.5,"steel":0.5,"water":2,"ground":2,"rock":2},
    "electric": {"grass":0.5,"electric":0.5,"dragon":0.5,"ground":0,"flying":2,"water":2},
    "ice":      {"water":0.5,"ice":0.5,"steel":0.5,"fire":0.5,"grass":2,"ground":2,"flying":2,"dragon":2},
    "fighting": {"poison":0.5,"bug":0.5,"psychic":0.5,"flying":0.5,"fairy":0.5,"ghost":0,"normal":2,"ice":2,"rock":2,"dark":2,"steel":2},
    "poison":   {"poison":0.5,"ground":0.5,"rock":0.5,"ghost":0.5,"steel":0,"grass":2,"fairy":2},
    "ground":   {"grass":0.5,"bug":0.5,"electric":0,"flying":0,"fire":2,"poison":2,"rock":2,"steel":2},
    "flying":   {"electric":0.5,"rock":0.5,"steel":0.5,"ground":0,"grass":2,"fighting":2,"bug":2},
    "psychic":  {"psychic":0.5,"steel":0.5,"dark":0,"fighting":2,"poison":2},
    "bug":      {"fire":0.5,"fighting":0.5,"flying":0.5,"ghost":0.5,"steel":0.5,"fairy":0.5,"grass":2,"psychic":2,"dark":2},
    "rock":     {"fighting":0.5,"ground":0.5,"steel":0.5,"fire":2,"ice":2,"flying":2,"bug":2},
    "ghost":    {"normal":0,"dark":0.5,"psychic":2,"ghost":2},
    "dragon":   {"steel":0.5,"fairy":0,"dragon":2},
    "dark":     {"fighting":0.5,"dark":0.5,"fairy":0.5,"ghost":2,"psychic":2},
    "steel":    {"fire":0.5,"water":0.5,"electric":0.5,"steel":0.5,"ice":2,"rock":2,"fairy":2},
    "fairy":    {"fire":0.5,"poison":0.5,"steel":0.5,"fighting":2,"dragon":2,"dark":2},
}

def type_mult(move_type: str, def_types: list[str]) -> float:
    chart = TYPE_CHART.get(move_type, {})
    m = 1.0
    for t in def_types:
        m *= chart.get(t, 1.0)
    return m

def eff_text(mult: float) -> str:
    if mult == 0:  return "It had no effect... 😶"
    if mult >= 4:  return "It's super effective!! 💥💥"
    if mult >= 2:  return "It's super effective! 💥"
    if mult < 1:   return "It's not very effective... 😬"
    return ""

# ─────────────────────────────────────────────────────────────────
# MOVES WITH SIDE EFFECTS
# ─────────────────────────────────────────────────────────────────

STATUS_MOVES: dict[str, dict] = {
    "flamethrower":   {"status": "burn",       "chance": 10, "target": "opponent"},
    "fire-blast":     {"status": "burn",       "chance": 10, "target": "opponent"},
    "lava-plume":     {"status": "burn",       "chance": 30, "target": "opponent"},
    "scald":          {"status": "burn",       "chance": 30, "target": "opponent"},
    "will-o-wisp":    {"status": "burn",       "chance": 100,"target": "opponent"},
    "fire-punch":     {"status": "burn",       "chance": 10, "target": "opponent"},
    "thunder":        {"status": "paralysis",  "chance": 30, "target": "opponent"},
    "thunderbolt":    {"status": "paralysis",  "chance": 10, "target": "opponent"},
    "thunder-wave":   {"status": "paralysis",  "chance": 100,"target": "opponent"},
    "body-slam":      {"status": "paralysis",  "chance": 30, "target": "opponent"},
    "discharge":      {"status": "paralysis",  "chance": 30, "target": "opponent"},
    "glare":          {"status": "paralysis",  "chance": 100,"target": "opponent"},
    "stun-spore":     {"status": "paralysis",  "chance": 100,"target": "opponent"},
    "sludge-bomb":    {"status": "poison",     "chance": 30, "target": "opponent"},
    "sludge-wave":    {"status": "poison",     "chance": 10, "target": "opponent"},
    "poison-jab":     {"status": "poison",     "chance": 30, "target": "opponent"},
    "toxic":          {"status": "toxic",      "chance": 100,"target": "opponent"},
    "poison-sting":   {"status": "poison",     "chance": 30, "target": "opponent"},
    "spore":          {"status": "sleep",      "chance": 100,"target": "opponent"},
    "sleep-powder":   {"status": "sleep",      "chance": 75, "target": "opponent"},
    "hypnosis":       {"status": "sleep",      "chance": 60, "target": "opponent"},
    "dark-void":      {"status": "sleep",      "chance": 50, "target": "opponent"},
    "blizzard":       {"status": "freeze",     "chance": 10, "target": "opponent"},
    "ice-beam":       {"status": "freeze",     "chance": 10, "target": "opponent"},
    "ice-punch":      {"status": "freeze",     "chance": 10, "target": "opponent"},
    "powder-snow":    {"status": "freeze",     "chance": 10, "target": "opponent"},
}

FLINCH_MOVES: dict[str, int] = {
    "fake-out": 100, "air-slash": 30, "iron-head": 30, "rock-slide": 30,
    "headbutt": 30, "stomp": 30, "bite": 30, "dark-pulse": 20,
    "waterfall": 20, "zen-headbutt": 20, "dragon-rush": 20, "twister": 20,
    "snore": 30, "icicle-crash": 30, "hyper-fang": 10,
}

MOVE_ACCURACY: dict[str, int | None] = {
    "blizzard": 70,       "thunder": 70,        "fire-blast": 85,     
    "focus-blast": 70,    "stone-edge": 80,     "dynamic-punch": 50,
    "inferno": 50,        "zap-cannon": 50,     "hypnosis": 60,       
    "sleep-powder": 75,   "dark-void": 50,      "stun-spore": 75,
    "will-o-wisp": 85,    "toxic": 90,          "hydro-pump": 80,     
    "blaze-kick": 90,     "poison-powder": 75,  "sing": 55,
    "supersonic": 55,     "confuse-ray": 100,   "glare": 100,         
    "thunder-wave": 90,   "spore": 100,         "earthquake": 100,
    "surf": 100,          "flamethrower": 100,  "thunderbolt": 100,   
    "ice-beam": 100,      "psychic": 100,       "shadow-ball": 100,
    "energy-ball": 100,   "sludge-bomb": 100,   "flash-cannon": 100,  
    "cross-chop": 80,     "megahorn": 85,       "petal-blizzard": 100,
    "draco-meteor": 90,   "hurricane": 70,
}

def get_accuracy(move_name: str) -> int | None:
    slug = move_name.lower().replace(" ", "-")
    return MOVE_ACCURACY.get(slug, None)

def hits(move_name: str, atk_accuracy_mod: float = 1.0, def_evasion_mod: float = 1.0) -> bool:
    acc = get_accuracy(move_name)
    if acc is None:
        return True
    roll = random.randint(1, 100)
    adjusted = acc * atk_accuracy_mod / def_evasion_mod
    return roll <= adjusted

# ─────────────────────────────────────────────────────────────────
# STATUS CONDITIONS
# ─────────────────────────────────────────────────────────────────

STATUS_ICONS = {
    "burn": "🔥 BRN", "paralysis": "⚡ PAR", "poison": "☠️ PSN",
    "toxic": "💜 TOX", "sleep": "💤 SLP", "freeze": "🧊 FRZ",
}

def status_icon(status: str) -> str:
    return STATUS_ICONS.get(status, "")

def apply_status_effects(state: "BattleState", p_idx: int, log: list[str]) -> bool:
    poke   = state.pokemon[p_idx]
    status = state.statuses[p_idx]

    if status == "paralysis":
        if random.randint(1, 4) == 1:
            log.append(f"⚡ **{poke['display']}** is fully paralyzed and can't move!")
            return False
    if status == "sleep":
        turns_left = state.sleep_turns[p_idx]
        if turns_left > 0:
            state.sleep_turns[p_idx] -= 1
            log.append(f"💤 **{poke['display']}** is fast asleep!")
            return False
        else:
            state.statuses[p_idx] = None
            log.append(f"😴 **{poke['display']}** woke up!")
    if status == "freeze":
        if random.randint(1, 5) == 1:
            state.statuses[p_idx] = None
            log.append(f"🧊 **{poke['display']}** thawed out!")
        else:
            log.append(f"🧊 **{poke['display']}** is frozen solid and can't move!")
            return False
    return True

def apply_end_of_turn(state: "BattleState", p_idx: int, log: list[str]):
    poke   = state.pokemon[p_idx]
    status = state.statuses[p_idx]
    max_hp = state.max_hp[p_idx]

    if status == "burn":
        dmg = max(1, max_hp // 16)
        state.cur_hp[p_idx] = max(0, state.cur_hp[p_idx] - dmg)
        log.append(f"🔥 **{poke['display']}** is hurt by its burn! (-{dmg} HP)")
    elif status == "poison":
        dmg = max(1, max_hp // 8)
        state.cur_hp[p_idx] = max(0, state.cur_hp[p_idx] - dmg)
        log.append(f"☠️ **{poke['display']}** is hurt by poison! (-{dmg} HP)")
    elif status == "toxic":
        state.toxic_counter[p_idx] = min(state.toxic_counter[p_idx] + 1, 15)
        dmg = max(1, (max_hp * state.toxic_counter[p_idx]) // 16)
        state.cur_hp[p_idx] = max(0, state.cur_hp[p_idx] - dmg)
        log.append(f"💜 **{poke['display']}** is badly poisoned! (-{dmg} HP)")

def try_inflict_status(state: "BattleState", move_name: str, atk_idx: int, def_idx: int, log: list[str]):
    slug = move_name.lower().replace(" ", "-")
    entry = STATUS_MOVES.get(slug)
    if not entry: return

    target_idx = def_idx if entry["target"] == "opponent" else atk_idx
    if state.statuses[target_idx] is not None: return

    target_types = state.pokemon[target_idx]["types"]
    new_status   = entry["status"]

    immune = False
    if new_status == "burn" and "fire" in target_types: immune = True
    if new_status == "paralysis" and "electric" in target_types: immune = True
    if new_status in ("poison", "toxic") and ("poison" in target_types or "steel" in target_types): immune = True
    if immune: return

    if random.randint(1, 100) <= entry["chance"]:
        state.statuses[target_idx] = new_status
        if new_status == "sleep": state.sleep_turns[target_idx] = random.randint(1, 3)
        if new_status == "toxic": state.toxic_counter[target_idx] = 0
        log.append(f"{status_icon(new_status)} **{state.pokemon[target_idx]['display']}** was inflicted with **{new_status.upper()}**!")

def try_flinch(state: "BattleState", move_name: str, atk_idx: int, def_idx: int, log: list[str]):
    slug  = move_name.lower().replace(" ", "-")
    chance = FLINCH_MOVES.get(slug, 0)
    if chance and random.randint(1, 100) <= chance:
        state.flinched[def_idx] = True

# ─────────────────────────────────────────────────────────────────
# STATS & DAMAGE
# ─────────────────────────────────────────────────────────────────

def apply_level_100_stats(poke_data: dict) -> dict:
    new_stats = {}
    for stat, base in poke_data["stats"].items():
        if stat == "hp": new_stats[stat] = 2 * base + 162
        else: new_stats[stat] = 2 * base + 57
    poke_data["stats"] = new_stats
    return poke_data

def calc_damage(atk_poke: dict, move: dict, def_poke: dict, atk_status: str | None = None) -> tuple[int, float]:
    if move["power"] == 0: return 0, 1.0

    if move["category"] == "special":
        A = atk_poke["stats"].get("special-attack",  80)
        D = def_poke["stats"].get("special-defense", 80)
    else:
        A = atk_poke["stats"].get("attack",   80)
        D = def_poke["stats"].get("defense",  80)

    if atk_status == "burn" and move["category"] == "physical":
        A = A // 2

    stab = 1.5 if move["type"] in atk_poke["types"] else 1.0
    tm   = type_mult(move["type"], def_poke["types"])
    rand = random.uniform(0.85, 1.0)
    raw  = ((2 * 100 / 5 + 2) * move["power"] * A / D / 50 + 2)
    dmg  = int(raw * stab * tm * rand)
    return max(1, dmg), tm

def hp_bar(cur: int, mx: int, length: int = 10) -> str:
    ratio  = max(0.0, cur / mx)
    filled = round(ratio * length)
    bar    = "█" * filled + "░" * (length - filled)
    pct    = round(ratio * 100)
    icon   = "🟩" if pct > 50 else ("🟨" if pct > 20 else "🟥")
    return f"{icon} `{bar}` **{cur}/{mx} HP**"

def small_hp_bar(cur: int, mx: int, length: int = 6) -> str:
    if mx == 0: return "💀"
    ratio  = max(0.0, cur / mx)
    filled = round(ratio * length)
    bar    = "█" * filled + "░" * (length - filled)
    pct    = round(ratio * 100)
    icon   = "🟩" if pct > 50 else ("🟨" if pct > 20 else "🟥")
    return f"{icon}`{bar}`"

# ─────────────────────────────────────────────────────────────────
# BATTLE STATE
# ─────────────────────────────────────────────────────────────────

class BattleState:
    def __init__(self, p0: discord.Member, p1: discord.Member,
                 poke0: dict, poke1: dict, team0: list[dict], team1: list[dict], bet: int):
        self.players   = [p0, p1]
        self.pokemon   = [poke0, poke1]
        self.teams     = [team0, team1]
        self.max_hp    = [poke0["stats"]["hp"], poke1["stats"]["hp"]]
        self.cur_hp    = [poke0["stats"]["hp"], poke1["stats"]["hp"]]
        self.team_hp: list[list] = [
            [[pk["stats"]["hp"], pk["stats"]["hp"]] for pk in team0],
            [[pk["stats"]["hp"], pk["stats"]["hp"]] for pk in team1],
        ]
        self.revealed: list[list[bool]] = [[False] * len(team0), [False] * len(team1)]
        self._reveal(0, poke0["name"])
        self._reveal(1, poke1["name"])

        self.bet        = bet
        self.turn_num   = 1
        self.log        = ""
        self.actions: dict = {}
        self.main_msg   = None

        self.statuses: list[str | None]  = [None, None]
        self.sleep_turns: list[int]      = [0, 0]
        self.toxic_counter: list[int]    = [0, 0]
        self.flinched: list[bool]        = [False, False]
        self.turns_out: list[int]        = [0, 0]

    def _reveal(self, p_idx: int, name: str):
        for i, pk in enumerate(self.teams[p_idx]):
            if pk["name"] == name: self.revealed[p_idx][i] = True

    def _team_slot(self, p_idx: int, name: str) -> int | None:
        for i, pk in enumerate(self.teams[p_idx]):
            if pk["name"] == name: return i
        return None

    def deal(self, p_idx: int, dmg: int):
        self.cur_hp[p_idx] = max(0, self.cur_hp[p_idx] - dmg)
        slot = self._team_slot(p_idx, self.pokemon[p_idx]["name"])
        if slot is not None: self.team_hp[p_idx][slot][0] = self.cur_hp[p_idx]

    def winner(self) -> int | None:
        for p in range(2):
            if all(self.team_hp[p][i][0] <= 0 for i in range(len(self.teams[p]))):
                return 1 - p
        return None

    def switch(self, p_idx: int, new_poke: dict):
        old_slot = self._team_slot(p_idx, self.pokemon[p_idx]["name"])
        if old_slot is not None: self.team_hp[p_idx][old_slot][0] = self.cur_hp[p_idx]

        self.pokemon[p_idx] = new_poke
        new_slot = self._team_slot(p_idx, new_poke["name"])
        if new_slot is not None:
            self.cur_hp[p_idx] = self.team_hp[p_idx][new_slot][0]
            self.max_hp[p_idx] = self.team_hp[p_idx][new_slot][1]
            self.revealed[p_idx][new_slot] = True

        self.flinched[p_idx] = False
        self.turns_out[p_idx] = 0


# ─────────────────────────────────────────────────────────────────
# VIEWS & EMBEDS
# ─────────────────────────────────────────────────────────────────

def team_panel(state: BattleState, viewer_idx: int) -> str:
    lines = ["**Your team:**"]
    opp_idx = 1 - viewer_idx
    for i, pk in enumerate(state.teams[viewer_idx]):
        hp_c, hp_m = state.team_hp[viewer_idx][i]
        bar  = small_hp_bar(hp_c, hp_m)
        active = " ◄" if pk["name"] == state.pokemon[viewer_idx]["name"] else ""
        st = state.statuses[viewer_idx] if pk["name"] == state.pokemon[viewer_idx]["name"] else ""
        st_txt = f" {status_icon(st)}" if st else ""
        fainted = " 💀" if hp_c <= 0 else ""
        lines.append(f"`{pk['display']:12}` {bar}{st_txt}{fainted}{active}")

    lines.append("\n**Opponent's team:**")
    for i, pk in enumerate(state.teams[opp_idx]):
        if not state.revealed[opp_idx][i]:
            lines.append(f"`{'???':12}` ❔ Not yet revealed")
        else:
            hp_c, hp_m = state.team_hp[opp_idx][i]
            bar  = small_hp_bar(hp_c, hp_m)
            active = " ◄" if pk["name"] == state.pokemon[opp_idx]["name"] else ""
            st = state.statuses[opp_idx] if pk["name"] == state.pokemon[opp_idx]["name"] else ""
            st_txt = f" {status_icon(st)}" if st else ""
            fainted = " 💀" if hp_c <= 0 else ""
            lines.append(f"`{pk['display']:12}` {bar}{st_txt}{fainted}{active}")
    return "\n".join(lines)

def battle_embed(state: BattleState, *, title="⚔️ Pokémon Battle", color=0x5865F2, final=False) -> discord.Embed:
    p0, p1   = state.players
    pk0, pk1 = state.pokemon
    h0, h1   = state.cur_hp
    m0, m1   = state.max_hp

    embed = discord.Embed(title=title, color=color)
    st0 = f"  {status_icon(state.statuses[0])}" if state.statuses[0] else ""
    st1 = f"  {status_icon(state.statuses[1])}" if state.statuses[1] else ""

    embed.add_field(name=f"{p0.display_name}  —  {pk0['display']}{st0}", value=hp_bar(h0, m0), inline=False)
    embed.add_field(name=f"{p1.display_name}  —  {pk1['display']}{st1}", value=hp_bar(h1, m1), inline=False)

    if state.log:
        embed.add_field(name="📢 Turn Log", value=state.log[:1024], inline=False)
    if state.bet:
        embed.add_field(name="💰 Pot", value=f"🪙 {format_cash(state.bet * 2)}", inline=True)

    if not final:
        waiting = 2 - len(state.actions)
        embed.set_footer(text=f"⏳ Turn {state.turn_num}  •  Waiting for {waiting} trainer{'s' if waiting != 1 else ''}...")

    embed.set_image(url="attachment://battle.png")
    return embed


class ForcedSwitchView(discord.ui.View):
    """View used to interrupt the battle loop and force a player to pick a new Pokémon."""
    def __init__(self, state: BattleState, p_idx: int):
        super().__init__(timeout=120)
        self.state = state
        self.p_idx = p_idx
        self.chosen_poke = None
        
        opts = []
        for pk in self.state.teams[p_idx]:
            if pk["name"] == self.state.pokemon[p_idx]["name"]:
                continue
            slot = self.state._team_slot(p_idx, pk["name"])
            if slot is None: continue
            hp_cur = self.state.team_hp[p_idx][slot][0]
            hp_max = self.state.team_hp[p_idx][slot][1]
            if hp_cur > 0:
                opts.append(discord.SelectOption(
                    label=pk["display"],
                    description=f"HP: {hp_cur}/{hp_max}",
                    value=pk["name"]
                ))
                
        p_name = self.state.players[p_idx].display_name
        sel = discord.ui.Select(placeholder=f"⚠️ {p_name}, choose your next Pokémon...", options=opts)
        sel.callback = self.cb
        self.add_item(sel)
        
    async def cb(self, interaction: discord.Interaction):
        if interaction.user.id != self.state.players[self.p_idx].id:
            return await interaction.response.send_message("❌ Not your turn!", ephemeral=True)
        val = interaction.data["values"][0]
        self.chosen_poke = next(p for p in self.state.teams[self.p_idx] if p["name"] == val)
        await interaction.response.send_message("✅ Switch confirmed! Resuming battle...", ephemeral=True)
        self.stop()
        
    async def on_timeout(self):
        # Auto-pick if they go AFK to prevent a softlock
        for pk in self.state.teams[self.p_idx]:
            if pk["name"] == self.state.pokemon[self.p_idx]["name"]: continue
            slot = self.state._team_slot(self.p_idx, pk["name"])
            if self.state.team_hp[self.p_idx][slot][0] > 0:
                self.chosen_poke = pk
                break
        self.stop()


class MainBattleView(discord.ui.View):
    def __init__(self, state, cog):
        super().__init__(timeout=120)
        self.state = state
        self.cog   = cog

        p0_name = self.state.players[0].display_name
        p1_name = self.state.players[1].display_name

        p0_moves = self._build_move_opts(0)
        sel_m0 = discord.ui.Select(placeholder=f"🔴 {p0_name}'s Moves...", options=p0_moves, row=0)
        sel_m0.callback = self._cb_m0
        self.add_item(sel_m0)

        p0_switches = self._build_switch_opts(0)
        if p0_switches:
            sel_s0 = discord.ui.Select(placeholder=f"🔄 {p0_name}'s Team...", options=p0_switches, row=1)
            sel_s0.callback = self._cb_s0
            self.add_item(sel_s0)

        p1_moves = self._build_move_opts(1)
        sel_m1 = discord.ui.Select(placeholder=f"🔵 {p1_name}'s Moves...", options=p1_moves, row=2)
        sel_m1.callback = self._cb_m1
        self.add_item(sel_m1)

        p1_switches = self._build_switch_opts(1)
        if p1_switches:
            sel_s1 = discord.ui.Select(placeholder=f"🔄 {p1_name}'s Team...", options=p1_switches, row=3)
            sel_s1.callback = self._cb_s1
            self.add_item(sel_s1)

        btn_team = discord.ui.Button(label="📊 Team Status", style=discord.ButtonStyle.secondary, row=4)
        btn_team.callback = self.btn_team
        self.add_item(btn_team)

        btn_sur = discord.ui.Button(label="🏳️ Surrender", style=discord.ButtonStyle.danger, row=4)
        btn_sur.callback = self.btn_surrender
        self.add_item(btn_sur)

    def _build_move_opts(self, p_idx):
        opts = []
        for m in self.state.pokemon[p_idx]["moves"]:
            prio = get_priority(m["name"])
            acc  = get_accuracy(m["name"])
            acc_str  = f" | Acc: {acc}%" if acc is not None else " | Acc: —"
            prio_str = f" | Prio +{prio}" if prio > 0 else (f" | Prio {prio}" if prio < 0 else "")
            pwr  = f"⚡{m['power']}" if m["power"] else "Status"
            
            has_flinch = m["name"].lower().replace(" ","-") in FLINCH_MOVES
            has_status = m["name"].lower().replace(" ","-") in STATUS_MOVES
            tags = ""
            if has_flinch: tags += " 😵"
            if has_status: tags += " 🌡"
            
            opts.append(discord.SelectOption(
                label=f"{m['display']}{tags}",
                description=f"{m['type'].title()} • {pwr}{acc_str}{prio_str}",
                value=m["name"]
            ))
        return opts

    def _build_switch_opts(self, p_idx):
        opts = []
        for pk in self.state.teams[p_idx]:
            if pk["name"] == self.state.pokemon[p_idx]["name"]:
                continue
            slot = self.state._team_slot(p_idx, pk["name"])
            if slot is None:
                continue
            hp_cur = self.state.team_hp[p_idx][slot][0]
            hp_max = self.state.team_hp[p_idx][slot][1]
            if hp_cur > 0:
                opts.append(discord.SelectOption(
                    label=pk["display"],
                    description=f"HP: {hp_cur}/{hp_max}",
                    value=pk["name"]
                ))
        return opts

    async def _process_action(self, interaction: discord.Interaction, p_idx: int, act_type: str, val: str):
        if interaction.user.id != self.state.players[p_idx].id:
            return await interaction.response.send_message("❌ Use your own dropdown menus!", ephemeral=True)
            
        if interaction.user.id in self.state.actions:
            return await interaction.response.send_message("✅ You already locked in your action!", ephemeral=True)

        if act_type == "move":
            data = next(m for m in self.state.pokemon[p_idx]["moves"] if m["name"] == val)
        else:
            data = next(p for p in self.state.teams[p_idx] if p["name"] == val)

        self.state.actions[interaction.user.id] = {"type": act_type, "data": data}
        await interaction.response.send_message("✅ Action locked in! Waiting for opponent...", ephemeral=True)

        if len(self.state.actions) == 2:
            await self.cog.resolve_turn(self.state)
        else:
            try:
                await self.state.main_msg.edit(embed=battle_embed(self.state))
            except Exception:
                pass

    async def _cb_m0(self, interaction): await self._process_action(interaction, 0, "move", interaction.data["values"][0])
    async def _cb_s0(self, interaction): await self._process_action(interaction, 0, "switch", interaction.data["values"][0])
    async def _cb_m1(self, interaction): await self._process_action(interaction, 1, "move", interaction.data["values"][0])
    async def _cb_s1(self, interaction): await self._process_action(interaction, 1, "switch", interaction.data["values"][0])

    async def btn_team(self, interaction: discord.Interaction):
        if interaction.user not in self.state.players:
            return await interaction.response.send_message("You're not in this battle!", ephemeral=True)
        p_idx = 0 if interaction.user.id == self.state.players[0].id else 1
        panel = team_panel(self.state, p_idx)
        await interaction.response.send_message(panel, ephemeral=True)

    async def btn_surrender(self, interaction: discord.Interaction):
        if interaction.user not in self.state.players:
            return await interaction.response.send_message("You're not in this battle!", ephemeral=True)
        self.stop()
        await interaction.response.defer()
        winner_idx = 1 if interaction.user.id == self.state.players[0].id else 0
        await self.cog.end_battle(self.state.main_msg, self.state, winner_idx, surrendered=True)

    async def on_timeout(self):
        self.stop()


class PokemonPickView(discord.ui.View):
    def __init__(self, challenger, opponent, ch_team, op_team, bet, cog):
        super().__init__(timeout=60)
        self.challenger = challenger
        self.opponent   = opponent
        self.ch_team    = ch_team
        self.op_team    = op_team
        self.bet        = bet
        self.cog        = cog
        self.ch_pick    = None
        self.op_pick    = None
        self.add_item(self._make_select(challenger, ch_team, "ch"))
        self.add_item(self._make_select(opponent,   op_team, "op"))

    def _make_select(self, player, team, tag):
        opts = [discord.SelectOption(label=n.title(), value=n) for n in team]
        sel  = discord.ui.Select(placeholder=f"{player.display_name}: pick your lead Pokémon", options=opts, custom_id=tag)
        async def cb(interaction: discord.Interaction):
            val = interaction.data["values"][0]
            if interaction.custom_id == "ch":
                if interaction.user.id != self.challenger.id:
                    return await interaction.response.send_message("Use your own dropdown!", ephemeral=True)
                self.ch_pick = val
            else:
                if interaction.user.id != self.opponent.id:
                    return await interaction.response.send_message("Use your own dropdown!", ephemeral=True)
                self.op_pick = val
            await interaction.response.send_message("✅ Lead locked in!", ephemeral=True)
            if self.ch_pick and self.op_pick:
                self.stop()
                await self.cog.start_battle(
                    interaction.message, self.challenger, self.opponent,
                    self.ch_team, self.op_team, self.ch_pick, self.op_pick, self.bet,
                )
        sel.callback = cb
        return sel

class ChallengeView(discord.ui.View):
    def __init__(self, challenger, opponent, bet, cog):
        super().__init__(timeout=30)
        self.challenger = challenger
        self.opponent   = opponent
        self.bet        = bet
        self.cog        = cog

    @discord.ui.button(label="✅ Accept", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, _):
        if interaction.user != self.opponent:
            return await interaction.response.send_message("Not your challenge!", ephemeral=True)
        self.stop()
        await interaction.response.defer()
        await self.cog.on_accepted(interaction.message, self.challenger, self.opponent, self.bet)

    @discord.ui.button(label="❌ Decline", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, _):
        if interaction.user not in (self.opponent, self.challenger):
            return await interaction.response.send_message("Not your challenge!", ephemeral=True)
        self.stop()
        await interaction.message.edit(
            embed=discord.Embed(description=f"**{self.opponent.display_name}** declined the battle. 💨", color=0xED4245), view=None)


# ─────────────────────────────────────────────────────────────────
# COG
# ─────────────────────────────────────────────────────────────────

async def _edit_with_image(msg, embed, view=None, state=None, content=None):
    """Edit a message replacing the image with a freshly rendered battle scene."""
    try:
        kwargs = {"embed": embed}
        if content is not None:
            kwargs["content"] = content
        else:
            kwargs["content"] = "" 
            
        if state is not None:
            battle_file = await make_battle_file(state)
            kwargs["attachments"] = [battle_file]
            
        kwargs["view"] = view
        await msg.edit(**kwargs)
    except Exception as e:
        kwargs = {"embed": embed}
        if content is not None: kwargs["content"] = content
        else: kwargs["content"] = ""
        kwargs["view"] = view
        await msg.edit(**kwargs)

class PokemonBattle(commands.Cog):
    def __init__(self, bot):
        self.bot    = bot
        self.active: dict[int, BattleState] = {}

    @commands.command(name="battle")
    async def battle(self, ctx, opponent: discord.Member = None, amount: str = None):
        if opponent is None:
            return await ctx.send(embed=discord.Embed(description="❌ Usage: `.battle @user <amount>`", color=0xED4245))
        if opponent == ctx.author or opponent.bot:
            return await ctx.send(embed=discord.Embed(description="❌ Invalid opponent.", color=0xED4245))
        if ctx.channel.id in self.active:
            return await ctx.send(embed=discord.Embed(description="❌ A battle is already active here!", color=0xED4245))

        from utils.economy import parse_amount as _pa
        bet = 0
        if amount:
            cash = get_cash(ctx.author.id)
            bet  = _pa(amount, cash)
            if bet is None or bet <= 0:
                return await ctx.send(embed=discord.Embed(description="❌ Invalid bet.", color=0xED4245))

        ch_team = get_team(str(ctx.author.id))
        op_team = get_team(str(opponent.id))
        if not ch_team:
            return await ctx.send(embed=discord.Embed(description=f"❌ **{ctx.author.display_name}** has no team! Use `.team`", color=0xED4245))
        if not op_team:
            return await ctx.send(embed=discord.Embed(description=f"❌ **{opponent.display_name}** has no team!", color=0xED4245))

        if bet > 0:
            if get_cash(ctx.author.id) < bet:
                return await ctx.send(embed=discord.Embed(description=f"❌ **{ctx.author.display_name}** can't afford that.", color=0xED4245))
            if get_cash(opponent.id) < bet:
                return await ctx.send(embed=discord.Embed(description=f"❌ **{opponent.display_name}** can't afford that.", color=0xED4245))

        bet_txt = f"🪙 **{format_cash(bet)}** each" if bet else "For glory (no bet)"
        embed = discord.Embed(
            title="⚔️ Battle Challenge!",
            description=f"{ctx.author.mention} challenges {opponent.mention}!\n\n💰 Wager: {bet_txt}\n\n{opponent.mention}, do you accept?",
            color=0xF1C40F,
        )
        embed.set_footer(text="30 seconds to respond.")
        await ctx.send(embed=embed, view=ChallengeView(ctx.author, opponent, bet, self))

    async def on_accepted(self, msg, challenger, opponent, bet):
        ch_team = get_team(str(challenger.id))
        op_team = get_team(str(opponent.id))
        embed = discord.Embed(
            title="⚔️ Battle Starting!",
            description="Both trainers — pick your **lead Pokémon** below!\n*(Hidden from your opponent 🤫)*",
            color=0x5865F2,
        )
        await msg.edit(embed=embed, view=PokemonPickView(challenger, opponent, ch_team, op_team, bet, self))

    async def start_battle(self, msg, challenger, opponent, ch_team_names, op_team_names, ch_lead, op_lead, bet):
        await msg.edit(embed=discord.Embed(description="⏳ Loading Pokémon data...", color=0x5865F2), view=None)

        async def load_team(names, uid):
            result = []
            for name in names:
                data = await fetch_pokemon_data(name, uid)
                if data:
                    data = apply_level_100_stats(data)
                    result.append(data)
            return result

        ch_full = await load_team(ch_team_names, str(challenger.id))
        op_full = await load_team(op_team_names, str(opponent.id))

        ch_poke = next((p for p in ch_full if p["name"] == ch_lead), ch_full[0] if ch_full else None)
        op_poke = next((p for p in op_full if p["name"] == op_lead), op_full[0] if op_full else None)

        if not ch_poke or not op_poke:
            return await msg.edit(embed=discord.Embed(description="❌ Failed to load Pokémon data. Try again.", color=0xED4245))

        if bet > 0:
            remove_cash(challenger.id, bet)
            remove_cash(opponent.id, bet)

        state          = BattleState(challenger, opponent, ch_poke, op_poke, ch_full, op_full, bet)
        state.main_msg = msg
        self.active[msg.channel.id] = state

        state.log = (
            f"**{challenger.display_name}** sent out **{ch_poke['display']}**!\n"
            f"**{opponent.display_name}** sent out **{op_poke['display']}**!\n\n"
            f"Both trainers: Select your move directly below!"
        )
        await _edit_with_image(msg, battle_embed(state), MainBattleView(state, self), state)

    async def prompt_forced_switch(self, state, p_idx, reason="fainted"):
        """Pauses the battle loop to force a player to pick a new pokemon."""
        has_bench = any(
            state.team_hp[p_idx][i][0] > 0 
            for i, pk in enumerate(state.teams[p_idx]) 
            if pk["name"] != state.pokemon[p_idx]["name"]
        )
        if not has_bench:
            return False
            
        view = ForcedSwitchView(state, p_idx)
        msg_content = f"⚠️ {state.players[p_idx].mention}, your active Pokémon {reason}! You must swap."
        
        try:
            await _edit_with_image(state.main_msg, battle_embed(state), view, state, content=msg_content)
        except Exception:
            pass
            
        await view.wait() # <--- This pauses the battle loop until they pick!
        
        if view.chosen_poke:
            state.switch(p_idx, view.chosen_poke)
            return True
        return False

    # ── TURN RESOLUTION ───────────────────────────────────────────

    async def resolve_turn(self, state: BattleState):
        p0_id = state.players[0].id
        p1_id = state.players[1].id

        a0 = state.actions[p0_id]
        a1 = state.actions[p1_id]

        def speed_score(p_idx, action):
            if action["type"] == "switch": return 1_000_000
            prio = get_priority(action["data"]["name"])
            spd  = state.pokemon[p_idx]["stats"].get("speed", 80)
            if state.statuses[p_idx] == "paralysis": spd = spd // 2
            return (prio * 10_000) + spd

        s0 = speed_score(0, a0)
        s1 = speed_score(1, a1)

        if s0 > s1:   order = [0, 1]
        elif s1 > s0: order = [1, 0]
        else:         order = random.choice([[0, 1], [1, 0]])

        log_lines = []

        for p_idx in order:
            other = 1 - p_idx
            action = state.actions[state.players[p_idx].id]

            if state.cur_hp[p_idx] <= 0:
                continue

            # ── SWITCH ───────────────────────────────────────────
            if action["type"] == "switch":
                new_poke = action["data"]
                state.switch(p_idx, new_poke)
                state.flinched[p_idx]  = False
                state.turns_out[p_idx] = 0
                log_lines.append(f"🔄 **{state.players[p_idx].display_name}** sent out **{new_poke['display']}**!")
                continue

            # ── MOVE ─────────────────────────────────────────────
            move = action["data"]

            if move["name"].lower().replace(" ", "-") == "fake-out" and state.turns_out[p_idx] > 0:
                log_lines.append(f"💨 **{state.pokemon[p_idx]['display']}**'s Fake Out failed! *(only works on first turn out)*")
                continue

            if state.flinched[p_idx]:
                state.flinched[p_idx] = False
                log_lines.append(f"😵 **{state.pokemon[p_idx]['display']}** flinched and couldn't move!")
                continue

            can_move = apply_status_effects(state, p_idx, log_lines)
            if not can_move: continue

            if state.cur_hp[other] <= 0: continue

            if not hits(move["name"]):
                log_lines.append(f"💨 **{state.pokemon[p_idx]['display']}** used **{move['display']}** — but it missed!")
                continue

            dmg, tm = calc_damage(state.pokemon[p_idx], move, state.pokemon[other], atk_status=state.statuses[p_idx])
            state.deal(other, dmg)

            eff = eff_text(tm)
            if move["power"] == 0:
                log_lines.append(f"✨ **{state.pokemon[p_idx]['display']}** used **{move['display']}**!")
            else:
                log_lines.append(f"⚔️ **{state.pokemon[p_idx]['display']}** used **{move['display']}** → **{dmg} damage**!")
            if eff: log_lines.append(f"└ {eff}")

            try_inflict_status(state, move["name"], p_idx, other, log_lines)
            if other not in [order.index(p_idx) + 1]: 
                try_flinch(state, move["name"], p_idx, other, log_lines)

            if state.cur_hp[other] <= 0:
                log_lines.append(f"💀 **{state.pokemon[other]['display']}** fainted!")

            # ── PIVOT LOGIC (Volt Switch / U-Turn) ──────────────
            is_pivot = move["name"].lower().replace(" ", "-") in ["u-turn", "volt-switch", "flip-turn", "baton-pass", "parting-shot", "teleport"]
            if is_pivot and state.cur_hp[p_idx] > 0:
                state.log = "\n".join(log_lines)
                log_lines.clear()
                switched = await self.prompt_forced_switch(state, p_idx, reason="is pivoting out")
                if switched:
                    log_lines.append(f"🔄 **{state.players[p_idx].display_name}** pivoted to **{state.pokemon[p_idx]['display']}**!")

        # ── END OF TURN ───────────────────────────────────────────
        for p_idx in [0, 1]:
            if state.cur_hp[p_idx] > 0:
                apply_end_of_turn(state, p_idx, log_lines)
                if state.cur_hp[p_idx] <= 0:
                    log_lines.append(f"💀 **{state.pokemon[p_idx]['display']}** fainted from status!")

        # ── DEAD POKEMON FORCED SWITCH LOOP ───────────────────────
        for p_idx in [0, 1]:
            if state.cur_hp[p_idx] <= 0:
                has_bench = any(state.team_hp[p_idx][i][0] > 0 for i, pk in enumerate(state.teams[p_idx]))
                if has_bench:
                    state.log = "\n".join(log_lines)
                    log_lines.clear()
                    switched = await self.prompt_forced_switch(state, p_idx, reason="fainted")
                    if switched:
                        log_lines.append(f"🔄 **{state.players[p_idx].display_name}** sent out **{state.pokemon[p_idx]['display']}**!")

        state.turns_out[0] += 1
        state.turns_out[1] += 1

        if log_lines:
            if state.log: state.log += "\n" + "\n".join(log_lines)
            else: state.log = "\n".join(log_lines)

        state.actions.clear()
        state.turn_num += 1

        w = state.winner()
        if w is not None:
            await self.end_battle(state.main_msg, state, w)
        else:
            await _edit_with_image(state.main_msg, battle_embed(state), MainBattleView(state, self), state, content=None)

    async def end_battle(self, msg, state: BattleState, winner_idx: int, surrendered: bool = False):
        self.active.pop(msg.channel.id, None)
        winner = state.players[winner_idx]
        loser  = state.players[1 - winner_idx]

        if state.bet > 0: add_cash(winner.id, state.bet * 2)

        embed = battle_embed(state, title="🏆 Battle Over!", color=0xF1C40F, final=True)
        lines = []
        if surrendered: lines.append(f"🏳️ **{loser.display_name}** surrendered!")
        else: lines.append(f"💀 **{state.pokemon[1 - winner_idx]['display']}** was defeated!")
        lines.append(f"🏆 **{winner.display_name}** wins!")
        if state.bet > 0: lines.append(f"💰 Prize: 🪙 **{format_cash(state.bet * 2)}**")

        embed.add_field(name="Result", value="\n".join(lines), inline=False)
        try:
            battle_file = await make_battle_file(state)
            await msg.edit(embed=embed, view=None, attachments=[battle_file], content=None)
        except Exception:
            embed.set_image(url=gif_url(state.pokemon[winner_idx]["name"]))
            await msg.edit(embed=embed, view=None, content=None)

async def setup(bot):
    await bot.add_cog(PokemonBattle(bot))
