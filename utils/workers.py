from datetime import datetime

from utils.economy import (
    economy_collection
)


# ─────────────────────────
# WORKER STATS
# ─────────────────────────

WORKER_LEVELS = {

    1: {
        "income": 200000
    },

    2: {
        "income": 350000
    },

    3: {
        "income": 600000
    },

    4: {
        "income": 850000
    },

    5: {
        "income": 1000000
    }

}

# ─────────────────────────
# WORKER NET WORTH VALUES
# ─────────────────────────

WORKER_VALUES = {

    1: 5_000_000,

    2: 11_000_000,

    3: 18_000_000,

    4: 26_000_000,

    5: 35_000_000
}


# ─────────────────────────
# UPDATE WORKERS
# ─────────────────────────

def update_workers(user_id):

    user_data = economy_collection.find_one({

        "user_id": str(user_id)

    })


    if not user_data:

        return


    workers = user_data.get(
        "workers",
        {}
    )


    current_time = int(
        datetime.now().timestamp()
    )


    updated = False


    for worker_name, worker in workers.items():

        level = worker.get(
            "level",
            1
        )


        stored = worker.get(
            "stored",
            0
        )


        last_claim = worker.get(
            "last_claim",
            current_time
        )


        income = WORKER_LEVELS[level]["income"]


        elapsed = current_time - last_claim


        # MONEY GENERATED

        generated = int(

            income * (elapsed / 86400)

        )


        if generated <= 0:

            continue


        # ADD GENERATED MONEY

        worker["stored"] = stored + generated


        # UPDATE TIME

        worker["last_claim"] = current_time


        updated = True


    if updated:

        economy_collection.update_one(

            {
                "user_id": str(user_id)
            },

            {
                "$set": {
                    "workers": workers
                }
            }
        )
