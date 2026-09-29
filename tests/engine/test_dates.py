import pytest

from lemonade.engine import dates
from lemonade.engine.config import Config


@pytest.mark.parametrize(
    ("day", "name", "weekend"),
    [
        (1, "Monday", False),
        (5, "Friday", False),
        (6, "Saturday", True),
        (7, "Sunday", True),
        (8, "Monday", False),
        (13, "Saturday", True),
    ],
)
def test_day_names_and_weekends(cfg: Config, day: int, name: str, weekend: bool) -> None:
    assert dates.day_name(day, cfg) == name
    assert dates.is_weekend(day, cfg) is weekend
    assert dates.day_of_week(day, cfg) == (day - 1) % 7


def test_holidays_from_content(cfg: Config) -> None:
    assert dates.holiday_name(4, cfg) == "Independence Day"
    holiday = dates.holiday_on(12, cfg)
    assert holiday is not None and holiday.traffic_mul > 1
    assert dates.holiday_on(2, cfg) is None
    assert dates.holiday_name(2, cfg) is None
