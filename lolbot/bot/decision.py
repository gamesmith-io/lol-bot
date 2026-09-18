"""
Utility AI scoring engine. Each game tick, scores all candidate actions
for the current phase and returns the highest-scoring action.
"""

import logging
import random
from dataclasses import dataclass

from lolbot.bot.constants import (
    ActionType, GamePhase, PHASE_ACTIONS,
    HEALTH_CRITICAL, HEALTH_LOW, HEALTH_COMFORTABLE,
    MANA_LOW, MANA_COMFORTABLE,
    GOLD_HIGH, GOLD_MEDIUM, GOLD_LOW,
    LOADING_SCREEN_TIME, MINION_CLASH_TIME, EARLY_LANING_END,
    MID_GAME_START, LATE_GAME_START, MAX_GAME_TIME,
)
from lolbot.bot.game_state import GameState

log = logging.getLogger(__name__)

NOISE_FACTOR = 0.05


@dataclass
class ScoredAction:
    action: ActionType
    score: float
    context: dict


def determine_phase(game_time: float) -> GamePhase:
    if game_time < LOADING_SCREEN_TIME:
        return GamePhase.LOADING
    elif game_time < MINION_CLASH_TIME:
        return GamePhase.EARLY_LANING
    elif game_time < MID_GAME_START:
        return GamePhase.LANING
    elif game_time < LATE_GAME_START:
        return GamePhase.MID_GAME
    else:
        return GamePhase.LATE_GAME


