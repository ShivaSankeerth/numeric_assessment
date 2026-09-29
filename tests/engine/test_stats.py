from dataclasses import replace

from factories import make_inventory, make_plan, make_state
from lemonade.engine.config import Config
from lemonade.engine.game import play_day
from lemonade.engine.models import Effect
from lemonade.engine.stats import (
    best_day,
    cash_series,
    effect_magnitude,
    ranked_effects,
    sell_through,
    totals,
    worst_day,
)
from lemonade.engine.types import Factor

STOCK = {"lemon": 60, "sugar": 40, "ice": 600, "cup": 200}


def test_empty_history() -> None:
    state = make_state()
    assert cash_series(state) == ()
    assert best_day(state) is None
    assert worst_day(state) is None
    assert totals(state).days == 0
    assert sell_through(state) == 0.0


def test_stats_over_played_days(cfg: Config) -> None:
    state = make_state(inventory=make_inventory(**STOCK))
    for plan in (make_plan(), make_plan({"ice": 2}), make_plan()):
        state, _ = play_day(state, plan, cfg)
    series = cash_series(state)
    assert series[0] == 2000
    assert series[-1] == state.cash
    assert len(series) == 4
    assert [r.cash_end for r in state.history] == list(series[1:])
    t = totals(state)
    assert t.days == 3
    assert t.profit == state.cash - 2000
    assert t.cups_sold == sum(r.cups_sold for r in state.history)
    assert best_day(state).profit >= worst_day(state).profit  # type: ignore[union-attr]
    assert 0 <= sell_through(state) <= 1
    assert sell_through(state) == t.cups_sold / t.customers


def _effect(op: str, value: float, source: str) -> Effect:
    return Effect(Factor.TRAFFIC, op, value, reason=source, source=source)  # type: ignore[arg-type]


def test_effect_magnitude() -> None:
    assert round(effect_magnitude(_effect("mul", 1.4, "a")), 9) == 0.4
    assert round(effect_magnitude(_effect("mul", 0.5, "a")), 9) == 0.5
    assert effect_magnitude(_effect("add", -0.2, "a")) == 0.2
    assert effect_magnitude(_effect("mul", 1.0, "a")) == 0.0


def test_ranked_effects_strongest_first(cfg: Config) -> None:
    state = make_state(inventory=make_inventory(**STOCK))
    _, result = play_day(state, make_plan(), cfg)
    small, big, neg = (
        _effect("mul", 1.1, "small"),
        _effect("mul", 1.5, "big"),
        _effect("add", -0.3, "neg"),
    )
    result = replace(result, effects=(small, big, neg))
    assert [e.source for e in ranked_effects(result)] == ["big", "neg", "small"]
