"""The per-customer sell loop (pipeline step 8).

Per-customer is intentional: it naturally models selling out mid-day and gives loss-reason stats.
Pitchers are made on demand (A1); cups left in a pitcher at close are discarded, so their lemons
and sugar count as consumed.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from lemonade.engine import inventory
from lemonade.engine.config import Config
from lemonade.engine.demand import DemandBreakdown, loss_reason
from lemonade.engine.models import Inventory, Recipe
from lemonade.engine.types import Item, LossReason, StopReason


@dataclass(frozen=True, slots=True)
class SalesOutcome:
    cups_sold: int
    inventory: Inventory
    consumed: dict[Item, int]
    lost_sales: dict[LossReason, int]
    stop_reason: StopReason | None


def _cannot_serve(inv: Inventory, recipe: Recipe, pitcher_cups: int) -> StopReason | None:
    """Why the next cup can't be served (checked cup, ice, then pitcher ingredients)."""
    if inv.count(Item.CUP) < 1:
        return StopReason.SOLD_OUT_CUPS
    if inv.count(Item.ICE) < recipe.ice_per_cup:
        return StopReason.SOLD_OUT_ICE
    if pitcher_cups == 0:
        if inv.count(Item.LEMON) < recipe.lemons_per_pitcher:
            return StopReason.SOLD_OUT_LEMONS
        if inv.count(Item.SUGAR) < recipe.sugar_per_pitcher:
            return StopReason.SOLD_OUT_SUGAR
    return None


def _use(inv: Inventory, consumed: dict[Item, int], item: Item, qty: int) -> Inventory:
    consumed[item] += qty
    return inventory.consume(inv, item, qty)


def sell(
    customers: int,
    breakdown: DemandBreakdown,
    inv: Inventory,
    recipe: Recipe,
    cfg: Config,
    rng: random.Random,
) -> SalesOutcome:
    """Serve customers one by one until the day ends or stock runs out.

    Every customer rolls buy/no-buy (so RNG use doesn't depend on stock). After a stop,
    would-be buyers are counted as SOLD_OUT. Invariant: sold + sum(lost) == customers.
    """
    consumed = {item: 0 for item in Item}
    lost = {reason: 0 for reason in LossReason}
    sold, pitcher_cups = 0, 0
    stop: StopReason | None = None
    for _ in range(customers):
        if rng.random() >= breakdown.buy_prob:
            lost[loss_reason(breakdown, cfg)] += 1
            continue
        stop = stop or _cannot_serve(inv, recipe, pitcher_cups)
        if stop is not None:
            lost[LossReason.SOLD_OUT] += 1
            continue
        if pitcher_cups == 0:
            inv = _use(inv, consumed, Item.LEMON, recipe.lemons_per_pitcher)
            inv = _use(inv, consumed, Item.SUGAR, recipe.sugar_per_pitcher)
            pitcher_cups = cfg.game.cups_per_pitcher
        inv = _use(inv, consumed, Item.ICE, recipe.ice_per_cup)
        inv = _use(inv, consumed, Item.CUP, 1)
        pitcher_cups -= 1
        sold += 1
    return SalesOutcome(sold, inv, consumed, lost, stop)
