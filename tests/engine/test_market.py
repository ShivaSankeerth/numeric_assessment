from dataclasses import replace

import pytest

from factories import make_inventory, make_plan, make_state, market_cfg
from lemonade.engine.config import Config, load_config
from lemonade.engine.errors import InsufficientFunds, InvalidPlan
from lemonade.engine.market import (
    apply_purchases,
    cost_to_make_one_cup,
    discount_pct,
    market_day,
    market_notes,
    plan_cost,
    purchase_cost,
    todays_pack_prices,
    validate_plan,
)
from lemonade.engine.models import Purchase, Recipe
from lemonade.engine.types import Item


@pytest.mark.parametrize(("packs", "pct"), [(1, 0), (2, 0), (3, 10), (5, 10), (6, 20), (20, 20)])
def test_lemon_bulk_tiers(cfg: Config, packs: int, pct: int) -> None:
    assert discount_pct(Item.LEMON, packs, cfg) == pct


def test_items_without_tiers_never_discount(cfg: Config) -> None:
    assert discount_pct(Item.ICE, 50, cfg) == 0


def test_purchase_cost_applies_discount_with_integer_rounding(cfg: Config) -> None:
    assert purchase_cost(Item.LEMON, 2, 400, cfg) == 800
    assert purchase_cost(Item.LEMON, 3, 400, cfg) == 1080  # 1200 - 10%
    assert purchase_cost(Item.LEMON, 6, 400, cfg) == 1920  # 2400 - 20%
    assert purchase_cost(Item.LEMON, 3, 333, cfg) == 899  # 899.1 -> 899
    assert purchase_cost(Item.LEMON, 3, 335, cfg) == 905  # 904.5 -> 905 (half up)


def test_todays_prices_are_base_prices(cfg: Config) -> None:
    prices = todays_pack_prices(make_state(), cfg)
    assert prices == {Item.LEMON: 400, Item.SUGAR: 300, Item.ICE: 150, Item.CUP: 250}


def test_plan_cost_sums_supplies_upgrades_and_rent(cfg: Config) -> None:
    plan = make_plan({"lemon": 1, "sugar": 1, "ice": 1, "cup": 1}, upgrade_purchases=("cooler",))
    assert plan_cost(make_state(), plan, cfg) == 400 + 300 + 150 + 250 + 1500


def test_valid_plan_passes(cfg: Config) -> None:
    validate_plan(make_state(), make_plan({"lemon": 1, "cup": 1}), cfg)


@pytest.mark.parametrize(
    ("plan_kwargs", "match"),
    [
        ({"purchases": (Purchase(Item.LEMON, 0),)}, "at least 1 pack"),
        ({"purchases": (Purchase(Item.CUP, 1), Purchase(Item.CUP, 2))}, "duplicated"),
        ({"location_id": "moon"}, "Unknown location"),
        ({"recipe": Recipe(0, 4, 3)}, "Lemons"),
        ({"recipe": Recipe(6, 13, 3)}, "Sugar"),
        ({"recipe": Recipe(6, 4, 11)}, "Ice"),
        ({"price_per_cup": 1}, "Price"),
        ({"price_per_cup": 5000}, "Price"),
        ({"upgrade_purchases": ("jetpack",)}, "Unknown upgrade"),
        ({"upgrade_purchases": ("cooler", "cooler")}, "only be bought once"),
    ],
)
def test_invalid_plans_rejected(cfg: Config, plan_kwargs: dict, match: str) -> None:
    with pytest.raises(InvalidPlan, match=match):
        validate_plan(make_state(cash=10_000), make_plan(**plan_kwargs), cfg)


def test_owned_upgrade_rejected(cfg: Config) -> None:
    state = make_state(upgrades=frozenset({"cooler"}))
    with pytest.raises(InvalidPlan, match="already own"):
        validate_plan(state, make_plan(upgrade_purchases=("cooler",)), cfg)


def test_overspending_raises_insufficient_funds(cfg: Config) -> None:
    with pytest.raises(InsufficientFunds, match=r"costs \$21\.70 but you only have \$20\.00"):
        validate_plan(make_state(), make_plan({"lemon": 6, "cup": 1}), cfg)  # 1920 + 250


