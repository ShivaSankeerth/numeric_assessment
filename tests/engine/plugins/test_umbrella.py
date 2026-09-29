import pytest

from factories import make_ctx
from lemonade.engine.config import Config
from lemonade.engine.registry import UPGRADE_HANDLERS
from lemonade.engine.types import Factor, Weather

umbrella = UPGRADE_HANDLERS["umbrella"]


@pytest.mark.parametrize("weather", [Weather.RAINY, Weather.STORM])
def test_halves_the_wet_weather_penalty(cfg: Config, weather: Weather) -> None:
    (effect,) = umbrella.effects(make_ctx(weather=weather))
    t = cfg.weather.traffic[weather]
    assert effect.factor is Factor.TRAFFIC and effect.op == "mul"
    assert t * effect.value == pytest.approx(1 - (1 - t) / 2)
    assert weather.value in effect.reason and effect.source == "umbrella"


def test_rain_penalty_45_becomes_725(cfg: Config) -> None:
    (effect,) = umbrella.effects(make_ctx(weather=Weather.RAINY))
    assert cfg.weather.traffic[Weather.RAINY] * effect.value == pytest.approx(0.725)


@pytest.mark.parametrize("weather", [Weather.SUNNY, Weather.HOT, Weather.CLOUDY])
def test_no_effect_on_dry_days(weather: Weather) -> None:
    assert umbrella.effects(make_ctx(weather=weather)) == []
