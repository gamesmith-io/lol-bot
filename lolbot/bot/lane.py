"""
Lane movement, waypoint navigation, and recall logic.
Handles movement without position data by clicking minimap waypoints.
"""

import logging
import random
from time import sleep

from lolbot.bot.constants import (
    GamePhase, Lane, LANE_WAYPOINTS,
    FIRST_WAVE_SPAWN, WAVE_INTERVAL,
)
from lolbot.bot import humanizer

log = logging.getLogger(__name__)


def move_to_lane(lane: Lane) -> None:
    """Right-click the lane middle waypoint on the minimap."""
    wp = LANE_WAYPOINTS[lane]
    humanizer.right_click(wp.lane_middle)


def advance_in_lane(lane: Lane, phase: GamePhase) -> None:
    """Move forward in lane. Target depends on phase."""
    wp = LANE_WAYPOINTS[lane]

    if phase == GamePhase.LATE_GAME:
        # Aggressive: weighted toward enemy structures
        targets = [
            (wp.lane_advanced, 0.2),
            (wp.enemy_tower, 0.4),
            (wp.enemy_nexus, 0.4),
        ]
    elif phase == GamePhase.MID_GAME:
        targets = [
            (wp.lane_middle, 0.2),
            (wp.lane_advanced, 0.5),
            (wp.enemy_tower, 0.3),
        ]
    else:
        # Conservative during laning
        targets = [
            (wp.lane_middle, 0.6),
            (wp.lane_advanced, 0.3),
            (wp.enemy_tower, 0.1),
        ]

    target = _weighted_choice(targets)
    humanizer.right_click(target)


def retreat_to_tower(lane: Lane) -> None:
    """Right-click the safe tower waypoint."""
    wp = LANE_WAYPOINTS[lane]
    humanizer.right_click(wp.tower_safe)


def recall() -> None:
    """Retreat and recall to base."""
    humanizer.keypress('b')
    # Wait for recall channel (8 seconds) with some variance
    sleep(random.uniform(8.0, 9.5))


def is_wave_approaching(game_time: float) -> bool:
    """Estimate if a minion wave is about to arrive based on game time."""
    if game_time < FIRST_WAVE_SPAWN:
        return False
    time_since_first = game_time - FIRST_WAVE_SPAWN
    time_in_cycle = time_since_first % WAVE_INTERVAL
    # Wave is "approaching" in the last 5 seconds of each cycle
    return time_in_cycle > (WAVE_INTERVAL - 5)


def _weighted_choice(options: list) -> tuple:
    """Choose from a list of (value, weight) tuples."""
    values, weights = zip(*options)
    return random.choices(values, weights=weights, k=1)[0]
