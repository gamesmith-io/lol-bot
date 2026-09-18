"""
Centralized game state management. Polls the Riot Live Client Data API,
parses responses into typed dataclasses, and provides derived convenience fields.
"""

import json
import logging
import time
from dataclasses import dataclass, field

from lolbot.lcu.game_server import GameServer, GameServerError

log = logging.getLogger(__name__)

POLL_INTERVAL = 0.5


@dataclass
class AbilityState:
    """State of a single ability (Q/W/E/R)."""
    key: str = ""
    level: int = 0
    name: str = ""


@dataclass
class ActivePlayerState:
    """State of the bot's own champion from activePlayer API data."""
    summoner_name: str = ""
    level: int = 1
    current_gold: float = 0.0
    health: float = 0.0
    max_health: float = 1.0
    mana: float = 0.0
    max_mana: float = 1.0
    abilities: dict = field(default_factory=dict)  # key -> AbilityState
    summoner_d: str = ""
    summoner_f: str = ""


@dataclass
class PlayerState:
    """State of any player in the game."""
    summoner_name: str = ""
    champion_name: str = ""
    team: str = ""
    level: int = 1
    is_dead: bool = False
    respawn_timer: float = 0.0
    items: list = field(default_factory=list)
    scores: dict = field(default_factory=dict)  # kills, deaths, assists, etc.


@dataclass
class GameEvent:
    """A game event from the events API."""
    event_name: str = ""
    event_time: float = 0.0
    data: dict = field(default_factory=dict)


@dataclass
class GameState:
    """Complete game state snapshot with derived convenience fields."""
    game_time: float = 0.0
    active_player: ActivePlayerState = field(default_factory=ActivePlayerState)
    all_players: list = field(default_factory=list)  # list of PlayerState
    events: list = field(default_factory=list)  # list of GameEvent
    raw_data: dict = field(default_factory=dict)

    @property
    def health_pct(self) -> float:
        ap = self.active_player
        if ap.max_health <= 0:
            return 0.0
        return ap.health / ap.max_health

    @property
    def mana_pct(self) -> float:
        ap = self.active_player
        if ap.max_mana <= 0:
            return 1.0  # manaless champions treated as full mana
        return ap.mana / ap.max_mana

    @property
    def is_dead(self) -> bool:
        for p in self.all_players:
            if p.summoner_name == self.active_player.summoner_name:
                return p.is_dead
        return False

    @property
    def my_team(self) -> str:
        for p in self.all_players:
            if p.summoner_name == self.active_player.summoner_name:
                return p.team
        return "ORDER"

    @property
    def allies(self) -> list:
        team = self.my_team
        name = self.active_player.summoner_name
        return [p for p in self.all_players if p.team == team and p.summoner_name != name]

    @property
    def enemies(self) -> list:
        team = self.my_team
        return [p for p in self.all_players if p.team != team]

    @property
    def dead_enemies(self) -> list:
        return [e for e in self.enemies if e.is_dead]

    @property
    def dead_allies(self) -> list:
        return [a for a in self.allies if a.is_dead]

    @property
    def ability_points_available(self) -> bool:
        """True if we likely have unspent ability points."""
        total_ability_levels = sum(a.level for a in self.active_player.abilities.values())
        return total_ability_levels < self.active_player.level

    def get_ability(self, key: str) -> AbilityState:
        return self.active_player.abilities.get(key, AbilityState())

    @property
    def recent_ally_deaths(self) -> int:
        """Count ally deaths in the last 15 seconds from events."""
        cutoff = self.game_time - 15
        count = 0
        my_team_names = {a.summoner_name for a in self.allies}
        my_team_names.add(self.active_player.summoner_name)
        for e in self.events:
            if e.event_name == "ChampionKill" and e.event_time >= cutoff:
                victim = e.data.get("VictimName", "")
                if victim in my_team_names:
                    count += 1
        return count


class GameStateManager:
    """Polls the game server API and maintains a parsed GameState."""

    def __init__(self, game_server: GameServer):
        self.game_server = game_server
        self._state = GameState()
        self._last_poll = 0.0
        self._processed_event_count = 0

    @property
    def state(self) -> GameState:
        return self._state

    def update(self) -> GameState:
        """Poll the API if enough time has passed, parse into GameState."""
        now = time.time()
        if now - self._last_poll < POLL_INTERVAL:
            return self._state

        try:
            self.game_server.update_data()
            raw = json.loads(self.game_server.data)
            self._state = self._parse(raw)
            self._last_poll = now
        except (GameServerError, json.JSONDecodeError, KeyError) as e:
            log.debug(f"State update failed: {e}")

        return self._state

    def _parse(self, raw: dict) -> GameState:
        state = GameState()
        state.raw_data = raw
        state.game_time = float(raw.get("gameData", {}).get("gameTime", 0))

        # Parse active player
        ap_raw = raw.get("activePlayer", {})
        ap = ActivePlayerState()
        ap.summoner_name = ap_raw.get("summonerName", "")
        ap.level = int(ap_raw.get("level", 1))
        ap.current_gold = float(ap_raw.get("currentGold", 0))

        stats = ap_raw.get("championStats", {})
        ap.health = float(stats.get("currentHealth", 0))
        ap.max_health = float(stats.get("maxHealth", 1))
        ap.mana = float(stats.get("resourceValue", 0))
        ap.max_mana = float(stats.get("resourceMax", 1))

        # Parse abilities
        abilities_raw = ap_raw.get("abilities", {})
        for key in ("Q", "W", "E", "R"):
            ab_data = abilities_raw.get(key, {})
            ab = AbilityState(
                key=key,
                level=int(ab_data.get("abilityLevel", 0)),
                name=ab_data.get("displayName", ""),
            )
            ap.abilities[key] = ab

        # Parse summoner spells
        spells_raw = ap_raw.get("summonerSpells", {})
        ap.summoner_d = spells_raw.get("summonerSpellOne", {}).get("displayName", "")
        ap.summoner_f = spells_raw.get("summonerSpellTwo", {}).get("displayName", "")

        state.active_player = ap

        # Parse all players
        for p_raw in raw.get("allPlayers", []):
            p = PlayerState(
                summoner_name=p_raw.get("summonerName", ""),
                champion_name=p_raw.get("championName", ""),
                team=p_raw.get("team", ""),
                level=int(p_raw.get("level", 1)),
                is_dead=bool(p_raw.get("isDead", False)),
                respawn_timer=float(p_raw.get("respawnTimer", 0)),
                items=[item.get("displayName", "") for item in p_raw.get("items", [])],
                scores=p_raw.get("scores", {}),
            )
            state.all_players.append(p)

        # Parse events
        events_raw = raw.get("events", {}).get("Events", [])
        for ev_raw in events_raw:
            ev = GameEvent(
                event_name=ev_raw.get("EventName", ""),
                event_time=float(ev_raw.get("EventTime", 0)),
                data=ev_raw,
            )
            state.events.append(ev)

        return state
