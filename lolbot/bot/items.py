"""
Gold-aware item purchasing from the in-game shop.
"""

import logging
import random

from lolbot.bot.constants import (
    GOLD_LOW, GOLD_HIGH,
    SHOP_ITEM_BUTTONS, SHOP_PURCHASE_ITEM_BUTTON,
)
from lolbot.bot.game_state import GameState
from lolbot.bot import humanizer

log = logging.getLogger(__name__)


def buy_items(state: GameState) -> None:
    """Open shop, click recommended items, and purchase."""
    gold = state.active_player.current_gold
    if gold < GOLD_LOW:
        return

    # Open shop
    humanizer.keypress('p')

    # Attempt multiple purchases when gold is high
    purchase_attempts = 3 if gold >= GOLD_HIGH else 2

    for _ in range(purchase_attempts):
        # Click a recommended item
        item_button = random.choice(SHOP_ITEM_BUTTONS)
        humanizer.left_click(item_button, fast=True)
        # Click purchase
        humanizer.left_click(SHOP_PURCHASE_ITEM_BUTTON, fast=True)

    # Close shop (toggle with 'p' to avoid opening settings menu)
    humanizer.keypress('p')
