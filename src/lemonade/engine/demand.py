"""Effect aggregation and the demand model (CLAUDE.md section 7). All constants in `[demand]`.

traffic      = base_traffic * prod(TRAFFIC mul) + sum(TRAFFIC add)
fair_price   = base_fair_price * prod(PRICE_TOLERANCE mul) + sum(PRICE_TOLERANCE add)
price_factor = clamp(1 - (price - fair) / fair, 0, max_price_factor)
taste        = clamp(recipe_score * prod(TASTE mul) + sum(TASTE add), 0, 1)
buy_prob     = clamp(base + scale * price_factor * taste * (offset + rep), 0, max_buy_prob)
               * prod(BUY_PROB mul) + sum(BUY_PROB add), clamped to [0, 1]
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from lemonade.engine.config import Config
from lemonade.engine.models import DayContext, Effect, Recipe
from lemonade.engine.types import Cents, Factor, LossReason


@dataclass(frozen=True, slots=True)
class DemandBreakdown:
    """Everything the sell loop and the day report need to know about today's demand."""

    customers: int
    fair_price: float
    price_factor: float
    taste: float
    feedback: tuple[str, ...]
    buy_prob: float


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def fmt_mul(value: float) -> str:
    """Multiplier as a signed percent change for effect reasons: 1.4 -> '+40%', 0.8 -> '-20%'."""
    return f"{round((value - 1) * 100):+d}%"


def combine(effects: Iterable[Effect], factor: Factor) -> tuple[float, float]:
    """(product of 'mul' values, sum of 'add' values) for one factor."""
    mul, add = 1.0, 0.0
    for e in effects:
        if e.factor is not factor:
            continue
        if e.op == "mul":
            mul *= e.value
        else:
            add += e.value
    return mul, add


def traffic(base: int, effects: Iterable[Effect]) -> int:
    """Potential customers today (never negative)."""
    mul, add = combine(effects, Factor.TRAFFIC)
    return max(0, int(base * mul + add))


def fair_price(effects: Iterable[Effect], cfg: Config) -> float:
    """The price (cents) customers consider fair today."""
    mul, add = combine(effects, Factor.PRICE_TOLERANCE)
    return max(0.0, cfg.demand.base_fair_price * mul + add)


def price_factor(price: Cents, fair: float, cfg: Config) -> float:
    """1.0 at the fair price, 0 at double it, capped at `max_price_factor` when cheap."""
    if fair <= 0:
        return 0.0
    return _clamp(1 - (price - fair) / fair, 0.0, cfg.demand.max_price_factor)


def ideal_ice(temp_f: int, cfg: Config) -> int:
    """Ideal ice cubes per cup at this temperature (rises with heat), within recipe limits."""
    d = cfg.demand
    ideal = round(d.ideal_ice_base + (temp_f - d.ideal_ice_temp_f) / 10 * d.ideal_ice_per_10f)
    low, high = cfg.game.recipe_limits.ice
    return int(_clamp(ideal, low, high))


def _feedback(recipe: Recipe, ice: int, cfg: Config) -> list[str]:
    d = cfg.demand
    notes: list[str] = []
    if recipe.sugar_per_pitcher < d.ideal_sugar - 1:
        notes.append("Too sour!")
    elif recipe.sugar_per_pitcher > d.ideal_sugar + 1:
        notes.append("Too sweet!")
    if recipe.lemons_per_pitcher < d.ideal_lemons - 1:
        notes.append("Tastes watery.")
    elif recipe.lemons_per_pitcher > d.ideal_lemons + 1:
        notes.append("Way too lemony!")
    if recipe.ice_per_cup < ice - 1:
        notes.append("Needs more ice!")
    elif recipe.ice_per_cup > ice + 1:
        notes.append("Too much ice!")
    return notes


def recipe_score(recipe: Recipe, temp_f: int, cfg: Config) -> tuple[float, tuple[str, ...]]:
    """Taste in [0, 1] (1 = ideal recipe) plus customer feedback strings.

    Score drops by `taste_penalty_per_unit` per unit of distance from the ideal recipe;
    feedback only mentions ingredients off by more than 1.
    """
    d = cfg.demand
    ice = ideal_ice(temp_f, cfg)
    distance = (
        abs(recipe.lemons_per_pitcher - d.ideal_lemons)
        + abs(recipe.sugar_per_pitcher - d.ideal_sugar)
        + abs(recipe.ice_per_cup - ice)
    )
    score = _clamp(1 - d.taste_penalty_per_unit * distance, 0.0, 1.0)
    notes = _feedback(recipe, ice, cfg) or (["Perfect lemonade!"] if score >= 0.9 else [])
    return score, tuple(notes)


def buy_probability(
    pf: float, taste: float, reputation: float, effects: Iterable[Effect], cfg: Config
) -> float:
    """Chance that one passing customer buys a cup (see module docstring)."""
    d = cfg.demand
    base = d.base_prob + d.prob_scale * pf * taste * (d.reputation_offset + reputation)
    mul, add = combine(effects, Factor.BUY_PROB)
    return _clamp(_clamp(base, 0.0, d.max_buy_prob) * mul + add, 0.0, 1.0)


def compute_demand(ctx: DayContext, effects: tuple[Effect, ...]) -> DemandBreakdown:
    """Turn today's context and collected effects into customers and a buy probability."""
    cfg = ctx.cfg
    base = cfg.locations[ctx.plan.location_id].base_traffic
    fair = fair_price(effects, cfg)
    pf = price_factor(ctx.plan.price_per_cup, fair, cfg)
    score, notes = recipe_score(ctx.plan.recipe, ctx.temp_f, cfg)
    taste_mul, taste_add = combine(effects, Factor.TASTE)
    taste = _clamp(score * taste_mul + taste_add, 0.0, 1.0)
    return DemandBreakdown(
        customers=traffic(base, effects),
        fair_price=fair,
        price_factor=pf,
        taste=taste,
        feedback=notes,
        buy_prob=buy_probability(pf, taste, ctx.state.reputation, effects, cfg),
    )


def loss_reason(b: DemandBreakdown, cfg: Config) -> LossReason:
    """Why a customer who didn't buy walked away: the weakest factor wins."""
    if b.price_factor < cfg.demand.loss_price_threshold:
        return LossReason.TOO_EXPENSIVE
    if b.taste < cfg.demand.loss_taste_threshold:
        return LossReason.BAD_TASTE
    return LossReason.NOT_INTERESTED


def reputation_delta(b: DemandBreakdown, cups_sold: int, cfg: Config) -> float:
    """Placeholder reputation change: positive for tasty, fairly priced lemonade.

    Zero if nothing was sold. Range is [-rate/2, +rate/2]; the caller clamps reputation to [0, 1].
    """
    if cups_sold == 0:
        return 0.0
    satisfaction = b.taste * min(b.price_factor, 1.0)
    return cfg.demand.reputation_rate * (satisfaction - 0.5)
