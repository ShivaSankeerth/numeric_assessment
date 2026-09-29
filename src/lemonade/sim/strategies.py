"""Bot strategies. A strategy is `callable(state, cfg) -> DayPlan`, registered by name.

Bots only use public engine functions and config (never engine internals), exactly like a
player would: look at the forecast and prices, then decide what to buy, the recipe and the price.
"""

from __future__ import annotations

import math
from collections.abc import Callable

from lemonade.engine import demand
from lemonade.engine.config import Config
from lemonade.engine.game import preview_plan
from lemonade.engine.models import DayPlan, GameState, Purchase, Recipe
from lemonade.engine.types import Cents, Item, Weather

Strategy = Callable[[GameState, Config], DayPlan]
STRATEGIES: dict[str, Strategy] = {}

NAIVE_TARGET_CUPS = 30
NAIVE_PRICE = 50
LOCATION = "park"


def register(name: str) -> Callable[[Strategy], Strategy]:
    def deco(fn: Strategy) -> Strategy:
        STRATEGIES[name] = fn
        return fn

    return deco


def _packs_for(state: GameState, cfg: Config, recipe: Recipe, cups: int) -> tuple[Purchase, ...]:
    """Packs to buy so current stock + purchases can serve `cups` cups with `recipe`."""
    pitchers = math.ceil(cups / cfg.game.cups_per_pitcher)
    needs = {
        Item.LEMON: pitchers * recipe.lemons_per_pitcher,
        Item.SUGAR: pitchers * recipe.sugar_per_pitcher,
        Item.ICE: cups * recipe.ice_per_cup,
        Item.CUP: cups,
    }
    out = []
    for item, need in needs.items():
        missing = need - state.inventory.count(item)
        if missing > 0:
            out.append(Purchase(item, math.ceil(missing / cfg.items[item].pack_size)))
    return tuple(out)


def stock_plan(state: GameState, cfg: Config, recipe: Recipe, price: Cents, cups: int) -> DayPlan:
    """A plan stocking for `cups` cups, scaled down until the engine says it's affordable."""
    while True:
        plan = DayPlan(
            purchases=_packs_for(state, cfg, recipe, cups),
            recipe=recipe,
            price_per_cup=price,
            location_id=LOCATION,
        )
        if cups <= 0 or preview_plan(state, plan, cfg).cash_after >= 0:
            return plan
        cups = int(cups * 0.8)


def expected_customers(state: GameState, cfg: Config) -> int:
    """Passers-by if the forecast is right (weather traffic only; events ignored)."""
    base = cfg.locations[LOCATION].base_traffic
    return round(base * cfg.weather.traffic[state.forecast.predicted])


def expected_sales(state: GameState, cfg: Config, recipe: Recipe, price: Cents) -> int:
    """Cups we'd sell at this price/recipe if the forecast holds (engine demand functions)."""
    fair = demand.fair_price((), cfg) * cfg.weather.price_tolerance[state.forecast.predicted]
    pf = demand.price_factor(price, fair, cfg)
    taste, _ = demand.recipe_score(recipe, state.forecast.predicted_temp_f, cfg)
    prob = demand.buy_probability(pf, taste, state.reputation, (), cfg)
    return round(expected_customers(state, cfg) * prob)


@register("naive")
def naive(state: GameState, cfg: Config) -> DayPlan:
    """Same plan every day: default recipe, 50c, stock for 30 cups whatever the weather."""
    return stock_plan(state, cfg, Recipe(), NAIVE_PRICE, NAIVE_TARGET_CUPS)


@register("greedy")
def greedy(state: GameState, cfg: Config) -> DayPlan:
    """Default recipe at the base fair price; buy exactly for the expected demand."""
    recipe, price = Recipe(), cfg.demand.base_fair_price
    return stock_plan(state, cfg, recipe, price, expected_sales(state, cfg, recipe, price))


def _round_price(cents: float) -> Cents:
    return max(5, int(round(cents / 5) * 5))


@register("forecast")
def forecast_aware(state: GameState, cfg: Config) -> DayPlan:
    """Ideal recipe for the forecast temperature, price at the forecast's fair price,
    10% safety stock, and no stock at all when a storm is forecast."""
    fc = state.forecast
    recipe = Recipe(
        lemons_per_pitcher=cfg.demand.ideal_lemons,
        sugar_per_pitcher=cfg.demand.ideal_sugar,
        ice_per_cup=demand.ideal_ice(fc.predicted_temp_f, cfg),
    )
    price = _round_price(demand.fair_price((), cfg) * cfg.weather.price_tolerance[fc.predicted])
    cups = 0 if fc.predicted is Weather.STORM else expected_sales(state, cfg, recipe, price)
    return stock_plan(state, cfg, recipe, price, math.ceil(cups * 1.1))
