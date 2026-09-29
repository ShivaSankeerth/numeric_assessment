from factories import make_ctx, make_inventory, make_plan, make_state
from lemonade.engine.config import Config
from lemonade.engine.registry import MODIFIERS
from lemonade.engine.simulation import simulate_day
from lemonade.engine.types import Factor

weekend = MODIFIERS["day_of_week"]
holiday = MODIFIERS["holiday"]


def test_weekend_boosts_traffic(cfg: Config) -> None:
    (effect,) = weekend.effects(make_ctx(state=make_state(day=6)))
    assert (effect.factor, effect.op) == (Factor.TRAFFIC, "mul")
    assert effect.value == cfg.calendar.weekend_traffic_mul
    assert effect.reason == "Weekend (Saturday): +25% foot traffic"
    assert effect.source == "day_of_week"


def test_weekdays_have_no_effect() -> None:
    assert weekend.effects(make_ctx(state=make_state(day=1))) == []


def test_holiday_boosts_traffic_with_its_name() -> None:
    (effect,) = holiday.effects(make_ctx(state=make_state(day=4)))
    assert effect.factor is Factor.TRAFFIC and effect.value == 1.5
    assert effect.reason == "Holiday (Independence Day): +50% foot traffic"
    assert holiday.effects(make_ctx(state=make_state(day=3))) == []


def test_simulation_sets_holiday_and_weekend_effects(cfg: Config) -> None:
    stock = make_inventory(lemon=60, sugar=40, ice=600, cup=200)
    _, result = simulate_day(make_state(day=4, inventory=stock), make_plan(), cfg)
    assert "holiday" in {e.source for e in result.effects}
    _, sat = simulate_day(make_state(day=6, inventory=stock), make_plan(), cfg)
    assert "day_of_week" in {e.source for e in sat.effects}
