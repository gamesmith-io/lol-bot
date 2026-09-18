"""
Game orchestrator. Plays through a single League of Legends match
using the data-driven decision engine.
"""

import logging
from time import sleep
from datetime import datetime, timedelta

from lolbot.lcu.game_server import GameServer, GameServerError
from lolbot.system import window, cmd

from lolbot.bot.constants import CENTER_OF_SCREEN, MAX_GAME_TIME, MAX_SERVER_ERRORS, Lane
from lolbot.bot.game_state import GameState, GameStateManager
from lolbot.bot.decision import DecisionEngine, determine_phase
from lolbot.bot.actions import ActionExecutor
from lolbot.bot import humanizer, items, combat, lane

log = logging.getLogger(__name__)


class GameError(Exception):
    """Indicates the game should be terminated"""
    pass


def play_game() -> None:
    """Plays a single game of League of Legends using the decision engine."""
    game_server = GameServer()
    try:
        wait_for_game_window()
        wait_for_connection(game_server)
        game_loop(game_server)
    except GameError as e:
        log.warning(e)
        cmd.run(cmd.CLOSE_GAME)
        sleep(30)
    except window.WindowNotFound:
        log.info("Game Complete")


def wait_for_game_window() -> None:
    """Loop that waits for game window to open."""
    for i in range(120):
        sleep(1)
        try:
            if window.check_window_exists(window.GAME_WINDOW):
                log.info("Game Launched")
                humanizer.left_click(CENTER_OF_SCREEN)
                humanizer.left_click(CENTER_OF_SCREEN)
                return
        except window.WindowNotFound:
            pass
    raise GameError("Game window did not open")


def wait_for_connection(game_server: GameServer) -> None:
    """Wait for the game server API to become reachable."""
    for i in range(120):
        if game_server.is_running():
            return
        sleep(1)
    raise GameError("Game window opened but connection failed")


def _early_game_setup(state: GameState, active_lane: Lane) -> None:
    """One-shot setup at fountain: buy, upgrade, lock camera, move to lane."""
    log.info("Early game setup: buy + upgrade + lock camera + move to lane")
    items.buy_items(state)
    combat.upgrade_abilities(state)
    humanizer.keypress('y')  # lock camera
    lane.move_to_lane(active_lane)


def game_loop(game_server: GameServer) -> None:
    """Main game loop: update state, decide, execute."""
    state_mgr = GameStateManager(game_server)
    engine = DecisionEngine()
    executor = ActionExecutor()

    server_errors = 0
    last_phase_log = None
    was_dead = False
    did_early_setup = False

    while True:
        try:
            state = state_mgr.update()
        except GameServerError:
            server_errors += 1
            if server_errors >= MAX_SERVER_ERRORS:
                raise GameError("Max Server Errors reached")
            sleep(1)
            continue

        server_errors = 0

        # Check game time limit
        if state.game_time >= MAX_GAME_TIME:
            raise GameError("Game has exceeded the max time limit")

        # Track death state for respawn buying
        if state.is_dead:
            was_dead = True
            sleep(2)
            continue

        # Respawn at fountain: buy items and upgrade before resuming
        if was_dead:
            log.info("Respawned at fountain: buying items and upgrading")
            items.buy_items(state)
            combat.upgrade_abilities(state)
            was_dead = False

        # Determine phase
        phase = determine_phase(state.game_time)
        if phase != last_phase_log:
            log.info(f"Phase: {phase.name} (time={state.game_time:.0f}s)")
            last_phase_log = phase

        # Loading screen wait
        if phase.name == "LOADING":
            start = datetime.now()
            while state.game_time < 3:
                sleep(2)
                if datetime.now() - start > timedelta(minutes=10):
                    raise GameError("Loading screen max time limit exceeded")
                try:
                    state = state_mgr.update()
                except GameServerError:
                    pass
            humanizer.left_click(CENTER_OF_SCREEN)
            log.info("Game Started")

            # One-shot early game setup
            if not did_early_setup:
                _early_game_setup(state, executor.lane)
                did_early_setup = True
            continue

        # Think pause between decisions
        humanizer.think()

        # Decide and execute
        action = engine.decide(state, phase)
        executor.execute(action.action, state, phase)
