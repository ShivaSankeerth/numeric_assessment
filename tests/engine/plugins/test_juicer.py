import pytest

from factories import make_ctx, make_inventory, make_plan, make_state
from lemonade.engine.config import Config
from lemonade.engine.game import preview_plan
from lemonade.engine.models import Recipe
from lemonade.engine.recipes import effective_recipe, lemon_yield_bonus
from lemonade.engine.registry import UPGRADE_HANDLERS
from lemonade.engine.simulation import simulate_day
from lemonade.engine.types import Item

JUICED = frozenset({"juicer"})


def test_juicer_handler(cfg: Config) -> None:
    juicer = UPGRADE_HANDLERS["juicer"]
    assert juicer.lemon_yield_bonus(cfg) == 0.25
    assert juicer.effects(make_ctx()) == []
    assert lemon_yield_bonus(make_state(upgrades=JUICED), cfg) == 0.25


@pytest.mark.parametrize(("lemons", "expected"), [(1, 1), (2, 2), (4, 4), (5, 4), (6, 5), (12, 10)])
def test_effective_recipe_needs_fewer_lemons(cfg: Config, lemons: int, expected: int) -> None:
    recipe = Recipe(lemons, 4, 3)
    got = effective_recipe(make_state(upgrades=JUICED), recipe, cfg)
    assert got == Recipe(expected, 4, 3)


def test_without_juicer_recipe_is_unchanged(cfg: Config) -> None:
    recipe = Recipe(6, 4, 3)
    assert effective_recipe(make_state(upgrades=frozenset({"cooler"})), recipe, cfg) is recipe


def test_preview_counts_juicer_bought_today(cfg: Config) -> None:
    buy = {"lemon": 1, "sugar": 2, "ice": 2, "cup": 1}
    state = make_state(cash=5000)
    plain = preview_plan(state, make_plan(buy), cfg)
    juiced = preview_plan(state, make_plan(buy, upgrade_purchases=("juicer",)), cfg)
    assert plain.cups_makeable == 24  # 12 lemons / 6 = 2 pitchers
    assert juiced.cups_makeable == 24  # 12 lemons / 5 = still 2 pitchers
    more = make_state(cash=5000, inventory=make_inventory(ice=1000, cup=200, sugar=100))
    assert preview_plan(more, make_plan({"lemon": 3}), cfg).cups_makeable == 72  # 6 pitchers
    juiced_more = make_plan({"lemon": 3}, upgrade_purchases=("juicer",))
    assert preview_plan(more, juiced_more, cfg).cups_makeable == 84  # 36 / 5 = 7 pitchers


def test_simulated_day_consumes_juiced_amount(cfg: Config) -> None:
    stock = make_inventory(lemon=5, sugar=40, ice=600, cup=200)
    state = make_state(inventory=stock, upgrades=JUICED)
    _, result = simulate_day(state, make_plan(price_per_cup=10), cfg)
    assert result.cups_sold == 12  # one pitcher from only 5 lemons
    assert result.consumed[Item.LEMON] == 5
