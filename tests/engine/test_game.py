import pytest

from factories import make_inventory, make_plan, make_state
from lemonade.engine.config import Config
from lemonade.engine.errors import GameOverError
from lemonade.engine.game import end_day, is_bankrupt, new_game, play_day, preview_plan
from lemonade.engine.models import Inventory, Recipe
from lemonade.engine.types import GameStatus


def test_new_game_defaults(cfg: Config) -> None:
    state = new_game(42, cfg)
    assert (state.day, state.cash, state.reputation) == (1, 2000, 0.3)
    assert state.inventory == Inventory.empty()
    assert state.status is GameStatus.PLAYING
    assert new_game(42, cfg).forecast == state.forecast


def test_bankrupt_when_cash_zero_and_cannot_make_a_cup(cfg: Config) -> None:
    assert is_bankrupt(make_state(cash=0), cfg)


def test_not_bankrupt_when_cash_zero_but_can_make_cups(cfg: Config) -> None:
    assert not is_bankrupt(make_state(cash=0, inventory=make_inventory(lemon=1, cup=1)), cfg)


def test_bankrupt_when_cash_below_missing_packs(cfg: Config) -> None:
    state = make_state(cash=300, inventory=make_inventory(cup=50))  # a lemon pack costs 400
    assert is_bankrupt(state, cfg)
    assert not is_bankrupt(make_state(cash=400, inventory=make_inventory(cup=50)), cfg)


def test_end_day_sets_status(cfg: Config) -> None:
    assert end_day(make_state(cash=0), cfg).status is GameStatus.BANKRUPT
    assert end_day(make_state(), cfg).status is GameStatus.PLAYING


def test_play_day_goes_bankrupt_and_then_refuses(cfg: Config) -> None:
    state, _ = play_day(make_state(cash=0), make_plan(), cfg)
    assert state.status is GameStatus.BANKRUPT
    with pytest.raises(GameOverError):
        play_day(state, make_plan(), cfg)


def test_preview_plan(cfg: Config) -> None:
    plan = make_plan({"lemon": 1, "sugar": 1, "ice": 1, "cup": 1}, recipe=Recipe(6, 4, 3))
    preview = preview_plan(make_state(), plan, cfg)
    assert preview.cost == 1100
    assert preview.cash_after == 900
    assert preview.cups_makeable == 24  # 12 lemons = 2 pitchers
    assert preview_plan(make_state(), make_plan({"lemon": 0}), cfg).cups_makeable == 0
