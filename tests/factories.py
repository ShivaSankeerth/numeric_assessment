"""Test factories. Use these instead of hand-building state (CLAUDE.md section 11)."""

from __future__ import annotations

import random
from dataclasses import replace
from functools import cache
from typing import Any

from lemonade.engine.config import Config, load_config
from lemonade.engine.models import (
    Batch,
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
    """The packaged content config, loaded once per test session."""
    return load_config()


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


def make_plan(purchases: dict[str, int] | None = None, **overrides: Any) -> DayPlan:
    """`make_plan({"lemon": 1, "cup": 1}, price_per_cup=75)`; defaults: no purchases, 50c."""
    plan = DayPlan(
        purchases=tuple(Purchase(Item(k), v) for k, v in (purchases or {}).items()),
        recipe=Recipe(),
        price_per_cup=50,
    )
    return replace(plan, **overrides)
