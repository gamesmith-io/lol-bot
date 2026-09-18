"""Tests for GameStateManager parsing with mock API JSON."""

import json
from unittest.mock import MagicMock

import pytest

from lolbot.bot.game_state import GameStateManager, GameState
from lolbot.lcu.game_server import GameServer


MOCK_API_RESPONSE = {
    "gameData": {"gameTime": 542.3},
    "activePlayer": {
        "summonerName": "TestBot",
        "level": 8,
        "currentGold": 1250.5,
        "championStats": {
            "currentHealth": 450.0,
            "maxHealth": 900.0,
            "resourceValue": 200.0,
            "resourceMax": 500.0,
        },
        "abilities": {
            "Q": {"abilityLevel": 3, "displayName": "Test Q"},
            "W": {"abilityLevel": 2, "displayName": "Test W"},
            "E": {"abilityLevel": 1, "displayName": "Test E"},
            "R": {"abilityLevel": 1, "displayName": "Test R"},
        },
        "summonerSpells": {
            "summonerSpellOne": {"displayName": "Ghost"},
            "summonerSpellTwo": {"displayName": "Heal"},
        },
    },
    "allPlayers": [
        {
            "summonerName": "TestBot",
            "championName": "Ashe",
            "team": "ORDER",
            "level": 8,
            "isDead": False,
            "respawnTimer": 0,
            "items": [{"displayName": "Doran's Blade"}],
            "scores": {"kills": 2, "deaths": 1, "assists": 3},
        },
        {
            "summonerName": "Ally1",
            "championName": "Garen",
            "team": "ORDER",
            "level": 7,
            "isDead": False,
            "respawnTimer": 0,
            "items": [],
            "scores": {"kills": 1, "deaths": 2, "assists": 1},
        },
        {
            "summonerName": "Enemy1",
            "championName": "Darius",
            "team": "CHAOS",
            "level": 9,
            "isDead": True,
            "respawnTimer": 15.0,
            "items": [{"displayName": "Trinity Force"}],
            "scores": {"kills": 5, "deaths": 3, "assists": 0},
        },
        {
            "summonerName": "Enemy2",
            "championName": "Lux",
            "team": "CHAOS",
            "level": 7,
            "isDead": False,
            "respawnTimer": 0,
            "items": [],
            "scores": {"kills": 0, "deaths": 0, "assists": 4},
        },
    ],
    "events": {
        "Events": [
            {"EventName": "GameStart", "EventTime": 0.0},
            {
                "EventName": "ChampionKill",
                "EventTime": 530.0,
                "VictimName": "Enemy1",
                "KillerName": "TestBot",
            },
        ]
    },
}


def _make_manager(raw_data: dict) -> GameStateManager:
    """Create a GameStateManager with mock data pre-loaded."""
    gs = GameServer()
    gs.data = json.dumps(raw_data)
    gs.update_data = MagicMock()  # prevent real HTTP calls
    mgr = GameStateManager(gs)
    mgr._last_poll = 0  # force update
    return mgr


