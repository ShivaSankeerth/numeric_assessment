"""Typed configuration built from `content/*.toml`.

`parse_config` is pure. `load_config` is the ONLY file access in `engine/`; it is called by entry
points (UI, sim, tests), never by engine functions, which always receive a `Config`.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, fields
from importlib import resources
from pathlib import Path
from typing import Any

from lemonade.engine.errors import ConfigError
from lemonade.engine.types import Cents, Item, Weather

CONTENT_FILES = ("game", "items", "upgrades", "events", "locations")


@dataclass(frozen=True, slots=True)
class BulkTier:
    min_packs: int
    discount_pct: int


@dataclass(frozen=True, slots=True)
class ItemConfig:
    pack_size: int
    pack_price: Cents
    tiers: tuple[BulkTier, ...]  # sorted by min_packs ascending
    shelf_life_days: int | None
    melts: bool


@dataclass(frozen=True, slots=True)
class RecipeLimits:
    lemons: tuple[int, int]
    sugar: tuple[int, int]
    ice: tuple[int, int]


@dataclass(frozen=True, slots=True)
class GameConfig:
    starting_cash: Cents
    starting_reputation: float
    cups_per_pitcher: int
    recipe_limits: RecipeLimits
    price_limits: tuple[Cents, Cents]


@dataclass(frozen=True, slots=True)
class DemandConfig:
    base_fair_price: Cents
    base_prob: float
    prob_scale: float
    reputation_offset: float
    max_buy_prob: float
    max_price_factor: float
    ideal_lemons: int
    ideal_sugar: int
    ideal_ice_base: int
    ideal_ice_temp_f: int
    ideal_ice_per_10f: float
    taste_penalty_per_unit: float
    reputation_rate: float
    loss_price_threshold: float
    loss_taste_threshold: float
    reputation_taste_weight: float
    reputation_neutral: float
    reputation_full_volume: int


@dataclass(frozen=True, slots=True)
class HolidayConfig:
    name: str
    traffic_mul: float


@dataclass(frozen=True, slots=True)
class CalendarConfig:
    """Day 1 is `day_names[0]`; the week repeats every `len(day_names)` days."""

    day_names: tuple[str, ...]
    weekend_days: frozenset[int]  # indexes into day_names
    weekend_traffic_mul: float
    holidays: Mapping[int, HolidayConfig]  # keyed by game day number


@dataclass(frozen=True, slots=True)
class DifficultyConfig:
    name: str
    description: str
    starting_cash: Cents
    traffic_mul: float
    supply_price_pct: int  # 100 = base supplier prices


@dataclass(frozen=True, slots=True)
class MarketConfig:
    """Daily supplier price movement (`market.todays_pack_prices`). Percentages are whole ints."""

    fluctuation: bool
    fluctuation_pct: int
    shortages: bool
    shortage_chance: float
    shortage_item: Item
    shortage_markup_pct: int


@dataclass(frozen=True, slots=True)
class WeatherConfig:
    accuracy: float
    temp_noise: int
    forecast_weights: Mapping[Weather, float]
    temp_range: Mapping[Weather, tuple[int, int]]
    traffic: Mapping[Weather, float]
    price_tolerance: Mapping[Weather, float]


@dataclass(frozen=True, slots=True)
class LocationConfig:
    name: str
    base_traffic: int
    rent: Cents
    description: str


@dataclass(frozen=True, slots=True)
class UpgradeConfig:
    name: str
    cost: Cents
    description: str
    params: Mapping[str, float]


@dataclass(frozen=True, slots=True)
class EventConfig:
    name: str
    base_chance: float
    params: Mapping[str, float]


@dataclass(frozen=True, slots=True)
class Config:
    game: GameConfig
    items: Mapping[Item, ItemConfig]
    demand: DemandConfig
    weather: WeatherConfig
    locations: Mapping[str, LocationConfig]
    upgrades: Mapping[str, UpgradeConfig]
    events: Mapping[str, EventConfig]
    market: MarketConfig
    calendar: CalendarConfig
    difficulties: Mapping[str, DifficultyConfig]  # must include "normal"


Table = Mapping[str, Any]


def _get(table: Table, key: str, path: str) -> Any:
    if key not in table:
        raise ConfigError(f"missing key '{path}.{key}'")
    return table[key]


def _num(table: Table, key: str, path: str, *, minimum: float = 0) -> Any:
    value = _get(table, key, path)
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ConfigError(f"'{path}.{key}' must be a number, got {value!r}")
    if value < minimum:
        raise ConfigError(f"'{path}.{key}' must be >= {minimum}, got {value}")
    return value


def _range(table: Table, key: str, path: str) -> tuple[int, int]:
    value = _get(table, key, path)
    if not (isinstance(value, list) and len(value) == 2 and value[0] <= value[1]):
        raise ConfigError(f"'{path}.{key}' must be [low, high], got {value!r}")
    return (int(value[0]), int(value[1]))


def _per_weather(table: Table, path: str, *, default: float | None = None) -> dict[Weather, Any]:
    out: dict[Weather, Any] = {}
    for w in Weather:
        if w.value in table:
            out[w] = table[w.value]
        elif default is not None:
            out[w] = default
        else:
            raise ConfigError(f"missing key '{path}.{w.value}'")
    return out


def _params(table: Table, reserved: set[str]) -> dict[str, float]:
    return {k: float(v) for k, v in table.items() if k not in reserved}


def _parse_game(t: Table) -> GameConfig:
    limits = _get(t, "recipe_limits", "game")
    price = _range(t, "price_limits", "game")
    return GameConfig(
        starting_cash=_num(t, "starting_cash", "game"),
        starting_reputation=_num(t, "starting_reputation", "game"),
        cups_per_pitcher=_num(t, "cups_per_pitcher", "game", minimum=1),
        recipe_limits=RecipeLimits(
            lemons=_range(limits, "lemons", "game.recipe_limits"),
            sugar=_range(limits, "sugar", "game.recipe_limits"),
            ice=_range(limits, "ice", "game.recipe_limits"),
        ),
        price_limits=price,
    )


def _parse_item(t: Table, path: str) -> ItemConfig:
    tiers = tuple(
        BulkTier(
            min_packs=_num(tier, "min_packs", path, minimum=1),
            discount_pct=_num(tier, "discount_pct", path),
        )
        for tier in t.get("tiers", [])
    )
    shelf = t.get("shelf_life_days")
    return ItemConfig(
        pack_size=_num(t, "pack_size", path, minimum=1),
        pack_price=_num(t, "pack_price", path),
        tiers=tuple(sorted(tiers, key=lambda b: b.min_packs)),
        shelf_life_days=None if shelf is None else int(shelf),
        melts=bool(t.get("melts", False)),
    )


def _parse_items(t: Table) -> dict[Item, ItemConfig]:
    tables = _get(t, "items", "items")
    unknown = set(tables) - {i.value for i in Item}
    if unknown:
        raise ConfigError(f"unknown items: {sorted(unknown)}")
    return {i: _parse_item(_get(tables, i.value, "items"), f"items.{i.value}") for i in Item}


def _field_names(cls: type) -> list[str]:
    return [f.name for f in fields(cls)]


def _parse_demand(t: Table) -> DemandConfig:
    d = _get(t, "demand", "items")
    return DemandConfig(**{name: _num(d, name, "demand") for name in _field_names(DemandConfig)})


def _flag(table: Table, key: str, path: str) -> bool:
    value = _get(table, key, path)
    if not isinstance(value, bool):
        raise ConfigError(f"'{path}.{key}' must be true or false, got {value!r}")
    return value


def _parse_market(t: Table) -> MarketConfig:
    m = _get(t, "market", "items")
    item = _get(m, "shortage_item", "market")
    if item not in {i.value for i in Item}:
        raise ConfigError(f"'market.shortage_item' must be an item, got {item!r}")
    return MarketConfig(
        fluctuation=_flag(m, "fluctuation", "market"),
        fluctuation_pct=int(_num(m, "fluctuation_pct", "market")),
        shortages=_flag(m, "shortages", "market"),
        shortage_chance=_num(m, "shortage_chance", "market"),
        shortage_item=Item(item),
        shortage_markup_pct=int(_num(m, "shortage_markup_pct", "market")),
    )


def _parse_calendar(t: Table) -> CalendarConfig:
    c = _get(t, "calendar", "game")
    names = tuple(str(n) for n in _get(c, "day_names", "calendar"))
    if not names:
        raise ConfigError("'calendar.day_names' must not be empty")
    weekend = frozenset(int(d) for d in _get(c, "weekend_days", "calendar"))
    if not weekend <= set(range(len(names))):
        raise ConfigError(f"'calendar.weekend_days' must index day_names, got {sorted(weekend)}")
    holidays: dict[int, HolidayConfig] = {}
    for h in c.get("holidays", []):
        day = int(_num(h, "day", "calendar.holidays", minimum=1))
        if day in holidays:
            raise ConfigError(f"two holidays on day {day}")
        holidays[day] = HolidayConfig(
            name=str(_get(h, "name", "calendar.holidays")),
            traffic_mul=_num(h, "traffic_mul", "calendar.holidays"),
        )
    return CalendarConfig(
        day_names=names,
        weekend_days=weekend,
        weekend_traffic_mul=_num(c, "weekend_traffic_mul", "calendar"),
        holidays=holidays,
    )


def _parse_difficulties(t: Table, starting_cash: Cents) -> dict[str, DifficultyConfig]:
    tables = _get(t, "difficulty", "game")
    if "normal" not in tables:
        raise ConfigError("missing key 'difficulty.normal'")
    return {
        diff_id: DifficultyConfig(
            name=str(_get(d, "name", f"difficulty.{diff_id}")),
            description=str(d.get("description", "")),
            starting_cash=int(_num(d, "starting_cash", f"difficulty.{diff_id}"))
            if "starting_cash" in d
            else starting_cash,
            traffic_mul=_num(d, "traffic_mul", f"difficulty.{diff_id}"),
            supply_price_pct=int(_num(d, "supply_price_pct", f"difficulty.{diff_id}", minimum=1)),
        )
        for diff_id, d in tables.items()
    }


def _parse_weather(t: Table) -> WeatherConfig:
    w = _get(t, "weather", "game")
    ranges = _get(w, "temp_range", "weather")
    return WeatherConfig(
        accuracy=_num(w, "accuracy", "weather"),
        temp_noise=_num(w, "temp_noise", "weather"),
        forecast_weights=_per_weather(_get(w, "forecast_weights", "weather"), "weather.weights"),
        temp_range={x: _range(ranges, x.value, "weather.temp_range") for x in Weather},
        traffic=_per_weather(_get(w, "traffic", "weather"), "weather.traffic"),
        price_tolerance=_per_weather(w.get("price_tolerance", {}), "", default=1.0),
    )


def _parse_locations(t: Table) -> dict[str, LocationConfig]:
    return {
        loc_id: LocationConfig(
            name=_get(loc, "name", loc_id),
            base_traffic=_num(loc, "base_traffic", loc_id),
            rent=_num(loc, "rent", loc_id),
            description=loc.get("description", ""),
        )
        for loc_id, loc in t.items()
    }


def _parse_upgrades(t: Table) -> dict[str, UpgradeConfig]:
    return {
        up_id: UpgradeConfig(
            name=_get(up, "name", up_id),
            cost=_num(up, "cost", up_id),
            description=up.get("description", ""),
            params=_params(up, {"name", "cost", "description"}),
        )
        for up_id, up in t.items()
    }


def _parse_events(t: Table) -> dict[str, EventConfig]:
    return {
        ev_id: EventConfig(
            name=_get(ev, "name", ev_id),
            base_chance=_num(ev, "base_chance", ev_id),
            params=_params(ev, {"name", "base_chance"}),
        )
        for ev_id, ev in t.items()
    }


def parse_config(raw: Mapping[str, Table]) -> Config:
    """Build a `Config` from parsed TOML tables keyed by file stem (game, items, ...).

    Raises `ConfigError` on any missing key or invalid value.
    """
    for name in CONTENT_FILES:
        if name not in raw:
            raise ConfigError(f"missing content file '{name}.toml'")
    game = _parse_game(_get(raw["game"], "game", "game"))
    return Config(
        game=game,
        items=_parse_items(raw["items"]),
        demand=_parse_demand(raw["items"]),
        weather=_parse_weather(raw["game"]),
        locations=_parse_locations(raw["locations"]),
        upgrades=_parse_upgrades(raw["upgrades"]),
        events=_parse_events(raw["events"]),
        market=_parse_market(raw["items"]),
        calendar=_parse_calendar(raw["game"]),
        difficulties=_parse_difficulties(raw["game"], game.starting_cash),
    )


def read_raw_content(content_dir: Path | None = None) -> dict[str, dict[str, Any]]:
    """Read every content TOML into plain dicts (the one sanctioned file read)."""
    base = content_dir or resources.files("lemonade") / "content"
    raw: dict[str, dict[str, Any]] = {}
    for name in CONTENT_FILES:
        raw[name] = tomllib.loads((base / f"{name}.toml").read_text(encoding="utf-8"))
    return raw


def load_config(content_dir: Path | None = None) -> Config:
    """Load and validate the game content. Defaults to the packaged `lemonade/content`."""
    return parse_config(read_raw_content(content_dir))
