"""
Renders the .blackjack table as real playing cards on a felt-style
board instead of monospace text — proper suits/colors, a face-down
dealer card, score chips, and a win/loss glow border at the end.
"""

from PIL import Image, ImageDraw
from utils.render_common import load_font, vertical_gradient, radial_glow, to_buffer

W = 760
CARD_W, CARD_H = 108, 152
CARD_GAP = 16
ROW_GAP = 46
PAD_X = 40
TOP_PAD = 96
LABEL_GAP = 34
CHIP_GAP = 40
BOTTOM_PAD = 54

BG_TOP = (13, 33, 24)      # deep felt green
BG_BOTTOM = (7, 16, 12)
FELT_LINE = (30, 62, 46)

CARD_BG = (250, 249, 245)
CARD_BACK_1 = (36, 40, 92)
CARD_BACK_2 = (60, 66, 140)
RED = (206, 44, 60)
BLACK = (32, 33, 38)
TEXT_MAIN = (240, 241, 245)
TEXT_SUB = (170, 200, 185)

SUIT_COLOR = {"♠": BLACK, "♣": BLACK, "♥": RED, "♦": RED}

FONT_RANK = load_font(30, "Bold")
FONT_RANK_SM = load_font(18, "Bold")
FONT_SUIT_BIG = load_font(52, "Regular")
FONT_SUIT_SM = load_font(16, "Regular")
FONT_LABEL = load_font(22, "SemiBold")
FONT_SCORE = load_font(20, "Bold")
FONT_FOOT = load_font(18, "Medium")
FONT_BANNER = load_font(30, "Bold")


def _draw_card_back(draw, base, x, y):
    box = [x, y, x + CARD_W, y + CARD_H]
    draw.rounded_rectangle(box, radius=14, fill=CARD_BACK_1, outline=(90, 96, 170), width=2)
    # diamond lattice pattern
    step = 18
    for i in range(-CARD_H, CARD_W + CARD_H, step):
        draw.line([(x + i, y), (x + i + CARD_H, y + CARD_H)], fill=CARD_BACK_2, width=2)
    # clip via re-drawing rounded border on top to hide overflow
    mask = Image.new("L", (CARD_W, CARD_H), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, CARD_W - 1, CARD_H - 1], radius=14, fill=255)
    inner = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
    idraw = ImageDraw.Draw(inner)
    idraw.rectangle([0, 0, CARD_W, CARD_H], fill=CARD_BACK_1)
    for i in range(-CARD_H, CARD_W + CARD_H, step):
        idraw.line([(i, 0), (i + CARD_H, CARD_H)], fill=CARD_BACK_2, width=2)
    idraw.rounded_rectangle([0, 0, CARD_W - 1, CARD_H - 1], radius=14, outline=(120, 128, 200), width=2)
    diamond = ImageDraw.Draw(inner)
    cx, cy = CARD_W / 2, CARD_H / 2
    diamond.polygon([(cx, cy - 22), (cx + 16, cy), (cx, cy + 22), (cx - 16, cy)], outline=(150, 156, 220), width=2)
    base.paste(inner, (x, y), Image.composite(inner, Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0)), mask))


def _draw_card_face(draw, base, x, y, card):
    rank = card[:-1]
    suit = card[-1]
    color = SUIT_COLOR[suit]
    box = [x, y, x + CARD_W, y + CARD_H]
    draw.rounded_rectangle(box, radius=14, fill=CARD_BG, outline=(210, 208, 200), width=2)

    draw.text((x + 10, y + 8), rank, font=FONT_RANK_SM, fill=color)
    draw.text((x + 10, y + 30), suit, font=FONT_SUIT_SM, fill=color)

    # big centered suit
    sw = draw.textlength(suit, font=FONT_SUIT_BIG)
    draw.text((x + CARD_W / 2 - sw / 2, y + CARD_H / 2 - 34), suit, font=FONT_SUIT_BIG, fill=color)

    # bottom-right rank (upside-down feel skipped for legibility on phones)
    rw = draw.textlength(rank, font=FONT_RANK_SM)
    draw.text((x + CARD_W - 10 - rw, y + CARD_H - 34), rank, font=FONT_RANK_SM, fill=color)
    sw2 = draw.textlength(suit, font=FONT_SUIT_SM)
    draw.text((x + CARD_W - 10 - sw2, y + CARD_H - 14 - 12), suit, font=FONT_SUIT_SM, fill=color)


def _hand_width(n_cards):
    return n_cards * CARD_W + (n_cards - 1) * CARD_GAP


