import pytest

from factories import make_ctx, make_plan, make_state
from lemonade.engine.config import Config
from lemonade.engine.errors import ConfigError
from lemonade.engine.game import new_game
from lemonade.engine.market import market_notes, plan_cost, todays_pack_prices
from lemonade.engine.registry import MODIFIERS
from lemonade.engine.types import Factor, Item

difficulty = MODIFIERS["difficulty"]


def test_levels_in_content(cfg: Config) -> None:
    assert set(cfg.difficulties) == {"easy", "normal", "hard"}
    normal = cfg.difficulties["normal"]
    assert (normal.starting_cash, normal.traffic_mul, normal.supply_price_pct) == (2000, 1.0, 100)


@pytest.mark.parametrize(("level", "cash"), [("easy", 3000), ("normal", 2000), ("hard", 1500)])
def test_new_game_uses_difficulty_starting_cash(cfg: Config, level: str, cash: int) -> None:
    state = new_game(1, cfg, level)
    assert state.cash == cash
    assert state.difficulty == level


def test_unknown_difficulty_rejected(cfg: Config) -> None:
    with pytest.raises(ConfigError, match="Unknown difficulty 'nightmare'"):
        new_game(1, cfg, "nightmare")


def test_traffic_effect_with_reason() -> None:
    (effect,) = difficulty.effects(make_ctx(state=make_state(difficulty="hard")))
    assert (effect.factor, effect.op, effect.value) == (Factor.TRAFFIC, "mul", 0.85)
    assert effect.reason == "Hard difficulty: -15% foot traffic"
    assert difficulty.effects(make_ctx(state=make_state(difficulty="normal"))) == []


def test_supplier_prices_scale_with_difficulty(cfg: Config) -> None:
    hard = todays_pack_prices(make_state(difficulty="hard"), cfg)
    easy = todays_pack_prices(make_state(difficulty="easy"), cfg)
    assert hard[Item.LEMON] == 460 and easy[Item.LEMON] == 360
    assert hard[Item.ICE] == 173  # 172.5 rounds half up
    plan = make_plan({"lemon": 1})
    assert plan_cost(make_state(difficulty="hard"), plan, cfg) == 460
    assert market_notes(make_state(difficulty="hard"), cfg) == (
        "Hard difficulty: all supplies +15%",
    )
    assert market_notes(make_state(), cfg) == ()
