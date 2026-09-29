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


def _cannot_serve(stock: dict[Item, int], recipe: Recipe, pitcher_cups: int) -> StopReason | None:
    """Why the next cup can't be served (checked cup, ice, then pitcher ingredients)."""
    if stock[Item.CUP] < 1:
        return StopReason.SOLD_OUT_CUPS
    if stock[Item.ICE] < recipe.ice_per_cup:
        return StopReason.SOLD_OUT_ICE
    if pitcher_cups == 0:
        if stock[Item.LEMON] < recipe.lemons_per_pitcher:
            return StopReason.SOLD_OUT_LEMONS
        if stock[Item.SUGAR] < recipe.sugar_per_pitcher:
            return StopReason.SOLD_OUT_SUGAR
    return None


def _write_back(inv: Inventory, consumed: dict[Item, int]) -> Inventory:
    """Apply the day's total consumption once (FIFO, so identical to consuming per cup)."""
    for item, qty in consumed.items():
        if qty:
            inv = inventory.consume(inv, item, qty)
    return inv


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
    Stock is tracked as plain counters and written back to the batches once at the end.
    """
    stock = {item: inv.count(item) for item in Item}
    consumed = {item: 0 for item in Item}
    lost = {reason: 0 for reason in LossReason}
    no_sale = loss_reason(breakdown, cfg)
    per_pitcher = {Item.LEMON: recipe.lemons_per_pitcher, Item.SUGAR: recipe.sugar_per_pitcher}
    per_cup = {Item.ICE: recipe.ice_per_cup, Item.CUP: 1}
    buy_prob, roll = breakdown.buy_prob, rng.random
    sold, pitcher_cups = 0, 0
    stop: StopReason | None = None
    for _ in range(customers):
        if roll() >= buy_prob:
            lost[no_sale] += 1
            continue
        stop = stop or _cannot_serve(stock, recipe, pitcher_cups)
        if stop is not None:
            lost[LossReason.SOLD_OUT] += 1
            continue
        uses = per_cup if pitcher_cups else {**per_cup, **per_pitcher}
        if not pitcher_cups:
            pitcher_cups = cfg.game.cups_per_pitcher
        for item, qty in uses.items():
            stock[item] -= qty
            consumed[item] += qty
        pitcher_cups -= 1
        sold += 1
    return SalesOutcome(sold, _write_back(inv, consumed), consumed, lost, stop)
