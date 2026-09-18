"""Tests for the DecisionEngine scoring functions."""

from dataclasses import field

import pytest

from lolbot.bot.constants import ActionType, GamePhase
from lolbot.bot.decision import DecisionEngine, determine_phase, ScoredAction
from lolbot.bot.game_state import GameState, ActivePlayerState, PlayerState, AbilityState, GameEvent


def _make_state(
    health_pct=1.0,
    mana_pct=1.0,
    gold=500.0,
    level=6,
    game_time=300.0,
    ability_levels=None,
    enemies_dead=0,
    ally_death_events=None,
) -> GameState:
    """Helper to construct a GameState for testing."""
    if ability_levels is None:
        ability_levels = {"Q": 3, "W": 2, "E": 1, "R": 0}

    max_health = 1000.0
    max_mana = 500.0

    abilities = {}
    for key in ("Q", "W", "E", "R"):
        abilities[key] = AbilityState(key=key, level=ability_levels.get(key, 0), name=f"Ability {key}")

    ap = ActivePlayerState(
        summoner_name="TestBot",
        level=level,
        current_gold=gold,
        health=health_pct * max_health,
        max_health=max_health,
        mana=mana_pct * max_mana,
        max_mana=max_mana,
        abilities=abilities,
        summoner_d="Ghost",
        summoner_f="Heal",
    )

    players = [
        PlayerState(summoner_name="TestBot", champion_name="Ashe", team="ORDER", level=level),
        PlayerState(summoner_name="Ally1", champion_name="Garen", team="ORDER", level=5),
    ]

    # Add enemies
    for i in range(5):
        players.append(PlayerState(
            summoner_name=f"Enemy{i}",
            champion_name=f"Champ{i}",
            team="CHAOS",
            level=6,
            is_dead=(i < enemies_dead),
        ))

    events = []
    if ally_death_events:
        for evt in ally_death_events:
            events.append(GameEvent(
                event_name="ChampionKill",
                event_time=evt["time"],
                data={"VictimName": evt["victim"]},
            ))

    state = GameState(
        game_time=game_time,
        active_player=ap,
        all_players=players,
        events=events,
    )
    return state


class TestDeterminePhase:
    def test_loading(self):
        assert determine_phase(1.0) == GamePhase.LOADING

    def test_early_laning(self):
        assert determine_phase(50.0) == GamePhase.EARLY_LANING

    def test_laning(self):
        assert determine_phase(300.0) == GamePhase.LANING

    def test_mid_game(self):
        assert determine_phase(1000.0) == GamePhase.MID_GAME

    def test_late_game(self):
        assert determine_phase(2000.0) == GamePhase.LATE_GAME


class TestRetreatScoring:
    def test_recall_wins_at_critical_hp(self):
        engine = DecisionEngine()
        state = _make_state(health_pct=0.2)
        result = engine.decide(state, GamePhase.LANING)
        # Recall should beat retreat at critical HP (11.0 vs 10.0)
        assert result.action == ActionType.RECALL

    def test_retreat_scores_higher_than_advance_at_low_hp(self):
        engine = DecisionEngine()
        state = _make_state(health_pct=0.3)
        retreat_score = engine._score_retreat(state, GamePhase.LANING)
        advance_score = engine._score_advance(state, GamePhase.LANING)
        assert retreat_score > advance_score

    def test_retreat_low_when_healthy(self):
        engine = DecisionEngine()
        state = _make_state(health_pct=0.95)
        retreat_score = engine._score_retreat(state, GamePhase.LANING)
        assert retreat_score < 1.0

    def test_retreat_boosted_by_ally_deaths(self):
        engine = DecisionEngine()
        state_no_deaths = _make_state(health_pct=0.6)
        state_with_deaths = _make_state(
            health_pct=0.6,
            ally_death_events=[{"time": 295.0, "victim": "Ally1"}],
        )
        score_no = engine._score_retreat(state_no_deaths, GamePhase.LANING)
        score_yes = engine._score_retreat(state_with_deaths, GamePhase.LANING)
        assert score_yes > score_no


class TestAdvanceScoring:
    def test_advance_higher_when_healthy(self):
        engine = DecisionEngine()
        state_healthy = _make_state(health_pct=0.9)
        state_low = _make_state(health_pct=0.3)
        score_h = engine._score_advance(state_healthy, GamePhase.LANING)
        score_l = engine._score_advance(state_low, GamePhase.LANING)
        assert score_h > score_l

    def test_advance_boosted_by_dead_enemies(self):
        engine = DecisionEngine()
        state_no_dead = _make_state(health_pct=0.8, enemies_dead=0)
        state_dead = _make_state(health_pct=0.8, enemies_dead=3)
        score_no = engine._score_advance(state_no_dead, GamePhase.LANING)
        score_dead = engine._score_advance(state_dead, GamePhase.LANING)
        assert score_dead > score_no

    def test_advance_multiplied_in_late_game(self):
        engine = DecisionEngine()
        state = _make_state(health_pct=0.8)
        score_laning = engine._score_advance(state, GamePhase.LANING)
        score_late = engine._score_advance(state, GamePhase.LATE_GAME)
        assert score_late > score_laning


