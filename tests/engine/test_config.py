import copy
from typing import Any

import pytest

from lemonade.engine.config import BulkTier, Config, parse_config, read_raw_content
from lemonade.engine.errors import ConfigError
from lemonade.engine.types import Item, Weather


def test_defaults_match_spec(cfg: Config) -> None:
    assert cfg.game.starting_cash == 2000
    assert cfg.game.starting_reputation == 0.3
    assert cfg.game.cups_per_pitcher == 12

    lemon = cfg.items[Item.LEMON]
    assert (lemon.pack_size, lemon.pack_price, lemon.shelf_life_days) == (12, 400, 5)
    assert lemon.tiers == (BulkTier(3, 10), BulkTier(6, 20))
    assert (cfg.items[Item.SUGAR].pack_size, cfg.items[Item.SUGAR].pack_price) == (8, 300)
    assert cfg.items[Item.ICE].melts
    assert cfg.items[Item.ICE].pack_price == 150
    assert (cfg.items[Item.CUP].pack_size, cfg.items[Item.CUP].pack_price) == (50, 250)
    assert cfg.items[Item.CUP].shelf_life_days is None


def test_weather_and_plugin_content_loaded(cfg: Config) -> None:
    assert set(cfg.weather.traffic) == set(Weather)
    assert cfg.weather.price_tolerance[Weather.RAINY] == 1.0  # default for missing
    assert "park" in cfg.locations
    assert cfg.upgrades["cooler"].params["ice_retention"] == 0.5
    assert cfg.events["heat_wave"].base_chance == pytest.approx(0.15)


@pytest.fixture
def raw() -> dict[str, Any]:
    return copy.deepcopy(read_raw_content())


def test_missing_key_raises(raw: dict[str, Any]) -> None:
    del raw["items"]["items"]["lemon"]["pack_price"]
    with pytest.raises(ConfigError, match="pack_price"):
        parse_config(raw)


def test_negative_price_raises(raw: dict[str, Any]) -> None:
    raw["items"]["items"]["cup"]["pack_price"] = -1
    with pytest.raises(ConfigError, match="pack_price"):
        parse_config(raw)


def test_missing_file_raises(raw: dict[str, Any]) -> None:
    del raw["events"]
    with pytest.raises(ConfigError, match="events"):
        parse_config(raw)


def test_unknown_item_raises(raw: dict[str, Any]) -> None:
    raw["items"]["items"]["straw"] = {"pack_size": 1, "pack_price": 1}
    with pytest.raises(ConfigError, match="straw"):
        parse_config(raw)


def test_market_content_loaded() -> None:
    market = parse_config(read_raw_content()).market
    assert market.fluctuation and market.shortages
    assert market.shortage_item is Item.LEMON
    assert market.shortage_markup_pct == 50


def test_bad_market_values_raise(raw: dict[str, Any]) -> None:
    raw["items"]["market"]["shortage_item"] = "straw"
    with pytest.raises(ConfigError, match="shortage_item"):
        parse_config(raw)
    raw["items"]["market"]["shortage_item"] = "lemon"
    raw["items"]["market"]["fluctuation"] = "yes"
    with pytest.raises(ConfigError, match="fluctuation"):
        parse_config(raw)
