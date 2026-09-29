import pytest

from factories import make_inventory
from lemonade.engine.inventory import add, consume, cups_makeable, melt, spoil
from lemonade.engine.models import Batch, Inventory, Recipe
from lemonade.engine.types import Item


def lemons(*batches: tuple[int, int | None]) -> Inventory:
    return Inventory(batches={Item.LEMON: tuple(Batch(q, e) for q, e in batches)})


def test_add_keeps_batches_sorted_and_merges_same_expiry() -> None:
    inv = add(Inventory.empty(), Item.LEMON, 12, 7)
    inv = add(inv, Item.LEMON, 12, 5)
    inv = add(inv, Item.LEMON, 3, None)
    inv = add(inv, Item.LEMON, 12, 5)
    assert inv.batches[Item.LEMON] == (Batch(24, 5), Batch(12, 7), Batch(3, None))
    assert inv.count(Item.LEMON) == 39


def test_add_rejects_negative_and_ignores_zero() -> None:
    inv = Inventory.empty()
    assert add(inv, Item.CUP, 0, None) is inv
    with pytest.raises(ValueError):
        add(inv, Item.CUP, -1, None)


def test_consume_is_fifo_by_expiry_and_splits_batches() -> None:
    inv = lemons((5, 3), (10, 6), (4, None))
    inv = consume(inv, Item.LEMON, 8)
    # the 5 expiring on day 3 are gone, 3 taken from the day-6 batch, never-expiring untouched
    assert inv.batches[Item.LEMON] == (Batch(7, 6), Batch(4, None))


def test_consume_exact_amount_empties_item() -> None:
    inv = consume(make_inventory(cup=50), Item.CUP, 50)
    assert inv.count(Item.CUP) == 0
    assert inv.batches[Item.CUP] == ()


def test_consume_more_than_available_raises() -> None:
    with pytest.raises(ValueError, match="need 13"):
        consume(make_inventory(lemon=12), Item.LEMON, 13)


@pytest.mark.parametrize(("ice", "retention", "kept"), [(100, 0.0, 0), (101, 0.5, 50), (0, 0.5, 0)])
def test_melt(ice: int, retention: float, kept: int) -> None:
    inv, melted = melt(make_inventory(ice=ice, cup=10), retention)
    assert inv.count(Item.ICE) == kept
    assert melted == ice - kept
    assert inv.count(Item.CUP) == 10  # other items untouched


def test_spoil_removes_only_expired_batches() -> None:
    inv = lemons((5, 3), (10, 4), (2, None))
    inv, spoiled = spoil(inv, day=3)
    assert spoiled == {Item.LEMON: 5}
    assert inv.batches[Item.LEMON] == (Batch(10, 4), Batch(2, None))
    _, spoiled_none = spoil(inv, day=3)
    assert spoiled_none == {}


def test_spoilage_uses_fifo() -> None:
    """Using lemons eats the oldest batch first, so the fresher batch survives spoilage."""
    inv = lemons((12, 3), (12, 8))
    inv = consume(inv, Item.LEMON, 12)
    inv, spoiled = spoil(inv, day=3)
    assert spoiled == {}
    assert inv.count(Item.LEMON) == 12


@pytest.mark.parametrize(
    ("counts", "recipe", "expected"),
    [
        ({"lemon": 12, "sugar": 8, "ice": 300, "cup": 50}, Recipe(6, 4, 3), 24),  # lemons/sugar
        ({"lemon": 5, "sugar": 8, "ice": 300, "cup": 50}, Recipe(6, 4, 3), 0),  # < 1 pitcher
        ({"lemon": 60, "sugar": 40, "ice": 30, "cup": 50}, Recipe(6, 4, 3), 10),  # ice-limited
        ({"lemon": 60, "sugar": 40, "ice": 300, "cup": 7}, Recipe(6, 4, 3), 7),  # cup-limited
        ({"lemon": 60, "sugar": 4, "ice": 300, "cup": 50}, Recipe(6, 4, 3), 12),  # sugar-limited
        ({"lemon": 1, "cup": 50}, Recipe(1, 0, 0), 12),  # no sugar, no ice needed
    ],
)
def test_cups_makeable(counts: dict[str, int], recipe: Recipe, expected: int) -> None:
    assert cups_makeable(make_inventory(**counts), recipe, 12) == expected
