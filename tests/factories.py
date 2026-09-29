"""Test factories. Use these instead of hand-building state (CLAUDE.md section 11)."""

from __future__ import annotations

import random
from dataclasses import replace
from functools import cache
from typing import Any

from lemonade.engine.config import Config, load_config
from lemonade.engine.models import (
    Batch,
    DayContext,
    DayPlan,
    Forecast,
    GameState,
    Inventory,
    Purchase,
    Recipe,
)
from lemonade.engine.types import Item, Weather


@cache
def default_cfg() -> Config:
    """The packaged content config with daily supplier price fluctuation and shortages OFF.

    Loaded once per test session. Fixed base prices keep money assertions stable (e.g. the UI's
    "Cart: $11.00"); the real game (`load_config()`) has both ON. Test them via `market_cfg()`.
    """
    cfg = load_config()
    return replace(cfg, market=replace(cfg.market, fluctuation=False, shortages=False))


def market_cfg(**market_overrides: Any) -> Config:
    """`default_cfg()` with `[market]` fields overridden, e.g. `market_cfg(fluctuation=True)`."""
    cfg = default_cfg()
    return replace(cfg, market=replace(cfg.market, **market_overrides))


def fixed_rng(seed: int = 0) -> random.Random:
    return random.Random(seed)


def make_inventory(expires_on_day: int | None = None, **counts: int) -> Inventory:
    """`make_inventory(lemon=12, cup=50)` -> one batch per item. Lemons get `expires_on_day`."""
    batches: dict[Item, tuple[Batch, ...]] = {item: () for item in Item}
    for name, qty in counts.items():
        item = Item(name)
        if qty > 0:
            expiry = expires_on_day if item is Item.LEMON else None
            batches[item] = (Batch(qty=qty, expires_on_day=expiry),)
    return Inventory(batches=batches)


def make_state(cfg: Config | None = None, **overrides: Any) -> GameState:
    """A fresh day-1 game state (seed 42, sunny forecast) with any field overridden."""
    cfg = cfg or default_cfg()
    state = GameState(
        seed=42,
        day=1,
        cash=cfg.game.starting_cash,
        inventory=Inventory.empty(),
        reputation=cfg.game.starting_reputation,
        upgrades=frozenset(),
        forecast=Forecast(predicted=Weather.SUNNY, predicted_temp_f=80),
        history=(),
    )
    return replace(state, **overrides)


def make_plan(buy: dict[str, int] | None = None, **overrides: Any) -> DayPlan:
    """`make_plan({"lemon": 1, "cup": 1}, price_per_cup=75)`: `buy` maps item -> packs.

    Defaults: no purchases, default recipe, 50c. Pass `purchases=` to set raw Purchase tuples.
    """
    plan = DayPlan(
        purchases=tuple(Purchase(Item(k), v) for k, v in (buy or {}).items()),
        recipe=Recipe(),
        price_per_cup=50,
    )
    return replace(plan, **overrides)


def make_ctx(
    state: GameState | None = None,
    plan: DayPlan | None = None,
    weather: Weather = Weather.SUNNY,
    temp_f: int = 80,
    cfg: Config | None = None,
    **overrides: Any,
) -> DayContext:
    """A DayContext for testing plugins and demand in isolation."""
    ctx = DayContext(
        state=state or make_state(),
        plan=plan or make_plan(),
        weather=weather,
        temp_f=temp_f,
        day_of_week=0,
        holiday=None,
        rng=fixed_rng(),
        cfg=cfg or default_cfg(),
    )
    return replace(ctx, **overrides)


def cfg_with(
    cfg: Config | None = None,
    *,
    event_chances: dict[str, float] | None = None,
    **weather_overrides: Any,
) -> Config:
    """Config copy with event base chances and/or weather fields overridden.

    `cfg_with(event_chances={"heat_wave": 1.0}, accuracy=1.0)` forces a heat wave and a
    perfectly accurate forecast.
    """
    cfg = cfg or default_cfg()
    events = dict(cfg.events)
    for event_id, chance in (event_chances or {}).items():
        events[event_id] = replace(events[event_id], base_chance=chance)
    return replace(cfg, events=events, weather=replace(cfg.weather, **weather_overrides))
