from dataclasses import replace

from factories import cfg_with, make_ctx, make_inventory, make_plan, make_state
from lemonade.engine.config import Config
from lemonade.engine.models import DayResult, Forecast, Recipe
from lemonade.engine.registry import EVENTS
from lemonade.engine.simulation import simulate_day
from lemonade.engine.types import Weather

inspector = EVENTS["inspector"]
STOCK = {"lemon": 60, "sugar": 40, "ice": 600, "cup": 200}


def _result(cups_sold: int = 10, taste: float = 0.9) -> DayResult:
    _, result = simulate_day(make_state(), make_plan(), cfg_with(event_chances={"inspector": 0}))
    return replace(result, cups_sold=cups_sold, taste_score=taste)


def test_random_chance_any_day(cfg: Config) -> None:
    assert inspector.chance(make_ctx(weather=Weather.RAINY)) == cfg.events["inspector"].base_chance


def test_good_lemonade_passes() -> None:
    outcome = inspector.on_day_end(make_ctx(), _result())
    assert outcome.cash_delta == 0
    assert outcome.message and "satisfied" in outcome.message


def test_bad_taste_is_fined_from_content(cfg: Config) -> None:
    outcome = inspector.on_day_end(make_ctx(), _result(taste=0.2))
    assert outcome.cash_delta == -cfg.events["inspector"].params["fine"] == -500
    assert outcome.message == "The health inspector fined you $5.00: the lemonade tastes awful."


def test_no_ice_on_a_hot_day_is_fined() -> None:
    ctx = make_ctx(weather=Weather.HOT, plan=make_plan(recipe=Recipe(6, 4, 0)))
    assert inspector.on_day_end(ctx, _result()).cash_delta == -500
    cool = make_ctx(weather=Weather.CLOUDY, plan=make_plan(recipe=Recipe(6, 4, 0)))
    assert inspector.on_day_end(cool, _result()).cash_delta == 0


def test_nothing_sold_nothing_to_inspect() -> None:
    assert inspector.on_day_end(make_ctx(), _result(cups_sold=0, taste=0.0)).message is None


def test_fine_is_charged_in_simulation() -> None:
    bad = make_plan(recipe=Recipe(1, 12, 10), price_per_cup=5)  # awful but cheap
    state = make_state(inventory=make_inventory(**STOCK), forecast=Forecast(Weather.SUNNY, 80))
    _, calm = simulate_day(state, bad, cfg_with(event_chances={"inspector": 0.0}))
    _, fined = simulate_day(state, bad, cfg_with(event_chances={"inspector": 1.0}))
    assert fined.cups_sold == calm.cups_sold > 0
    assert fined.cash_end == calm.cash_end - 500
    assert any("fined" in m for m in fined.events)