class TestAbilityScoring:
    def test_ability_negative_if_not_leveled(self):
        engine = DecisionEngine()
        state = _make_state(ability_levels={"Q": 0, "W": 0, "E": 0, "R": 0})
        assert engine._score_cast_q(state, GamePhase.LANING) < 0
        assert engine._score_cast_r(state, GamePhase.LANING) < 0

    def test_ability_low_when_low_mana(self):
        engine = DecisionEngine()
        state = _make_state(mana_pct=0.1, ability_levels={"Q": 3, "W": 2, "E": 1, "R": 1})
        q_score = engine._score_cast_q(state, GamePhase.LANING)
        assert q_score < 1.0

    def test_ability_reasonable_with_mana(self):
        engine = DecisionEngine()
        state = _make_state(mana_pct=0.8, health_pct=0.8, ability_levels={"Q": 3, "W": 2, "E": 1, "R": 1})
        q_score = engine._score_cast_q(state, GamePhase.LANING)
        assert q_score > 2.0


class TestBuyItemsScoring:
    def test_high_gold_high_score(self):
        engine = DecisionEngine()
        state = _make_state(gold=1500.0)
        score = engine._score_buy_items(state, GamePhase.LANING)
        assert score >= 6.0

    def test_medium_gold(self):
        engine = DecisionEngine()
        state = _make_state(gold=700.0)
        score = engine._score_buy_items(state, GamePhase.LANING)
        assert 2.5 < score < 6.5

    def test_low_gold_low_score(self):
        engine = DecisionEngine()
        state = _make_state(gold=100.0)
        score = engine._score_buy_items(state, GamePhase.LANING)
        assert score < 1.0


class TestRecallScoring:
    def test_recall_beats_retreat_at_critical_hp(self):
        engine = DecisionEngine()
        state = _make_state(health_pct=0.2)
        recall_score = engine._score_recall(state, GamePhase.LANING)
        retreat_score = engine._score_retreat(state, GamePhase.LANING)
        assert recall_score > retreat_score

    def test_recall_beats_retreat_at_low_hp(self):
        engine = DecisionEngine()
        state = _make_state(health_pct=0.3)
        recall_score = engine._score_recall(state, GamePhase.LANING)
        retreat_score = engine._score_retreat(state, GamePhase.LANING)
        assert recall_score > retreat_score

    def test_recall_low_when_healthy(self):
        engine = DecisionEngine()
        state = _make_state(health_pct=0.8)
        score = engine._score_recall(state, GamePhase.LANING)
        assert score == 0.0

    def test_recall_penalized_late_game(self):
        engine = DecisionEngine()
        state = _make_state(health_pct=0.3, mana_pct=0.1, gold=1200.0)
        score_laning = engine._score_recall(state, GamePhase.LANING)
        score_late = engine._score_recall(state, GamePhase.LATE_GAME)
        assert score_late < score_laning


class TestUpgradeAbilitiesScoring:
    def test_high_when_points_available(self):
        engine = DecisionEngine()
        # Level 6, abilities sum = 3+2+1+0 = 6 < 6? No, 6 == 6 => not available
        # Let's use level 8, abilities sum = 3+2+1+0 = 6 < 8 => available
        state = _make_state(level=8, ability_levels={"Q": 3, "W": 2, "E": 1, "R": 0})
        score = engine._score_upgrade_abilities(state, GamePhase.LANING)
        assert score == 9.0

    def test_negative_when_no_points(self):
        engine = DecisionEngine()
        state = _make_state(level=6, ability_levels={"Q": 3, "W": 2, "E": 1, "R": 0})
        score = engine._score_upgrade_abilities(state, GamePhase.LANING)
        assert score < 0


class TestSummonerSpellScoring:
    def test_summoner_f_high_at_low_hp(self):
        engine = DecisionEngine()
        state = _make_state(health_pct=0.3)
        score = engine._score_summoner_f(state, GamePhase.LANING)
        assert score >= 7.0

    def test_summoner_f_low_when_healthy(self):
        engine = DecisionEngine()
        state = _make_state(health_pct=0.9)
        score = engine._score_summoner_f(state, GamePhase.LANING)
        assert score < 1.0

    def test_summoner_d_flee_at_critical(self):
        engine = DecisionEngine()
        state = _make_state(health_pct=0.2)
        score = engine._score_summoner_d(state, GamePhase.LANING)
        assert score >= 6.0


