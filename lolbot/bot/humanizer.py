"""
Natural variance layer for input actions. Replaces fixed sleep() calls
with randomized delays and adds coordinate jitter for more human-like behavior.
"""

import random
from time import sleep

from lolbot.system import mouse, keys, window


# Delay ranges (seconds)
CLICK_DELAY = (0.7, 1.5)
FAST_CLICK_DELAY = (0.3, 0.7)
KEY_DELAY = (0.6, 1.3)
THINK_PAUSE = (0.3, 1.2)

# Coordinate jitter ratio (±pixels relative to window width)
JITTER_RATIO = 0.008


def _delay(delay_range: tuple) -> None:
    sleep(random.uniform(*delay_range))


def _jitter(ratio: tuple) -> tuple:
    """Apply small random offset to coordinates."""
    jx = random.uniform(-JITTER_RATIO, JITTER_RATIO)
    jy = random.uniform(-JITTER_RATIO, JITTER_RATIO)
    return (
        max(0.0, min(1.0, ratio[0] + jx)),
        max(0.0, min(1.0, ratio[1] + jy)),
    )


def think() -> None:
    """Simulate a brief thinking pause between decisions."""
    _delay(THINK_PAUSE)


def left_click(ratio: tuple, fast: bool = False) -> None:
    """Move mouse and left-click at a screen ratio coordinate with jitter."""
    coords = window.convert_ratio(_jitter(ratio), window.GAME_WINDOW)
    mouse.move(coords)
    mouse.left_click()
    _delay(FAST_CLICK_DELAY if fast else CLICK_DELAY)


def right_click(ratio: tuple, fast: bool = False) -> None:
    """Move mouse and right-click at a screen ratio coordinate with jitter."""
    coords = window.convert_ratio(_jitter(ratio), window.GAME_WINDOW)
    mouse.move(coords)
    mouse.right_click()
    _delay(FAST_CLICK_DELAY if fast else CLICK_DELAY)


def attack_click(ratio: tuple) -> None:
    """A-click toward a screen ratio coordinate with jitter."""
    coords = window.convert_ratio(_jitter(ratio), window.GAME_WINDOW)
    mouse.move(coords)
    keys.key_down('a')
    sleep(random.uniform(0.08, 0.15))
    mouse.left_click()
    sleep(random.uniform(0.08, 0.15))
    mouse.left_click()
    keys.key_up('a')
    _delay(CLICK_DELAY)


def keypress(key: str) -> None:
    """Press a key with the game window focused."""
    window.check_window_exists(window.GAME_WINDOW)
    keys.press_and_release(key)
    _delay(KEY_DELAY)


def fast_keypress(key: str) -> None:
    """Press a key with a shorter delay."""
    window.check_window_exists(window.GAME_WINDOW)
    keys.press_and_release(key)
    _delay(FAST_CLICK_DELAY)
