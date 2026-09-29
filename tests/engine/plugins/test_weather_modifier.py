from factories import make_ctx
from lemonade.engine.config import Config
from lemonade.engine.registry import MODIFIERS
from lemonade.engine.types import Factor, Weather


def test_hot_weather_boosts_traffic_and_price_tolerance(cfg: Config) -> None:
    effects = MODIFIERS["weather"].effects(make_ctx(weather=Weather.HOT))
    by_factor = {e.factor: e for e in effects}
    assert by_factor[Factor.TRAFFIC].value == cfg.weather.traffic[Weather.HOT]
    assert by_factor[Factor.PRICE_TOLERANCE].value == 1.2
    assert all(e.reason and e.source == "weather" for e in effects)
    assert by_factor[Factor.TRAFFIC].reason == "Hot weather: +30% foot traffic"


def test_rain_cuts_traffic_without_price_effect() -> None:
    effects = MODIFIERS["weather"].effects(make_ctx(weather=Weather.RAINY))
    assert [e.factor for e in effects] == [Factor.TRAFFIC]
    assert effects[0].value < 1