class TestMoveToLaneScoring:
    def test_early_laning_boosted(self):
        engine = DecisionEngine()
        state = _make_state(health_pct=0.8)
        score = engine._score_move_to_lane(state, GamePhase.EARLY_LANING)
        assert score == 5.0

    def test_early_laning_move_wins_over_idle(self):
        engine = DecisionEngine()
        state = _make_state(health_pct=0.8, game_time=50.0)
        result = engine.decide(state, GamePhase.EARLY_LANING)
        assert result.action == ActionType.MOVE_TO_LANE


class TestAttackMoveScoring:
    def test_attack_move_dominant_when_healthy(self):
        engine = DecisionEngine()
        state = _make_state(health_pct=0.9, mana_pct=0.8)
        attack_score = engine._score_attack_move(state, GamePhase.LANING)
        move_score = engine._score_move_to_lane(state, GamePhase.LANING)
        advance_score = engine._score_advance(state, GamePhase.LANING)
        assert attack_score > move_score
        assert attack_score > advance_score

    def test_attack_move_wins_decide_when_healthy(self):
        engine = DecisionEngine()
        # No ability points available, so upgrade won't interfere
        state = _make_state(health_pct=0.9, mana_pct=0.8, level=6,
                            ability_levels={"Q": 3, "W": 2, "E": 1, "R": 0})
        result = engine.decide(state, GamePhase.LANING)
        assert result.action == ActionType.ATTACK_MOVE

    def test_attack_move_penalized_at_low_hp(self):
        engine = DecisionEngine()
        state = _make_state(health_pct=0.3)
        score = engine._score_attack_move(state, GamePhase.LANING)
        assert score < 1.0


class TestLockCameraScoring:
    def test_high_during_loading(self):
        engine = DecisionEngine()
        state = _make_state()
        score = engine._score_lock_camera(state, GamePhase.LOADING)
        assert score == 5.0

    def test_low_during_early_laning(self):
        engine = DecisionEngine()
        state = _make_state()
        score = engine._score_lock_camera(state, GamePhase.EARLY_LANING)
        assert score == 0.3

    def test_low_during_laning(self):
        engine = DecisionEngine()
        state = _make_state()
        score = engine._score_lock_camera(state, GamePhase.LANING)
        assert score == 0.3


class TestPhaseActions:
    def test_buy_items_not_in_laning(self):
        from lolbot.bot.constants import PHASE_ACTIONS
        assert ActionType.BUY_ITEMS not in PHASE_ACTIONS[GamePhase.LANING]

    def test_buy_items_not_in_mid_game(self):
        from lolbot.bot.constants import PHASE_ACTIONS
        assert ActionType.BUY_ITEMS not in PHASE_ACTIONS[GamePhase.MID_GAME]

    def test_buy_items_not_in_late_game(self):
        from lolbot.bot.constants import PHASE_ACTIONS
        assert ActionType.BUY_ITEMS not in PHASE_ACTIONS[GamePhase.LATE_GAME]

    def test_buy_items_not_in_early_laning(self):
        from lolbot.bot.constants import PHASE_ACTIONS
        assert ActionType.BUY_ITEMS not in PHASE_ACTIONS[GamePhase.EARLY_LANING]

    def test_early_laning_has_move_to_lane(self):
        from lolbot.bot.constants import PHASE_ACTIONS
        assert ActionType.MOVE_TO_LANE in PHASE_ACTIONS[GamePhase.EARLY_LANING]

    def test_early_laning_no_upgrade_or_lock_camera(self):
        from lolbot.bot.constants import PHASE_ACTIONS
        early = PHASE_ACTIONS[GamePhase.EARLY_LANING]
        assert ActionType.UPGRADE_ABILITIES not in early
        assert ActionType.LOCK_CAMERA not in early


class TestDecideIntegration:
    def test_decide_returns_scored_action(self):
        engine = DecisionEngine()
        state = _make_state(health_pct=0.8)
        result = engine.decide(state, GamePhase.LANING)
        assert isinstance(result, ScoredAction)
        assert isinstance(result.action, ActionType)

    def test_upgrade_wins_when_points_available(self):
        engine = DecisionEngine()
        state = _make_state(level=10, ability_levels={"Q": 3, "W": 2, "E": 1, "R": 1})
        # Total = 7 < 10, so upgrade should score 9.0 (highest)
        result = engine.decide(state, GamePhase.LANING)
        assert result.action == ActionType.UPGRADE_ABILITIES

    def test_loading_phase_limited_actions(self):
        engine = DecisionEngine()
        state = _make_state(health_pct=0.8, game_time=1.0)
        result = engine.decide(state, GamePhase.LOADING)
        assert result.action in (ActionType.IDLE, ActionType.LOCK_CAMERA, ActionType.DISMISS_AFK)

    def test_buy_items_never_chosen_during_laning(self):
        engine = DecisionEngine()
        state = _make_state(health_pct=0.8, gold=2000.0, game_time=300.0)
        result = engine.decide(state, GamePhase.LANING)
        assert result.action != ActionType.BUY_ITEMS
