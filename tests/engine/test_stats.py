from factories import make_inventory, make_plan, make_state
from lemonade.engine.config import Config
from lemonade.engine.game import play_day
from lemonade.engine.stats import best_day, cash_series, totals, worst_day

STOCK = {"lemon": 60, "sugar": 40, "ice": 600, "cup": 200}


def test_empty_history() -> None:
    state = make_state()
    assert cash_series(state) == ()
    assert best_day(state) is None
    assert worst_day(state) is None
    assert totals(state).days == 0


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