class DecisionEngine:
    """Scores candidate actions and returns the best one."""

    def __init__(self):
        self._scorers = {
            ActionType.IDLE: self._score_idle,
            ActionType.MOVE_TO_LANE: self._score_move_to_lane,
            ActionType.ADVANCE_IN_LANE: self._score_advance,
            ActionType.RETREAT_TO_TOWER: self._score_retreat,
            ActionType.ATTACK_MOVE: self._score_attack_move,
            ActionType.CAST_ABILITY_Q: self._score_cast_q,
            ActionType.CAST_ABILITY_W: self._score_cast_w,
            ActionType.CAST_ABILITY_E: self._score_cast_e,
            ActionType.CAST_ABILITY_R: self._score_cast_r,
            ActionType.USE_SUMMONER_D: self._score_summoner_d,
            ActionType.USE_SUMMONER_F: self._score_summoner_f,
            ActionType.BUY_ITEMS: self._score_buy_items,
            ActionType.RECALL: self._score_recall,
            ActionType.UPGRADE_ABILITIES: self._score_upgrade_abilities,
            ActionType.DISMISS_AFK: self._score_dismiss_afk,
            ActionType.LOCK_CAMERA: self._score_lock_camera,
        }

    def decide(self, state: GameState, phase: GamePhase) -> ScoredAction:
        """Score all candidate actions for the current phase, return highest."""
        candidates = PHASE_ACTIONS.get(phase, {ActionType.IDLE})
        scored = []

        for action_type in candidates:
            scorer = self._scorers.get(action_type)
            if scorer is None:
                continue
            raw_score = scorer(state, phase)
            noise = random.uniform(-NOISE_FACTOR, NOISE_FACTOR)
            final_score = raw_score + noise
            scored.append(ScoredAction(action=action_type, score=final_score, context={}))

        if not scored:
            return ScoredAction(action=ActionType.IDLE, score=0.0, context={})

        scored.sort(key=lambda s: s.score, reverse=True)
        best = scored[0]
        log.debug(f"Decision: {best.action.name} (score={best.score:.2f})")
        return best

    # --- Scoring functions ---

    @staticmethod
    def _score_idle(state: GameState, phase: GamePhase) -> float:
        return 0.1

    @staticmethod
    def _score_move_to_lane(state: GameState, phase: GamePhase) -> float:
        if phase == GamePhase.EARLY_LANING:
            return 5.0  # rush to lane to avoid AFK warning
        if state.health_pct > HEALTH_COMFORTABLE:
            return 2.5
        return 1.0

    @staticmethod
    def _score_advance(state: GameState, phase: GamePhase) -> float:
        score = 3.0 * state.health_pct
        # Bonus for dead enemies
        dead_ratio = len(state.dead_enemies) / max(len(state.enemies), 1)
        score += 2.0 * dead_ratio
        if phase == GamePhase.LATE_GAME:
            score *= 1.5
        if state.health_pct < HEALTH_LOW:
            score *= 0.3
        return score

    @staticmethod
    def _score_retreat(state: GameState, phase: GamePhase) -> float:
        hp = state.health_pct
        if hp < HEALTH_CRITICAL:
            score = 10.0
        elif hp < HEALTH_LOW:
            score = 7.0
        elif hp < HEALTH_COMFORTABLE:
            score = 3.0
        else:
            score = 0.5

        # Boost if allies dying nearby
        if state.recent_ally_deaths > 0:
            score += 2.0
        return score

    @staticmethod
    def _score_attack_move(state: GameState, phase: GamePhase) -> float:
        score = 5.0 * state.health_pct
        if state.mana_pct > MANA_COMFORTABLE:
            score += 1.0
        if state.health_pct < HEALTH_LOW:
            score *= 0.3
        return score

    @staticmethod
    def _score_cast_q(state: GameState, phase: GamePhase) -> float:
        ab = state.get_ability("Q")
        if ab.level <= 0:
            return -1.0
        if state.mana_pct < MANA_LOW:
            return 0.2
        return 3.5 * state.health_pct

    @staticmethod
    def _score_cast_w(state: GameState, phase: GamePhase) -> float:
        ab = state.get_ability("W")
        if ab.level <= 0:
            return -1.0
        if state.mana_pct < MANA_LOW:
            return 0.2
        return 3.0 * state.health_pct

    @staticmethod
    def _score_cast_e(state: GameState, phase: GamePhase) -> float:
        ab = state.get_ability("E")
        if ab.level <= 0:
            return -1.0
        if state.mana_pct < MANA_LOW:
            return 0.2
        return 3.0 * state.health_pct

    @staticmethod
    def _score_cast_r(state: GameState, phase: GamePhase) -> float:
        ab = state.get_ability("R")
        if ab.level <= 0:
            return -1.0
        # Conserve ult unless good opportunity
        if state.health_pct > HEALTH_COMFORTABLE and len(state.dead_enemies) == 0:
            return 2.0
        if state.health_pct < HEALTH_LOW:
            return 1.0  # don't waste ult when about to die
        # Good opportunity: healthy and enemies dead or mid-fight
        return 4.5

    @staticmethod
    def _score_summoner_d(state: GameState, phase: GamePhase) -> float:
        hp = state.health_pct
        if hp < HEALTH_CRITICAL:
            return 6.0  # flee
        if hp > HEALTH_COMFORTABLE:
            return 1.5  # engage/chase
        return 0.5

    @staticmethod
    def _score_summoner_f(state: GameState, phase: GamePhase) -> float:
        hp = state.health_pct
        if hp < HEALTH_LOW:
            return 7.0  # emergency defensive
        return 0.1  # conserve

    @staticmethod
    def _score_buy_items(state: GameState, phase: GamePhase) -> float:
        gold = state.active_player.current_gold
        if gold >= GOLD_HIGH:
            return 6.0
        elif gold >= GOLD_MEDIUM:
            return 3.0
        elif gold >= GOLD_LOW:
            return 1.0
        return 0.2

    @staticmethod
    def _score_recall(state: GameState, phase: GamePhase) -> float:
        hp = state.health_pct
        mp = state.mana_pct
        gold = state.active_player.current_gold

        score = 0.0
        if hp < HEALTH_CRITICAL:
            score += 11.0
        elif hp < HEALTH_LOW:
            score += 8.0
        if mp < MANA_LOW:
            score += 2.0
        if gold >= GOLD_HIGH:
            score += 2.0

        # Penalize recall in late game (push is more important)
        if phase == GamePhase.LATE_GAME:
            score *= 0.6

        return score

    @staticmethod
    def _score_upgrade_abilities(state: GameState, phase: GamePhase) -> float:
        if state.ability_points_available:
            return 9.0
        return -1.0

    @staticmethod
    def _score_dismiss_afk(state: GameState, phase: GamePhase) -> float:
        # Always worth clicking periodically
        return 1.5

    @staticmethod
    def _score_lock_camera(state: GameState, phase: GamePhase) -> float:
        if phase == GamePhase.LOADING:
            return 5.0
        return 0.3
