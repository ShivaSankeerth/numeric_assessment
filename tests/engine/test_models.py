import dataclasses

import pytest

from factories import make_inventory, make_state
from lemonade.engine.models import Batch, Inventory, Recipe
from lemonade.engine.types import Item


def test_models_are_frozen() -> None:
    state = make_state()
    with pytest.raises(dataclasses.FrozenInstanceError):
        state.cash = 0  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        Recipe().ice_per_cup = 9  # type: ignore[misc]


def test_empty_inventory_counts_zero() -> None:
    inv = Inventory.empty()
    assert all(inv.count(item) == 0 for item in Item)


def test_count_sums_batches() -> None:
    inv = Inventory(batches={Item.LEMON: (Batch(5, 3), Batch(7, None))})
    assert inv.count(Item.LEMON) == 12
    assert inv.count(Item.CUP) == 0


def test_make_inventory_factory() -> None:
    inv = make_inventory(expires_on_day=4, lemon=12, cup=50)
    assert inv.count(Item.LEMON) == 12
    assert inv.batches[Item.LEMON][0].expires_on_day == 4
    assert inv.batches[Item.CUP][0].expires_on_day is None


def test_recipe_defaults() -> None:
    assert Recipe() == Recipe(lemons_per_pitcher=6, sugar_per_pitcher=4, ice_per_cup=3)