def test_apply_purchases_charges_and_stocks(cfg: Config) -> None:
    state = make_state(day=3, cash=5000)
    plan = make_plan({"lemon": 3, "cup": 1}, upgrade_purchases=("cooler",))
    new_state, purchased = apply_purchases(state, plan, cfg)
    assert new_state.cash == 5000 - 1080 - 250 - 1500
    assert purchased == {Item.LEMON: 36, Item.SUGAR: 0, Item.ICE: 0, Item.CUP: 50}
    assert new_state.inventory.batches[Item.LEMON][0].expires_on_day == 3 + 5 - 1
    assert new_state.inventory.batches[Item.CUP][0].expires_on_day is None
    assert "cooler" in new_state.upgrades
    assert state.inventory.count(Item.LEMON) == 0  # input state untouched


def test_cost_to_make_one_cup_is_zero_when_a_cup_is_possible(cfg: Config) -> None:
    state = make_state(cash=0, inventory=make_inventory(lemon=1, cup=1))
    assert cost_to_make_one_cup(state, cfg) == 0


@pytest.mark.parametrize(
    ("counts", "expected"),
    [({}, 400 + 250), ({"lemon": 3}, 250), ({"cup": 50, "sugar": 8, "ice": 100}, 400)],
)
def test_cost_to_make_one_cup_sums_missing_packs(
    cfg: Config, counts: dict[str, int], expected: int
) -> None:
    state = replace(make_state(), inventory=make_inventory(**counts))
    assert cost_to_make_one_cup(state, cfg) == expected


def test_market_notes_empty_without_fluctuation(cfg: Config) -> None:
    assert market_notes(make_state(), cfg) == ()


def test_test_config_has_fixed_prices_but_real_game_fluctuates(cfg: Config) -> None:
    assert not cfg.market.fluctuation and not cfg.market.shortages
    real = load_config()
    assert real.market.fluctuation and real.market.shortages
    assert real.market.fluctuation_pct == 15
    assert market_notes(make_state(), cfg) == ()


def test_fluctuation_stays_within_bounds_and_is_deterministic() -> None:
    cfg = market_cfg(fluctuation=True)
    moved = []
    for day in range(1, 40):
        state = make_state(day=day)
        prices = todays_pack_prices(state, cfg)
        assert prices == todays_pack_prices(state, cfg)
        for item, price in prices.items():
            base = cfg.items[item].pack_price
            assert base * 0.85 - 1 <= price <= base * 1.15 + 1
            moved.append(price != base)
    assert any(moved)


def test_fluctuation_notes_match_prices() -> None:
    cfg = market_cfg(fluctuation=True)
    state = make_state(day=3)
    today = market_day(state, cfg)
    assert any(today.change_pct.values())
    notes = market_notes(state, cfg)
    for item, pct in today.change_pct.items():
        assert (f"Supplier prices: {item.value} {pct:+d}%" in notes) == (pct != 0)
    sugar = cfg.items[Item.SUGAR].pack_price
    expected = (sugar * (100 + today.change_pct[Item.SUGAR]) + 50) // 100
    assert todays_pack_prices(state, cfg)[Item.SUGAR] == expected


def test_shortage_marks_lemons_up_50_percent_with_note() -> None:
    cfg = market_cfg(shortages=True, shortage_chance=1.0)
    prices = todays_pack_prices(make_state(), cfg)
    assert prices[Item.LEMON] == 600
    assert prices[Item.SUGAR] == 300
    assert market_notes(make_state(), cfg) == ("Lemon shortage: lemons +50% today",)


def test_shortage_is_rare_and_seeded() -> None:
    cfg = market_cfg(shortages=True)
    hits = [market_day(make_state(day=d), cfg).shortage for d in range(1, 201)]
    assert 0 < hits.count(Item.LEMON) < 40
    assert set(hits) <= {None, Item.LEMON}


def test_plan_cost_and_bankruptcy_use_todays_prices() -> None:
    cfg = market_cfg(shortages=True, shortage_chance=1.0)
    assert plan_cost(make_state(), make_plan({"lemon": 1}), cfg) == 600
    assert cost_to_make_one_cup(make_state(inventory=make_inventory(cup=1)), cfg) == 600
