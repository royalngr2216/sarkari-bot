# ─────────────────────────
# COMMON ACHIEVEMENTS
# ─────────────────────────

COMMON_ACHIEVEMENTS = {

    "hunter_1": {

        "name": "🏹 Hunter I",

        "description": "Hunt 100 times",

        "type": "total_hunts",

        "required": 100,

        "reward": 5_000_000,

        "rarity": "common"
    },

    "miner_1": {

        "name": "⛏ Miner I",

        "description": "Mine 100 times",

        "type": "total_mines",

        "required": 100,

        "reward": 5_000_000,

        "rarity": "common"
    },

    "fisher_1": {

        "name": "🎣 Fisher I",

        "description": "Fish 100 times",

        "type": "total_fishes",

        "required": 100,

        "reward": 5_000_000,

        "rarity": "common"
    },

    "worker_1": {

        "name": "💼 Worker I",

        "description": "Job 100 times",

        "type": "total_jobs",

        "required": 100,

        "reward": 5_000_000,

        "rarity": "common"
    },

    "gambler_1": {

        "name": "🎰 Casual Gambler",

        "description": "Play 500 casino games",

        "type": "games_played",

        "required": 500,

        "reward": 5_000_000,

        "rarity": "common"
    }
}


# ─────────────────────────
# RARE ACHIEVEMENTS
# ─────────────────────────

RARE_ACHIEVEMENTS = {

    "deep_miner": {

        "name": "⛏ Deep Miner",

        "description": "Mine 1000 times",

        "type": "total_mines",

        "required": 1000,

        "reward": "bat_pet",

        "rarity": "rare"
    },

    "corporate_slave": {

        "name": "💼 Corporate Slave",

        "description": "Job 1000 times",

        "type": "total_jobs",

        "required": 1000,

        "reward": "cat_pet",

        "rarity": "rare"
    },

    "sea_predator": {

        "name": "🎣 Sea Predator",

        "description": "Fish 1000 times",

        "type": "total_fishes",

        "required": 1000,

        "reward": "shark_pet",

        "rarity": "rare"
    },

    "apex_hunter": {

        "name": "🏹 Apex Hunter",

        "description": "Hunt 1000 times",

        "type": "total_hunts",

        "required": 1000,

        "reward": "cobra_pet",

        "rarity": "rare"
    },

    "work_empire": {

        "name": "🏭 Work Empire",

        "description": "Own 5 workers",

        "type": "workers_owned",

        "required": 5,

        "reward": 10_000_000,

        "rarity": "rare"
    }
}


# ─────────────────────────
# LEGENDARY ACHIEVEMENTS
# ─────────────────────────

LEGENDARY_ACHIEVEMENTS = {

    "collector": {

        "name": "📦 Collector",

        "description": "Reach 100M inventory value",

        "type": "inventory_value",

        "required": 100_000_000,

        "reward": 10_000_000,

        "rarity": "legendary"
    },

    "gambler": {

        "name": "🎰 Gambler",

        "description": "Win at least 100M from a single bet",

        "type": "biggest_win",

        "required": 100_000_000,

        "reward": 25_000_000,

        "rarity": "legendary"
    },

    "honoured_one": {

        "name": "🐉 Honoured One",

        "description": "Reach 1B net worth",

        "type": "networth",

        "required": 1_000_000_000,

        "reward": "dragon_pet",

        "rarity": "legendary"
    },

    "immortal": {

        "name": "♾ Immortal",

        "description": "Win 20 gambles in a row",

        "type": "gambling_streak",

        "required": 20,

        "reward": 20_000_000,

        "rarity": "legendary"
    },

    "unluckiest_man_alive": {

        "name": "💀 Unluckiest Man Alive",

        "description": "Lose 10 gambles in a row",

        "type": "loss_streak",

        "required": 10,

        "reward": 10_000_000,

        "rarity": "legendary"
    }
}


# ─────────────────────────
# ALL ACHIEVEMENTS
# ─────────────────────────

ALL_ACHIEVEMENTS = {

    **COMMON_ACHIEVEMENTS,

    **RARE_ACHIEVEMENTS,

    **LEGENDARY_ACHIEVEMENTS
}
