"""Derived statistics over a game's history (read-only; used by the Stats screen).

Owned by the UI+TOOLS lane during Phase 1 (see CLAUDE.md section 14).
"""

from __future__ import annotations

from dataclasses import dataclass

from lemonade.engine.models import DayResult, Effect, GameState
from lemonade.engine.types import Cents


@dataclass(frozen=True, slots=True)
class Totals:
    days: int
    customers: int
    cups_sold: int
    revenue: Cents
    spend: Cents
    profit: Cents


def cash_series(state: GameState) -> tuple[Cents, ...]:
    """Cash before day 1 followed by cash at the end of each day played (empty if none)."""
    if not state.history:
        return ()
    first = state.history[0]
    return (first.cash_end - first.profit, *(r.cash_end for r in state.history))


def best_day(state: GameState) -> DayResult | None:
    """The most profitable day (earliest on ties), or None before day 1 is played."""
    return max(state.history, key=lambda r: r.profit, default=None)


def worst_day(state: GameState) -> DayResult | None:
    """The least profitable day (earliest on ties), or None before day 1 is played."""
    return min(state.history, key=lambda r: r.profit, default=None)


def totals(state: GameState) -> Totals:
    """Sums across every day played."""
    h = state.history
    return Totals(
        days=len(h),
        customers=sum(r.potential_customers for r in h),
        cups_sold=sum(r.cups_sold for r in h),
        revenue=sum(r.revenue for r in h),
        spend=sum(r.spend for r in h),
        profit=sum(r.profit for r in h),
    )


def effect_magnitude(effect: Effect) -> float:
    """How strongly an effect moves its factor: |value - 1| for 'mul', |value| for 'add'."""
    return abs(effect.value - 1) if effect.op == "mul" else abs(effect.value)


def ranked_effects(result: DayResult) -> tuple[Effect, ...]:
    """The day's effects, strongest first (stable for ties), for the "why?" breakdown."""
    return tuple(sorted(result.effects, key=effect_magnitude, reverse=True))


def sell_through(state: GameState) -> float:
    """Share of all passers-by who bought a cup across the game (0.0 before day 1)."""
    t = totals(state)
    return t.cups_sold / t.customers if t.customers else 0.0
