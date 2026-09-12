from utils.economy import (
    get_cash,
    add_cash
)


# ─────────────────────────
# CREATE WAGER
# ─────────────────────────

def create_wager(
    user1,
    user2,
    amount,
    game
):

    if amount <= 0:

        return (
            False,
            "Invalid amount."
        )


    cash1 = get_cash(user1)
    cash2 = get_cash(user2)


    if cash1 < amount:

        return (
            False,
            "Player 1 lacks cash."
        )


    if cash2 < amount:

        return (
            False,
            "Player 2 lacks cash."
        )


    return (
        True,
        f"Wager created for {game}"
    )


# ─────────────────────────
# COMPLETE WAGER
# ─────────────────────────

def complete_wager(
    winner,
    loser,
    amount
):

    payout = amount

    add_cash(
        winner,
        payout
    )

    return payout
