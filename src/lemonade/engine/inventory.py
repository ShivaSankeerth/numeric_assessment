"""Pure inventory transitions: add, consume (FIFO), melt, spoil, and cups makeable.

Invariant: each item's batches are kept sorted by expiry (soonest first, never-expiring last)
with at most one batch per expiry day, so FIFO consumption is simply "take from the front".
"""

from __future__ import annotations

import math
from dataclasses import replace

from lemonade.engine.models import Batch, Inventory, Recipe
from lemonade.engine.types import Item


def _expiry_key(batch: Batch) -> tuple[bool, int]:
    return (batch.expires_on_day is None, batch.expires_on_day or 0)


def _with_batches(inv: Inventory, item: Item, batches: tuple[Batch, ...]) -> Inventory:
    return replace(inv, batches={**inv.batches, item: batches})


def add(inv: Inventory, item: Item, qty: int, expires_on_day: int | None) -> Inventory:
    """Add `qty` units usable through `expires_on_day` (None = never).

    Batches with the same expiry are merged.
    """
    if qty < 0:
        raise ValueError(f"cannot add negative quantity {qty} of {item}")
    if qty == 0:
        return inv
    batches = list(inv.batches.get(item, ()))
    for i, b in enumerate(batches):
        if b.expires_on_day == expires_on_day:
            batches[i] = Batch(b.qty + qty, expires_on_day)
            break
    else:
        batches.append(Batch(qty, expires_on_day))
    return _with_batches(inv, item, tuple(sorted(batches, key=_expiry_key)))


def consume(inv: Inventory, item: Item, qty: int) -> Inventory:
    """Remove `qty` units, oldest expiry first. Raises ValueError if there is not enough."""
    if qty < 0:
        raise ValueError(f"cannot consume negative quantity {qty} of {item}")
    if qty > inv.count(item):
        raise ValueError(f"need {qty} {item}, have {inv.count(item)}")
    remaining = qty
    kept: list[Batch] = []
    for b in inv.batches.get(item, ()):
        take = min(b.qty, remaining)
        remaining -= take
        if b.qty > take:
            kept.append(Batch(b.qty - take, b.expires_on_day))
    return _with_batches(inv, item, tuple(kept))


def melt(inv: Inventory, retention: float) -> tuple[Inventory, int]:
    """Melt ice at end of day, keeping floor(ice * retention). Returns (inventory, cubes melted)."""
    ice = inv.count(Item.ICE)
    kept = math.floor(ice * max(0.0, min(1.0, retention)))
    new_batches = (Batch(kept, None),) if kept else ()
    return _with_batches(inv, Item.ICE, new_batches), ice - kept


def spoil(inv: Inventory, day: int) -> tuple[Inventory, dict[Item, int]]:
    """Drop batches whose last usable day is `day` or earlier. Returns (inventory, spoiled)."""
    spoiled: dict[Item, int] = {}
    batches = dict(inv.batches)
    for item, item_batches in inv.batches.items():
        fresh = tuple(b for b in item_batches if b.expires_on_day is None or b.expires_on_day > day)
        lost = sum(b.qty for b in item_batches) - sum(b.qty for b in fresh)
        if lost:
            spoiled[item] = lost
            batches[item] = fresh
    return replace(inv, batches=batches), spoiled


def cups_makeable(inv: Inventory, recipe: Recipe, cups_per_pitcher: int) -> int:
    """How many cups this inventory can serve with `recipe` (pitchers made whole, on demand)."""
    pitcher_limits = [
        inv.count(Item.LEMON) // recipe.lemons_per_pitcher if recipe.lemons_per_pitcher else None,
        inv.count(Item.SUGAR) // recipe.sugar_per_pitcher if recipe.sugar_per_pitcher else None,
    ]
    limits = [inv.count(Item.CUP)]
    known = [p for p in pitcher_limits if p is not None]
    if known:
        limits.append(min(known) * cups_per_pitcher)
    if recipe.ice_per_cup:
        limits.append(inv.count(Item.ICE) // recipe.ice_per_cup)
    return min(limits)
