"""`simulate_day`: the ONLY orchestrator of a day (CLAUDE.md section 6).

Each step lives in its own module; this file only wires them together. Game-level status
(bankruptcy, win, achievements) is applied afterwards by `game.end_day`.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from lemonade.engine import inventory, market, weather
from lemonade.engine.config import Config
from lemonade.engine.demand import DemandBreakdown, compute_demand, reputation_delta
from lemonade.engine.models import DayContext, DayPlan, DayResult, Effect, GameState, Inventory
from lemonade.engine.recipes import effective_recipe
from lemonade.engine.registry import EVENTS, MODIFIERS, GameEvent, active_upgrades
from lemonade.engine.rng import day_rng
from lemonade.engine.sales import SalesOutcome, sell
from lemonade.engine.types import Cents, Item, LossReason, StopReason


@dataclass(frozen=True, slots=True)
class _FiredEvent:
    event: GameEvent
    ctx: DayContext  # carries the event's own RNG stream


def _context(state: GameState, plan: DayPlan, cfg: Config) -> DayContext:
    w, temp = weather.resolve(state.forecast, day_rng(state.seed, state.day, "weather"), cfg)
    return DayContext(
        state=state,
        plan=plan,
        weather=w,
        temp_f=temp,
        day_of_week=(state.day - 1) % 7,
        holiday=None,
        rng=day_rng(state.seed, state.day, "context"),
        cfg=cfg,
    )


def _fire_start_events(ctx: DayContext) -> list[_FiredEvent]:
    """Roll every registered event on its own RNG stream (so events never perturb each other)."""
    fired = []
    for event_id in sorted(EVENTS):
        event = EVENTS[event_id]
        event_ctx = replace(ctx, rng=day_rng(ctx.state.seed, ctx.state.day, f"event:{event_id}"))
        if event_ctx.rng.random() < event.chance(event_ctx):
            fired.append(_FiredEvent(event, event_ctx))
    return fired


def _collect_effects(ctx: DayContext, start_effects: list[Effect]) -> tuple[Effect, ...]:
    effects: list[Effect] = []
    for modifier_id in sorted(MODIFIERS):
        effects.extend(MODIFIERS[modifier_id].effects(ctx))
    for handler in active_upgrades(ctx.state):
        effects.extend(handler.effects(ctx))
    return (*effects, *start_effects)


def _closed_sales(ctx: DayContext) -> SalesOutcome:
    zeros = {item: 0 for item in Item}
    lost = {reason: 0 for reason in LossReason}
    return SalesOutcome(0, ctx.state.inventory, zeros, lost, StopReason.STAND_CLOSED)


def _run_sales(ctx: DayContext, demand: DemandBreakdown, *, closed: bool) -> SalesOutcome:
    if closed:
        return _closed_sales(ctx)
    rng = day_rng(ctx.state.seed, ctx.state.day, "sales")
    recipe = effective_recipe(ctx.state, ctx.plan.recipe, ctx.cfg)
    return sell(demand.customers, demand, ctx.state.inventory, recipe, ctx.cfg, rng)


def _upkeep(ctx: DayContext, inv: Inventory) -> tuple[Inventory, int, dict[Item, int]]:
    """End-of-day: melt ice (minus the best upgrade retention) and spoil expired batches."""
    retention = max((h.ice_retention(ctx.cfg) for h in active_upgrades(ctx.state)), default=0.0)
    inv, melted = inventory.melt(inv, retention)
    inv, spoiled = inventory.spoil(inv, ctx.state.day)
    return inv, melted, spoiled


def _result(
    ctx: DayContext,
    demand: DemandBreakdown,
    sales: SalesOutcome,
    effects: tuple[Effect, ...],
    messages: list[str],
    spend: Cents,
    purchased: dict[Item, int],
) -> DayResult:
    revenue = sales.cups_sold * ctx.plan.price_per_cup
    return DayResult(
        day=ctx.state.day,
        weather=ctx.weather,
        temp_f=ctx.temp_f,
        potential_customers=demand.customers,
        cups_sold=sales.cups_sold,
        lost_sales=sales.lost_sales,
        stop_reason=sales.stop_reason,
        revenue=revenue,
        spend=spend,
        profit=revenue - spend,
        ice_melted=0,
        spoiled={},
        effects=effects,
        events=tuple(messages),
        reputation_delta=reputation_delta(demand, sales.cups_sold, ctx.cfg),
        feedback=demand.feedback if sales.cups_sold else (),
        purchased=purchased,
        consumed=sales.consumed,
        taste_score=demand.taste,
        buy_prob=demand.buy_prob,
    )


def simulate_day(state: GameState, plan: DayPlan, cfg: Config) -> tuple[GameState, DayResult]:
    """Play one day: validate, buy, resolve weather, sell, upkeep, advance to the next day.

    Raises InvalidPlan / InsufficientFunds before any change. Invariants: cash never goes below
    0; stock is conserved (start + purchased == consumed + remaining + melted + spoiled).
    """
    market.validate_plan(state, plan, cfg)
    spend = market.plan_cost(state, plan, cfg)
    bought, purchased = market.apply_purchases(state, plan, cfg)
    ctx = _context(bought, plan, cfg)

    fired = _fire_start_events(ctx)
    starts = [f.event.on_day_start(f.ctx) for f in fired]
    effects = _collect_effects(ctx, [e for o in starts for e in o.effects])
    demand = compute_demand(ctx, effects)
    sales = _run_sales(ctx, demand, closed=any(o.close_stand for o in starts))
    messages = [o.message for o in starts if o.message]
    result = _result(ctx, demand, sales, effects, messages, spend, purchased)

    ends = [f.event.on_day_end(f.ctx, result) for f in fired]
    messages += [o.message for o in ends if o.message]
    event_cash = sum(o.cash_delta for o in (*starts, *ends))
    inv, melted, spoiled = _upkeep(ctx, sales.inventory)
    cash = max(0, bought.cash + result.revenue + event_cash)
    result = replace(
        result,
        profit=cash - state.cash,
        cash_end=cash,
        ice_melted=melted,
        spoiled=spoiled,
        events=tuple(messages),
    )
    return _advance(bought, cfg, cash, inv, result), result


def _advance(
    state: GameState, cfg: Config, cash: Cents, inv: Inventory, result: DayResult
) -> GameState:
    """Move to the next morning: new cash, stock, reputation, forecast and history."""
    next_day = state.day + 1
    return replace(
        state,
        day=next_day,
        cash=cash,
        inventory=inv,
        reputation=max(0.0, min(1.0, state.reputation + result.reputation_delta)),
        forecast=weather.generate_forecast(day_rng(state.seed, next_day, "forecast"), cfg),
        history=(*state.history, result),
    )
