"""
Ability usage, engagement, disengagement, and ability upgrade logic.
"""

import logging
import random

from lolbot.bot.constants import (
    FORWARD_DIRECTION, ULT_DIRECTION, HEALTH_CRITICAL, HEALTH_LOW, MANA_LOW,
    Lane, LANE_WAYPOINTS,
)
from lolbot.bot.game_state import GameState
from lolbot.bot import humanizer

log = logging.getLogger(__name__)

# R can only be upgraded at levels 6, 11, 16
ULT_LEVEL_GATES = {1: 6, 2: 11, 3: 16}


# Attack-move push timeline (seconds)
_PUSH_TO_ADVANCED = 210   # 3.5 min: start pushing past lane middle
_PUSH_TO_TOWER = 300      # 5 min: start hitting enemy tower
_PUSH_TO_NEXUS = 420      # 7 min: start pushing enemy nexus


def attack_move_forward(lane: Lane, game_time: float) -> None:
    """A-click toward lane targets. Pushes deeper on the minimap over time."""
    wp = LANE_WAYPOINTS[lane]

    if game_time >= _PUSH_TO_NEXUS:
        targets = [
            (FORWARD_DIRECTION, 0.2),
            (wp.enemy_tower, 0.3),
            (wp.enemy_nexus, 0.5),
        ]
    elif game_time >= _PUSH_TO_TOWER:
        targets = [
            (FORWARD_DIRECTION, 0.2),
            (wp.lane_advanced, 0.3),
            (wp.enemy_tower, 0.5),
        ]
    elif game_time >= _PUSH_TO_ADVANCED:
        targets = [
            (FORWARD_DIRECTION, 0.3),
            (wp.lane_middle, 0.2),
            (wp.lane_advanced, 0.5),
        ]
    else:
        targets = [
            (FORWARD_DIRECTION, 0.3),
            (wp.lane_middle, 0.5),
            (wp.lane_advanced, 0.2),
        ]

    values, weights = zip(*targets)
    target = random.choices(values, weights=weights, k=1)[0]
    humanizer.attack_click(target)


def weave_ability(state: GameState) -> None:
    """Cast a random available basic ability during attack-move."""
    if state.mana_pct < MANA_LOW:
        return
    keys = ['q', 'w', 'e']
    random.shuffle(keys)
    for key in keys:
        ab = state.get_ability(key.upper())
        if ab.level > 0:
            humanizer.fast_keypress(key)
            return


def cast_ability(key: str) -> None:
    """Press an ability key with cursor aimed forward."""
    if key.upper() == "R":
        target = ULT_DIRECTION
    else:
        target = FORWARD_DIRECTION
    # Move cursor to target first, then cast
    humanizer.right_click(target, fast=True)
    humanizer.fast_keypress(key.lower())


def upgrade_abilities(state: GameState) -> None:
    """Upgrade abilities with R priority, then shuffled Q/W/E."""
    if not state.ability_points_available:
        return

    level = state.active_player.level

    # Try R first if level gate allows
    r_ability = state.get_ability("R")
    if _can_upgrade_ult(r_ability.level, level):
        humanizer.fast_keypress('ctrl+r')

    # Shuffle Q/W/E for variety
    basic_keys = ['ctrl+q', 'ctrl+w', 'ctrl+e']
    random.shuffle(basic_keys)
    for key in basic_keys:
        humanizer.fast_keypress(key)


def should_disengage(state: GameState) -> bool:
    """Check if the bot should disengage from combat."""
    if state.health_pct < HEALTH_CRITICAL:
        return True
    if state.health_pct < HEALTH_LOW and state.mana_pct < MANA_LOW:
        return True
    return False


def _can_upgrade_ult(current_ult_level: int, champion_level: int) -> bool:
    """Check if R can be upgraded based on level gates."""
    next_ult_level = current_ult_level + 1
    required_champ_level = ULT_LEVEL_GATES.get(next_ult_level)
    if required_champ_level is None:
        return False  # max ult level reached
    return champion_level >= required_champ_level
