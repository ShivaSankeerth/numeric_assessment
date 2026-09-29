"""Calendar helpers: day of week, weekends and holidays (all from `[calendar]` in game.toml)."""

from __future__ import annotations

from lemonade.engine.config import Config, HolidayConfig


def day_of_week(day: int, cfg: Config) -> int:
    """0-based weekday index into `cfg.calendar.day_names`; day 1 is index 0."""
    return (day - 1) % len(cfg.calendar.day_names)


def day_name(day: int, cfg: Config) -> str:
    """Weekday name for a game day, e.g. day 6 -> "Saturday"."""
    return cfg.calendar.day_names[day_of_week(day, cfg)]


def is_weekend(day: int, cfg: Config) -> bool:
    """True if the game day falls on a configured weekend day."""
    return day_of_week(day, cfg) in cfg.calendar.weekend_days


def holiday_on(day: int, cfg: Config) -> HolidayConfig | None:
    """The holiday on this game day, if any."""
    return cfg.calendar.holidays.get(day)


def holiday_name(day: int, cfg: Config) -> str | None:
    """Name of the holiday on this game day (what `DayContext.holiday` holds), if any."""
    holiday = holiday_on(day, cfg)
    return holiday.name if holiday else None
