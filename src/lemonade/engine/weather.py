"""Forecast generation and resolving the actual weather from a forecast (assumption A5)."""

from __future__ import annotations

import random

from lemonade.engine.config import Config
from lemonade.engine.models import Forecast
from lemonade.engine.types import Weather

# Ordinal scale used for "the forecast was off by one step".
WEATHER_SCALE: tuple[Weather, ...] = (
    Weather.STORM,
    Weather.RAINY,
    Weather.CLOUDY,
    Weather.SUNNY,
    Weather.HOT,
)


def generate_forecast(rng: random.Random, cfg: Config) -> Forecast:
    """Pick tomorrow's forecast from the configured weights; temp uniform within that band."""
    options = list(WEATHER_SCALE)
    weights = [cfg.weather.forecast_weights[w] for w in options]
    predicted = rng.choices(options, weights=weights)[0]
    low, high = cfg.weather.temp_range[predicted]
    return Forecast(predicted=predicted, predicted_temp_f=rng.randint(low, high))


def _shift_one_step(weather: Weather, rng: random.Random) -> Weather:
    idx = WEATHER_SCALE.index(weather)
    if idx == 0:
        return WEATHER_SCALE[1]
    if idx == len(WEATHER_SCALE) - 1:
        return WEATHER_SCALE[-2]
    return WEATHER_SCALE[idx + rng.choice((-1, 1))]


def resolve(forecast: Forecast, rng: random.Random, cfg: Config) -> tuple[Weather, int]:
    """Actual (weather, temp_f) for the day.

    With probability `accuracy` the forecast holds and temp is predicted +/- `temp_noise`
    (clamped to the band); otherwise weather shifts exactly one step on WEATHER_SCALE and temp
    is re-rolled within the new band.
    """
    if rng.random() < cfg.weather.accuracy:
        low, high = cfg.weather.temp_range[forecast.predicted]
        noise = rng.randint(-cfg.weather.temp_noise, cfg.weather.temp_noise)
        return forecast.predicted, max(low, min(high, forecast.predicted_temp_f + noise))
    actual = _shift_one_step(forecast.predicted, rng)
    low, high = cfg.weather.temp_range[actual]
    return actual, rng.randint(low, high)
