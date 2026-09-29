"""Supplier prices, bulk pricing, plan validation and applying purchases."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace

from lemonade.engine import inventory
from lemonade.engine.config import Config
from lemonade.engine.errors import InsufficientFunds, InvalidPlan
from lemonade.engine.models import DayPlan, GameState, Recipe
from lemonade.engine.rng import day_rng
from lemonade.engine.types import Cents, Item


def dollars(cents: Cents) -> str:
    """Integer-only money text for error messages (UI formatting lives in ui/format.py)."""
    return f"${cents // 100}.{cents % 100:02d}"


@dataclass(frozen=True, slots=True)
class MarketDay:
    """Today's supplier price adjustments (whole percents), rolled once per game day."""

    change_pct: Mapping[Item, int]  # daily fluctuation per item (0 when disabled)
    shortage: Item | None  # item marked up by `shortage_markup_pct` today, if any


def market_day(state: GameState, cfg: Config) -> MarketDay:
    """Roll today's fluctuation and shortage from `day_rng(seed, day, "market")`.

    The shortage roll comes first so toggling fluctuation never changes whether a shortage hits.
    Lemon shortages live here, not in EVENTS: the player must see prices before buying.
    """
    m = cfg.market
    rng = day_rng(state.seed, state.day, "market")
    short = rng.random() < m.shortage_chance
    shortage = m.shortage_item if m.shortages and short else None
    change = {
        item: rng.randint(-m.fluctuation_pct, m.fluctuation_pct) if m.fluctuation else 0
        for item in Item
    }
    return MarketDay(change_pct=change, shortage=shortage)


