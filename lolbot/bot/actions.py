"""
Action dispatch. Maps ActionType to handler functions in the subsystems.
"""

import logging

from lolbot.bot.constants import ActionType, GamePhase, Lane, AFK_OK_BUTTON
from lolbot.bot.game_state import GameState
from lolbot.bot import combat, lane, items, humanizer

log = logging.getLogger(__name__)


class ActionExecutor:
    """Dispatches scored actions to the appropriate subsystem."""

    def __init__(self, active_lane: Lane = Lane.MID):
        self.lane = active_lane
        self._last_action = None
        self._repeat_count = 0

    def execute(self, action: ActionType, state: GameState, phase: GamePhase) -> None:
        """Execute an action by dispatching to the appropriate handler."""
        # Track repeated actions
        if action == self._last_action:
            self._repeat_count += 1
        else:
            self._repeat_count = 0
            self._last_action = action

        handler = self._dispatch_table.get(action)
        if handler is None:
            log.debug(f"No handler for action: {action.name}")
            return

        log.debug(f"Executing: {action.name} (repeat={self._repeat_count})")
        handler(self, state, phase)

    def _do_idle(self, state: GameState, phase: GamePhase) -> None:
        humanizer.think()

    def _do_move_to_lane(self, state: GameState, phase: GamePhase) -> None:
        lane.move_to_lane(self.lane)

    def _do_advance(self, state: GameState, phase: GamePhase) -> None:
        lane.advance_in_lane(self.lane, phase)

    def _do_retreat(self, state: GameState, phase: GamePhase) -> None:
        lane.retreat_to_tower(self.lane)

    def _do_attack_move(self, state: GameState, phase: GamePhase) -> None:
        combat.attack_move_forward(self.lane, state.game_time)
        combat.weave_ability(state)

    def _do_cast_q(self, state: GameState, phase: GamePhase) -> None:
        combat.cast_ability("Q")

    def _do_cast_w(self, state: GameState, phase: GamePhase) -> None:
        combat.cast_ability("W")

    def _do_cast_e(self, state: GameState, phase: GamePhase) -> None:
        combat.cast_ability("E")

    def _do_cast_r(self, state: GameState, phase: GamePhase) -> None:
        combat.cast_ability("R")

    def _do_summoner_d(self, state: GameState, phase: GamePhase) -> None:
        humanizer.keypress('d')

    def _do_summoner_f(self, state: GameState, phase: GamePhase) -> None:
        humanizer.keypress('f')

    def _do_buy_items(self, state: GameState, phase: GamePhase) -> None:
        items.buy_items(state)

    def _do_recall(self, state: GameState, phase: GamePhase) -> None:
        lane.retreat_to_tower(self.lane)
        lane.recall()
        # At fountain after recall: buy items and upgrade abilities
        items.buy_items(state)
        combat.upgrade_abilities(state)

    def _do_upgrade_abilities(self, state: GameState, phase: GamePhase) -> None:
        combat.upgrade_abilities(state)

    def _do_dismiss_afk(self, state: GameState, phase: GamePhase) -> None:
        humanizer.left_click(AFK_OK_BUTTON, fast=True)

    def _do_lock_camera(self, state: GameState, phase: GamePhase) -> None:
        humanizer.keypress('y')

    _dispatch_table = {
        ActionType.IDLE: _do_idle,
        ActionType.MOVE_TO_LANE: _do_move_to_lane,
        ActionType.ADVANCE_IN_LANE: _do_advance,
        ActionType.RETREAT_TO_TOWER: _do_retreat,
        ActionType.ATTACK_MOVE: _do_attack_move,
        ActionType.CAST_ABILITY_Q: _do_cast_q,
        ActionType.CAST_ABILITY_W: _do_cast_w,
        ActionType.CAST_ABILITY_E: _do_cast_e,
        ActionType.CAST_ABILITY_R: _do_cast_r,
        ActionType.USE_SUMMONER_D: _do_summoner_d,
        ActionType.USE_SUMMONER_F: _do_summoner_f,
        ActionType.BUY_ITEMS: _do_buy_items,
        ActionType.RECALL: _do_recall,
        ActionType.UPGRADE_ABILITIES: _do_upgrade_abilities,
        ActionType.DISMISS_AFK: _do_dismiss_afk,
        ActionType.LOCK_CAMERA: _do_lock_camera,
    }
