"""Achievements (content/achievements.toml), checked at the end of every day by `game.end_day`.

Unlocked ids are added to `GameState.achievements` and never removed; the ids first unlocked on
a day are also recorded on that day's `DayResult.achievements_unlocked`.
"""

from __future__ import annotations

from dataclasses import replace

from lemonade.engine.config import AchievementConfig, Config
from lemonade.engine.models import GameState
from lemonade.engine.types import AchievementKind, GameStatus


def is_met(achievement: AchievementConfig, state: GameState) -> bool:
    """Whether the (end-of-day) state satisfies one achievement's condition."""
    threshold = achievement.threshold
    match achievement.kind:
        case AchievementKind.CASH_AT_LEAST:
            return state.cash >= threshold
        case AchievementKind.DAYS_SURVIVED:
            return state.status is GameStatus.PLAYING and len(state.history) >= threshold
        case AchievementKind.CUPS_SOLD_TOTAL:
            return sum(r.cups_sold for r in state.history) >= threshold
        case AchievementKind.PERFECT_RECIPE:
            last = state.history[-1] if state.history else None
            return last is not None and last.cups_sold > 0 and last.taste_score >= threshold
    return False


def newly_unlocked(state: GameState, cfg: Config) -> tuple[str, ...]:
    """Ids met now but not yet owned, in content (display) order."""
    return tuple(
        ach_id
        for ach_id, ach in cfg.achievements.items()
        if ach_id not in state.achievements and is_met(ach, state)
    )


def unlock(state: GameState, cfg: Config) -> GameState:
    """Add newly met achievements to the state and to the latest day's result."""
    new = newly_unlocked(state, cfg)
    if not new:
        return state
    history = state.history
    if history:
        last = history[-1]
        last = replace(last, achievements_unlocked=(*last.achievements_unlocked, *new))
        history = (*history[:-1], last)
    return replace(state, achievements=state.achievements | frozenset(new), history=history)