class TestGameStateManagerParsing:
    def test_game_time_parsed(self):
        mgr = _make_manager(MOCK_API_RESPONSE)
        state = mgr.update()
        assert state.game_time == pytest.approx(542.3)

    def test_active_player_basic_fields(self):
        mgr = _make_manager(MOCK_API_RESPONSE)
        state = mgr.update()
        ap = state.active_player
        assert ap.summoner_name == "TestBot"
        assert ap.level == 8
        assert ap.current_gold == pytest.approx(1250.5)

    def test_health_and_mana(self):
        mgr = _make_manager(MOCK_API_RESPONSE)
        state = mgr.update()
        assert state.health_pct == pytest.approx(0.5)
        assert state.mana_pct == pytest.approx(0.4)

    def test_abilities_parsed(self):
        mgr = _make_manager(MOCK_API_RESPONSE)
        state = mgr.update()
        q = state.get_ability("Q")
        assert q.level == 3
        assert q.name == "Test Q"
        r = state.get_ability("R")
        assert r.level == 1

    def test_summoner_spells(self):
        mgr = _make_manager(MOCK_API_RESPONSE)
        state = mgr.update()
        assert state.active_player.summoner_d == "Ghost"
        assert state.active_player.summoner_f == "Heal"

    def test_all_players_parsed(self):
        mgr = _make_manager(MOCK_API_RESPONSE)
        state = mgr.update()
        assert len(state.all_players) == 4

    def test_allies_and_enemies(self):
        mgr = _make_manager(MOCK_API_RESPONSE)
        state = mgr.update()
        assert len(state.allies) == 1
        assert state.allies[0].summoner_name == "Ally1"
        assert len(state.enemies) == 2

    def test_dead_enemies(self):
        mgr = _make_manager(MOCK_API_RESPONSE)
        state = mgr.update()
        dead = state.dead_enemies
        assert len(dead) == 1
        assert dead[0].summoner_name == "Enemy1"

    def test_is_dead_false(self):
        mgr = _make_manager(MOCK_API_RESPONSE)
        state = mgr.update()
        assert state.is_dead is False

    def test_is_dead_true(self):
        data = json.loads(json.dumps(MOCK_API_RESPONSE))
        data["allPlayers"][0]["isDead"] = True
        mgr = _make_manager(data)
        state = mgr.update()
        assert state.is_dead is True

    def test_my_team(self):
        mgr = _make_manager(MOCK_API_RESPONSE)
        state = mgr.update()
        assert state.my_team == "ORDER"

    def test_events_parsed(self):
        mgr = _make_manager(MOCK_API_RESPONSE)
        state = mgr.update()
        assert len(state.events) == 2
        assert state.events[0].event_name == "GameStart"
        assert state.events[1].event_name == "ChampionKill"

    def test_ability_points_available(self):
        mgr = _make_manager(MOCK_API_RESPONSE)
        state = mgr.update()
        # Level 8, abilities: 3+2+1+1 = 7 < 8
        assert state.ability_points_available is True

    def test_ability_points_not_available(self):
        data = json.loads(json.dumps(MOCK_API_RESPONSE))
        data["activePlayer"]["abilities"]["Q"]["abilityLevel"] = 4
        # 4+2+1+1 = 8 == level 8
        mgr = _make_manager(data)
        state = mgr.update()
        assert state.ability_points_available is False

    def test_recent_ally_deaths(self):
        data = json.loads(json.dumps(MOCK_API_RESPONSE))
        # Add a recent ally death event
        data["events"]["Events"].append({
            "EventName": "ChampionKill",
            "EventTime": 540.0,
            "VictimName": "Ally1",
            "KillerName": "Enemy2",
        })
        mgr = _make_manager(data)
        state = mgr.update()
        assert state.recent_ally_deaths == 1

    def test_manaless_champion(self):
        """Manaless champions (resourceMax=0) should report mana_pct=1.0."""
        data = json.loads(json.dumps(MOCK_API_RESPONSE))
        data["activePlayer"]["championStats"]["resourceMax"] = 0
        data["activePlayer"]["championStats"]["resourceValue"] = 0
        mgr = _make_manager(data)
        state = mgr.update()
        assert state.mana_pct == 1.0

    def test_player_items_parsed(self):
        mgr = _make_manager(MOCK_API_RESPONSE)
        state = mgr.update()
        bot_player = state.all_players[0]
        assert "Doran's Blade" in bot_player.items

    def test_poll_interval_respected(self):
        """Second update within poll interval returns cached state."""
        mgr = _make_manager(MOCK_API_RESPONSE)
        state1 = mgr.update()
        # Immediately update again (within 0.5s interval)
        state2 = mgr.update()
        assert state1 is state2  # same object, not re-parsed