def _draw_hand(draw, base, cards, y, hide_second, label, total_text, accent):
    n = len(cards)
    hw = _hand_width(n)
    x0 = W / 2 - hw / 2

    draw.text((W / 2, y - LABEL_GAP), "", font=FONT_LABEL, fill=TEXT_MAIN)  # placeholder no-op
    lw = draw.textlength(label, font=FONT_LABEL)
    draw.text((W / 2 - lw / 2, y - LABEL_GAP), label, font=FONT_LABEL, fill=TEXT_MAIN)

    for i, card in enumerate(cards):
        cx = x0 + i * (CARD_W + CARD_GAP)
        if hide_second and i == 1:
            _draw_card_back(draw, base, int(cx), int(y))
        else:
            _draw_card_face(draw, base, int(cx), int(y), card)

    # score chip under the hand
    chip_y = y + CARD_H + 12
    tw = draw.textlength(total_text, font=FONT_SCORE)
    chip_w = tw + 28
    chip_box = [W / 2 - chip_w / 2, chip_y, W / 2 + chip_w / 2, chip_y + 32]
    draw.rounded_rectangle(chip_box, radius=16, fill=accent)
    draw.text((W / 2 - tw / 2, chip_y + 6), total_text, font=FONT_SCORE, fill=(15, 16, 20))

    return chip_y + 32


def _score_label(total, hidden, busted, blackjack):
    if hidden:
        return "?"
    if busted:
        return f"{total} BUST"
    if blackjack:
        return f"{total} BLACKJACK"
    return str(total)


def render_blackjack(
    player,
    dealer,
    player_total,
    dealer_total,
    hide_second,
    bet,
    format_cash,
    result=None,          # None while playing; "win"/"loss"/"push"/"bj" at the end
    log_text=None,
):
    n_max = max(len(player), len(dealer))
    hand_block_h = CARD_H + 12 + 32
    h = TOP_PAD + hand_block_h + ROW_GAP + hand_block_h + BOTTOM_PAD

    base = vertical_gradient(W, h, BG_TOP, BG_BOTTOM).convert("RGBA")
    draw = ImageDraw.Draw(base)

    # felt centerline
    draw.line([(PAD_X, h // 2), (W - PAD_X, h // 2)], fill=FELT_LINE, width=2)

    busted = player_total > 21
    p_bj = (len(player) == 2 and player_total == 21)
    player_score = _score_label(player_total, False, busted, p_bj)
    dealer_score = _score_label(dealer_total, hide_second, dealer_total > 21, False)

    dealer_accent = (237, 66, 69) if dealer_total > 21 and not hide_second else (254, 231, 92)
    player_accent = (237, 66, 69) if busted else ((87, 242, 135) if p_bj else (88, 101, 242))

    y = TOP_PAD
    y_after_dealer = _draw_hand(draw, base, dealer, y, hide_second, "DEALER", dealer_score, dealer_accent)

    y2 = y_after_dealer + ROW_GAP - 20
    _draw_hand(draw, base, player, y2, False, "YOU", player_score, player_accent)

    # bet footer
    bet_text = f"Bet {format_cash(bet)}"
    draw.text((PAD_X, h - 34), bet_text, font=FONT_FOOT, fill=TEXT_SUB)

    if log_text:
        ltw = draw.textlength(log_text, font=FONT_FOOT)
        draw.text((W - PAD_X - ltw, h - 34), log_text, font=FONT_FOOT, fill=TEXT_SUB)

    # result banner + glow border
    if result is not None:
        if result in ("win", "bj"):
            glow_color = (87, 242, 135)
            banner = "YOU WIN"
        elif result == "loss":
            glow_color = (237, 66, 69)
            banner = "DEALER WINS"
        else:
            glow_color = (254, 231, 92)
            banner = "PUSH"

        glow = radial_glow(W, h, (W // 2, 6), 260, glow_color, max_alpha=70)
        base.alpha_composite(glow)
        draw = ImageDraw.Draw(base)
        draw.rounded_rectangle([0, 0, W - 1, h - 1], radius=0, outline=glow_color, width=4)

        bw = draw.textlength(banner, font=FONT_BANNER)
        pad = 18
        bx0 = W / 2 - bw / 2 - pad
        by0 = 14
        bx1 = W / 2 + bw / 2 + pad
        by1 = by0 + 40
        draw.rounded_rectangle([bx0, by0, bx1, by1], radius=20, fill=glow_color)
        draw.text((W / 2 - bw / 2, by0 + 6), banner, font=FONT_BANNER, fill=(15, 16, 20))

    return to_buffer(base)
