import pytest

from factories import cfg_with, make_ctx, make_inventory, make_plan, make_state
from lemonade.engine.config import Config
from lemonade.engine.models import Forecast
from lemonade.engine.registry import EVENTS
from lemonade.engine.simulation import simulate_day
from lemonade.engine.types import StopReason, Weather

storm = EVENTS["storm"]


def test_only_possible_in_a_storm(cfg: Config) -> None:
    assert storm.chance(make_ctx(weather=Weather.STORM)) == cfg.events["storm"].base_chance
    for weather in (Weather.SUNNY, Weather.HOT, Weather.CLOUDY, Weather.RAINY):
        assert storm.chance(make_ctx(weather=weather)) == 0.0


def test_closes_the_stand_with_a_message() -> None:
    outcome = storm.on_day_start(make_ctx(weather=Weather.STORM))
    assert outcome.close_stand
    assert outcome.message and "storm" in outcome.message.lower()


@pytest.mark.parametrize("seed", range(3))
def test_forced_storm_closes_stand_in_simulation(seed: int) -> None:
    cfg = cfg_with(event_chances={"storm": 1.0}, accuracy=1.0)
    stock = make_inventory(lemon=60, sugar=40, ice=600, cup=200)
    state = make_state(seed=seed, forecast=Forecast(Weather.STORM, 55), inventory=stock)
    _, result = simulate_day(state, make_plan(), cfg)
    assert result.stop_reason is StopReason.STAND_CLOSED
    assert result.cups_sold == 0
    assert any("storm" in m.lower() for m in result.events)
