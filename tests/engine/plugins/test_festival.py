from factories import cfg_with, make_ctx, make_inventory, make_plan, make_state
from lemonade.engine.config import Config
from lemonade.engine.registry import EVENTS
from lemonade.engine.simulation import simulate_day
from lemonade.engine.types import Factor, Weather

festival = EVENTS["festival"]


def test_small_chance_except_in_storms(cfg: Config) -> None:
    base = cfg.events["festival"].base_chance
    assert 0 < base <= 0.1
    assert festival.chance(make_ctx(weather=Weather.CLOUDY)) == base
    assert festival.chance(make_ctx(weather=Weather.STORM)) == 0.0


def test_boosts_traffic_with_message() -> None:
    outcome = festival.on_day_start(make_ctx())
    (effect,) = outcome.effects
    assert (effect.factor, effect.op, effect.value) == (Factor.TRAFFIC, "mul", 1.5)
    assert effect.reason == "Town festival: +50% foot traffic"
    assert outcome.message and not outcome.close_stand


def test_forced_festival_raises_customers() -> None:
    stock = make_inventory(lemon=60, sugar=40, ice=600, cup=200)
    state = make_state(inventory=stock)
    _, quiet = simulate_day(state, make_plan(), cfg_with(event_chances={"festival": 0.0}))
    _, busy = simulate_day(state, make_plan(), cfg_with(event_chances={"festival": 1.0}))
    assert busy.potential_customers > quiet.potential_customers
    assert "festival" in {e.source for e in busy.effects}
