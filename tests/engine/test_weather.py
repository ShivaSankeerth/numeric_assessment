import pytest

from factories import fixed_rng
from lemonade.engine.config import Config
from lemonade.engine.models import Forecast
from lemonade.engine.rng import day_rng
from lemonade.engine.types import Weather
from lemonade.engine.weather import WEATHER_SCALE, generate_forecast, resolve


def in_band(cfg: Config, weather: Weather, temp: int) -> bool:
    low, high = cfg.weather.temp_range[weather]
    return low <= temp <= high


def test_forecast_is_deterministic_and_in_band(cfg: Config) -> None:
    for day in range(1, 50):
        a = generate_forecast(day_rng(7, day, "forecast"), cfg)
        b = generate_forecast(day_rng(7, day, "forecast"), cfg)
        assert a == b
        assert in_band(cfg, a.predicted, a.predicted_temp_f)


def test_forecast_uses_every_weather(cfg: Config) -> None:
    seen = {generate_forecast(fixed_rng(s), cfg).predicted for s in range(500)}
    assert seen == set(Weather)


def test_resolve_accuracy_and_one_step_shift(cfg: Config) -> None:
    forecast = Forecast(Weather.CLOUDY, 70)
    hits = 0
    for seed in range(2000):
        actual, temp = resolve(forecast, fixed_rng(seed), cfg)
        steps = abs(WEATHER_SCALE.index(actual) - WEATHER_SCALE.index(forecast.predicted))
        assert steps <= 1
        assert in_band(cfg, actual, temp)
        hits += steps == 0
    assert hits / 2000 == pytest.approx(cfg.weather.accuracy, abs=0.05)


@pytest.mark.parametrize(
    ("predicted", "only_miss"), [(Weather.STORM, Weather.RAINY), (Weather.HOT, Weather.SUNNY)]
)
def test_misses_at_scale_ends_shift_inward(
    cfg: Config, predicted: Weather, only_miss: Weather
) -> None:
    outcomes = {resolve(Forecast(predicted, 70), fixed_rng(s), cfg)[0] for s in range(300)}
    assert outcomes == {predicted, only_miss}


def test_correct_forecast_temp_is_near_prediction(cfg: Config) -> None:
    forecast = Forecast(Weather.SUNNY, 80)
    for seed in range(200):
        actual, temp = resolve(forecast, fixed_rng(seed), cfg)
        if actual is Weather.SUNNY:
            assert abs(temp - 80) <= cfg.weather.temp_noise
