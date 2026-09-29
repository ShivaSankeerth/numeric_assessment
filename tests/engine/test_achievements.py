import copy
from dataclasses import replace

import pytest

from factories import achievements_cfg, make_inventory, make_plan, make_state
from lemonade.engine.achievements import is_met, newly_unlocked, unlock
from lemonade.engine.config import Config, parse_config, read_raw_content
from lemonade.engine.errors import ConfigError
from lemonade.engine.game import end_day, play_day
from lemonade.engine.models import DayResult, Recipe
from lemonade.engine.simulation import simulate_day
from lemonade.engine.types import AchievementKind, GameStatus


@pytest.fixture
def cfg() -> Config:
    return achievements_cfg()


STOCK = {"lemon": 60, "sugar": 40, "ice": 600, "cup": 200}


def _day(cfg: Config, cups: int, taste: float = 0.5) -> DayResult:
    _, result = simulate_day(make_state(), make_plan(), cfg)
    return replace(result, cups_sold=cups, taste_score=taste)


def test_content_parsed_into_typed_config(cfg: Config) -> None:
    assert next(iter(cfg.achievements)) == "first_sale"
    kinds = {a.kind for a in cfg.achievements.values()}
    assert kinds == set(AchievementKind)
    assert cfg.achievements["pocket_money"].threshold == 5000


def test_each_kind(cfg: Config) -> None:
    a = cfg.achievements
    assert is_met(a["pocket_money"], make_state(cash=5000))
    assert not is_met(a["pocket_money"], make_state(cash=4999))
    week = make_state(history=tuple(_day(cfg, 0) for _ in range(7)))
    assert is_met(a["one_week"], week)
    assert not is_met(a["one_week"], replace(week, status=GameStatus.BANKRUPT))
    assert not is_met(a["one_week"], replace(week, history=week.history[:6]))
    sold = make_state(history=(_day(cfg, 60), _day(cfg, 40)))
    assert is_met(a["hundred_cups"], sold) and not is_met(a["thousand_cups"], sold)
    assert is_met(a["perfect_recipe"], make_state(history=(_day(cfg, 5, taste=1.0),)))
    assert not is_met(a["perfect_recipe"], make_state(history=(_day(cfg, 0, taste=1.0),)))
    assert not is_met(a["perfect_recipe"], make_state())


def test_unlock_records_on_state_and_last_result(cfg: Config) -> None:
    state = make_state(history=(_day(cfg, 0), _day(cfg, 3)))
    assert newly_unlocked(state, cfg) == ("first_sale",)
    after = unlock(state, cfg)
    assert after.achievements == {"first_sale"}
    assert after.history[-1].achievements_unlocked == ("first_sale",)
    assert after.history[0].achievements_unlocked == ()
    assert unlock(after, cfg) == after  # nothing new, nothing re-added


def test_achievements_are_never_removed(cfg: Config) -> None:
    state = make_state(cash=0, achievements=frozenset({"tycoon"}))
    assert "tycoon" in end_day(state, cfg).achievements


def test_play_day_reports_unlocks_in_the_result(cfg: Config) -> None:
    state = make_state(inventory=make_inventory(**STOCK))
    after, result = play_day(state, make_plan(price_per_cup=10, recipe=Recipe(6, 4, 3)), cfg)
    assert result.cups_sold > 0
    assert "first_sale" in result.achievements_unlocked
    assert after.history[-1] == result
    assert "first_sale" in after.achievements
    _, again = play_day(after, make_plan(price_per_cup=10), cfg)
    assert "first_sale" not in again.achievements_unlocked


def test_unknown_kind_is_a_config_error() -> None:
    raw = copy.deepcopy(read_raw_content())
    raw["achievements"]["first_sale"]["kind"] = "be_nice"
    with pytest.raises(ConfigError, match="kind"):
        parse_config(raw)