def _apply_pcts(price: Cents, pcts: Iterable[int]) -> Cents:
    """`price` scaled by each (100 + pct)%, with one half-up rounding at the end."""
    num, den = price, 1
    for pct in pcts:
        num *= 100 + pct
        den *= 100
    return (num + den // 2) // den


def todays_pack_prices(state: GameState, cfg: Config) -> dict[Item, Cents]:
    """Per-pack price of each item today: base price, daily fluctuation, shortage markup.

    Deterministic per (seed, day). Always use this (never `cfg.items[...].pack_price`) for prices.
    """
    today = market_day(state, cfg)
    prices = {}
    for item, item_cfg in cfg.items.items():
        pcts = [today.change_pct[item]]
        if today.shortage is item:
            pcts.append(cfg.market.shortage_markup_pct)
        prices[item] = _apply_pcts(item_cfg.pack_price, pcts)
    return prices


def market_notes(state: GameState, cfg: Config) -> tuple[str, ...]:
    """Player-facing notes about today's supplier prices, shown on the Shop tab before buying.

    Shortage first, then one note per item whose price moved, in Item order, e.g.
    ("Lemon shortage: lemons +50% today", "Supplier prices: sugar -8%"). Empty on a quiet day.
    """
    today = market_day(state, cfg)
    notes = []
    if today.shortage is not None:
        name = today.shortage.value
        pct = cfg.market.shortage_markup_pct
        notes.append(f"{name.capitalize()} shortage: {name}s {pct:+d}% today")
    for item, pct in today.change_pct.items():
        if pct:
            notes.append(f"Supplier prices: {item.value} {pct:+d}%")
    return tuple(notes)


def discount_pct(item: Item, packs: int, cfg: Config) -> int:
    """Bulk discount (whole percent) for buying `packs` packs: the best tier reached."""
    pct = 0
    for tier in cfg.items[item].tiers:
        if packs >= tier.min_packs:
            pct = tier.discount_pct
    return pct


def purchase_cost(item: Item, packs: int, pack_price: Cents, cfg: Config) -> Cents:
    """Total cost of `packs` packs after bulk discount, rounded half-up to the cent."""
    pct = discount_pct(item, packs, cfg)
    return (packs * pack_price * (100 - pct) + 50) // 100


def plan_cost(state: GameState, plan: DayPlan, cfg: Config) -> Cents:
    """Everything the plan charges up front: supplies + upgrades + location rent.

    Unknown upgrade/location ids cost 0 here; `validate_plan` rejects them.
    """
    prices = todays_pack_prices(state, cfg)
    supplies = sum(purchase_cost(p.item, p.packs, prices[p.item], cfg) for p in plan.purchases)
    upgrades = sum(cfg.upgrades[u].cost for u in plan.upgrade_purchases if u in cfg.upgrades)
    location = cfg.locations.get(plan.location_id)
    return supplies + upgrades + (location.rent if location else 0)


def _check_range(name: str, value: int, bounds: tuple[int, int]) -> None:
    low, high = bounds
    if not low <= value <= high:
        raise InvalidPlan(f"{name} must be between {low} and {high}, got {value}")


def _validate_recipe(recipe: Recipe, cfg: Config) -> None:
    limits = cfg.game.recipe_limits
    _check_range("Lemons per pitcher", recipe.lemons_per_pitcher, limits.lemons)
    _check_range("Sugar per pitcher", recipe.sugar_per_pitcher, limits.sugar)
    _check_range("Ice per cup", recipe.ice_per_cup, limits.ice)


def _validate_purchases(plan: DayPlan) -> None:
    for p in plan.purchases:
        if p.packs < 1:
            raise InvalidPlan(f"Must buy at least 1 pack of {p.item}, got {p.packs}")
    dupes = [item for item, n in Counter(p.item for p in plan.purchases).items() if n > 1]
    if dupes:
        raise InvalidPlan(f"Each item may appear once per plan; duplicated: {dupes[0]}")


def _validate_upgrades(state: GameState, plan: DayPlan, cfg: Config) -> None:
    if len(set(plan.upgrade_purchases)) != len(plan.upgrade_purchases):
        raise InvalidPlan("Each upgrade can only be bought once")
    for up_id in plan.upgrade_purchases:
        if up_id not in cfg.upgrades:
            raise InvalidPlan(f"Unknown upgrade '{up_id}'")
        if up_id in state.upgrades:
            raise InvalidPlan(f"You already own the {cfg.upgrades[up_id].name}")


def validate_plan(state: GameState, plan: DayPlan, cfg: Config) -> None:
    """Raise InvalidPlan / InsufficientFunds (with a player-facing message) if `plan` is illegal."""
    if plan.location_id not in cfg.locations:
        raise InvalidPlan(f"Unknown location '{plan.location_id}'")
    _validate_purchases(plan)
    _validate_recipe(plan.recipe, cfg)
    _check_range("Price per cup (cents)", plan.price_per_cup, cfg.game.price_limits)
    _validate_upgrades(state, plan, cfg)
    cost = plan_cost(state, plan, cfg)
    if cost > state.cash:
        raise InsufficientFunds(
            f"This plan costs {dollars(cost)} but you only have {dollars(state.cash)}"
        )


def apply_purchases(
    state: GameState, plan: DayPlan, cfg: Config
) -> tuple[GameState, dict[Item, int]]:
    """Charge the plan cost and add purchased stock and upgrades. Assumes `validate_plan` passed.

    Returns (new state, units purchased per item). Batches expire on
    `day + shelf_life_days - 1` (their last usable day).
    """
    inv = state.inventory
    purchased = {item: 0 for item in Item}
    for p in plan.purchases:
        item_cfg = cfg.items[p.item]
        units = p.packs * item_cfg.pack_size
        shelf = item_cfg.shelf_life_days
        expiry = None if shelf is None else state.day + shelf - 1
        inv = inventory.add(inv, p.item, units, expiry)
        purchased[p.item] = units
    new_state = replace(
        state,
        cash=state.cash - plan_cost(state, plan, cfg),
        inventory=inv,
        upgrades=state.upgrades | frozenset(plan.upgrade_purchases),
    )
    return new_state, purchased


def cost_to_make_one_cup(state: GameState, cfg: Config) -> Cents:
    """Cheapest spend needed before one cup can be served (0 if one can be served now).

    A "minimal cup" uses the recipe lower limits (1 lemon, no sugar, no ice) and one paper cup,
    so melted ice never makes a player bankrupt. Used by the bankruptcy rule (assumption A3).
    """
    limits = cfg.game.recipe_limits
    needs = {
        Item.LEMON: limits.lemons[0],
        Item.SUGAR: limits.sugar[0],
        Item.ICE: limits.ice[0],
        Item.CUP: 1,
    }
    prices = todays_pack_prices(state, cfg)
    total = 0
    for item, need in needs.items():
        missing = need - state.inventory.count(item)
        if missing > 0:
            total += math.ceil(missing / cfg.items[item].pack_size) * prices[item]
    return total
