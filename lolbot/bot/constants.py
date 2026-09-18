"""
Enums, coordinates, and thresholds for the bot decision engine.
"""

from dataclasses import dataclass
from enum import Enum, auto


class GamePhase(Enum):
    LOADING = auto()
    EARLY_LANING = auto()
    LANING = auto()
    MID_GAME = auto()
    LATE_GAME = auto()


class Lane(Enum):
    TOP = auto()
    MID = auto()
    BOT = auto()


class ActionType(Enum):
    IDLE = auto()
    MOVE_TO_LANE = auto()
    ADVANCE_IN_LANE = auto()
    RETREAT_TO_TOWER = auto()
    ATTACK_MOVE = auto()
    CAST_ABILITY_Q = auto()
    CAST_ABILITY_W = auto()
    CAST_ABILITY_E = auto()
    CAST_ABILITY_R = auto()
    USE_SUMMONER_D = auto()
    USE_SUMMONER_F = auto()
    BUY_ITEMS = auto()
    RECALL = auto()
    UPGRADE_ABILITIES = auto()
    DISMISS_AFK = auto()
    LOCK_CAMERA = auto()


@dataclass(frozen=True)
class LaneWaypoints:
    tower_safe: tuple
    lane_middle: tuple
    lane_advanced: tuple
    enemy_tower: tuple
    enemy_nexus: tuple


# Minimap ratio coordinates per lane (blue side)
LANE_WAYPOINTS = {
    Lane.MID: LaneWaypoints(
        tower_safe=(0.88, 0.90),
        lane_middle=(0.9035, 0.87),
        lane_advanced=(0.93, 0.84),
        enemy_tower=(0.945, 0.82),
        enemy_nexus=(0.9628, 0.7852),
    ),
    Lane.TOP: LaneWaypoints(
        tower_safe=(0.87, 0.86),
        lane_middle=(0.875, 0.82),
        lane_advanced=(0.88, 0.79),
        enemy_tower=(0.885, 0.77),
        enemy_nexus=(0.9628, 0.7852),
    ),
    Lane.BOT: LaneWaypoints(
        tower_safe=(0.91, 0.92),
        lane_middle=(0.935, 0.91),
        lane_advanced=(0.95, 0.90),
        enemy_tower=(0.955, 0.88),
        enemy_nexus=(0.9628, 0.7852),
    ),
}

# Screen coordinate ratios
CENTER_OF_SCREEN = (0.5, 0.5)
ULT_DIRECTION = (0.7298, 0.2689)
FORWARD_DIRECTION = (0.6, 0.35)

# UI element ratios
AFK_OK_BUTTON = (0.4981, 0.4647)
SYSTEM_MENU_X_BUTTON = (0.7729, 0.2488)
SHOP_PURCHASE_ITEM_BUTTON = (0.7586, 0.58)
SHOP_ITEM_BUTTONS = [
    (0.3216, 0.5036),
    (0.4084, 0.5096),
    (0.4943, 0.4928),
    (0.3216, 0.62),
    (0.4084, 0.62),
    (0.4943, 0.62),
]

# Health thresholds
HEALTH_CRITICAL = 0.25
HEALTH_LOW = 0.45
HEALTH_COMFORTABLE = 0.70

# Mana thresholds
MANA_LOW = 0.20
MANA_COMFORTABLE = 0.50

# Gold thresholds
GOLD_HIGH = 1000
GOLD_MEDIUM = 500
GOLD_LOW = 300

# Game time thresholds (seconds)
LOADING_SCREEN_TIME = 3
MINION_CLASH_TIME = 85
EARLY_LANING_END = 300
MID_GAME_START = 900
LATE_GAME_START = 1500
MAX_GAME_TIME = 3000

# Wave timing
FIRST_WAVE_SPAWN = 65
WAVE_INTERVAL = 30

# Max server errors before giving up
MAX_SERVER_ERRORS = 15

# Phase-gated action sets
PHASE_ACTIONS = {
    GamePhase.LOADING: {
        ActionType.IDLE,
        ActionType.LOCK_CAMERA,
        ActionType.DISMISS_AFK,
    },
    GamePhase.EARLY_LANING: {
        ActionType.MOVE_TO_LANE,
        ActionType.RETREAT_TO_TOWER,
        ActionType.DISMISS_AFK,
        ActionType.IDLE,
    },
    GamePhase.LANING: {
        ActionType.MOVE_TO_LANE,
        ActionType.ADVANCE_IN_LANE,
        ActionType.RETREAT_TO_TOWER,
        ActionType.ATTACK_MOVE,
        ActionType.CAST_ABILITY_Q,
        ActionType.CAST_ABILITY_W,
        ActionType.CAST_ABILITY_E,
        ActionType.CAST_ABILITY_R,
        ActionType.USE_SUMMONER_D,
        ActionType.USE_SUMMONER_F,
        ActionType.RECALL,
        ActionType.UPGRADE_ABILITIES,
        ActionType.DISMISS_AFK,
        ActionType.LOCK_CAMERA,
        ActionType.IDLE,
    },
    GamePhase.MID_GAME: {
        ActionType.MOVE_TO_LANE,
        ActionType.ADVANCE_IN_LANE,
        ActionType.RETREAT_TO_TOWER,
        ActionType.ATTACK_MOVE,
        ActionType.CAST_ABILITY_Q,
        ActionType.CAST_ABILITY_W,
        ActionType.CAST_ABILITY_E,
        ActionType.CAST_ABILITY_R,
        ActionType.USE_SUMMONER_D,
        ActionType.USE_SUMMONER_F,
        ActionType.RECALL,
        ActionType.UPGRADE_ABILITIES,
        ActionType.DISMISS_AFK,
        ActionType.IDLE,
    },
    GamePhase.LATE_GAME: {
        ActionType.MOVE_TO_LANE,
        ActionType.ADVANCE_IN_LANE,
        ActionType.RETREAT_TO_TOWER,
        ActionType.ATTACK_MOVE,
        ActionType.CAST_ABILITY_Q,
        ActionType.CAST_ABILITY_W,
        ActionType.CAST_ABILITY_E,
        ActionType.CAST_ABILITY_R,
        ActionType.USE_SUMMONER_D,
        ActionType.USE_SUMMONER_F,
        ActionType.RECALL,
        ActionType.UPGRADE_ABILITIES,
        ActionType.DISMISS_AFK,
        ActionType.IDLE,
    },
}
