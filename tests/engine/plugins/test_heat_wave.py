import pytest

from factories import make_ctx
from lemonade.engine.config import Config
from lemonade.engine.registry import EVENTS
from lemonade.engine.types import Factor, Weather

heat_wave = EVENTS["heat_wave"]


@pytest.mark.parametrize("weather", [Weather.SUNNY, Weather.HOT])
def test_can_fire_on_warm_days(cfg: Config, weather: Weather) -> None:
    assert heat_wave.chance(make_ctx(weather=weather)) == cfg.events["heat_wave"].base_chance


@pytest.mark.parametrize("weather", [Weather.CLOUDY, Weather.RAINY, Weather.STORM])
def test_never_fires_on_cool_days(weather: Weather) -> None:
    assert heat_wave.chance(make_ctx(weather=weather)) == 0.0


def test_boosts_traffic_with_message() -> None:
    outcome = heat_wave.on_day_start(make_ctx(weather=Weather.HOT))
    (effect,) = outcome.effects
    assert (effect.factor, effect.op, effect.value) == (Factor.TRAFFIC, "mul", 1.4)
    assert effect.reason == "Heat wave: +40% foot traffic"
    assert outcome.message
    assert not outcome.close_stand
