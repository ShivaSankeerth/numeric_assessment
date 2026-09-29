"""Immutable domain models. Transitions return new objects via `dataclasses.replace`.

Dict-typed fields are read-only by convention: never mutate them, always build a new dict.
"""

from __future__ import annotations

import random
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from lemonade.engine.types import (
    Cents,
    Factor,
    GameStatus,
    Item,
    LossReason,
    StopReason,
    Weather,
)

if TYPE_CHECKING:
    from lemonade.engine.config import Config


@dataclass(frozen=True, slots=True)
class Batch:
    """A quantity of one item sharing an expiry day (None = never expires)."""

    qty: int
    expires_on_day: int | None  # last day the batch is usable


@dataclass(frozen=True, slots=True)
class Inventory:
    """Stock on hand, as batches per item. Consumption is FIFO by expiry."""

    batches: Mapping[Item, tuple[Batch, ...]]

    @classmethod
    def empty(cls) -> Inventory:
        return cls(batches={item: () for item in Item})

    def count(self, item: Item) -> int:
        return sum(b.qty for b in self.batches.get(item, ()))


@dataclass(frozen=True, slots=True)
class Recipe:
    """Per pitcher; one pitcher = `cfg.game.cups_per_pitcher` (12) cups."""

    lemons_per_pitcher: int = 6
    sugar_per_pitcher: int = 4
    ice_per_cup: int = 3


@dataclass(frozen=True, slots=True)
class Purchase:
    item: Item
    packs: int


@dataclass(frozen=True, slots=True)
class DayPlan:
    purchases: tuple[Purchase, ...]
    recipe: Recipe
    price_per_cup: Cents
    location_id: str = "park"
    upgrade_purchases: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Forecast:
    predicted: Weather
    predicted_temp_f: int


@dataclass(frozen=True, slots=True)
class Effect:
    factor: Factor
    op: Literal["mul", "add"]
    value: float
    reason: str  # "Heat wave: +40% foot traffic"
    source: str  # modifier/event/upgrade id


@dataclass(frozen=True, slots=True)
class EventOutcome:
    """What an event hook returns. All fields are optional."""

    effects: tuple[Effect, ...] = ()
    message: str | None = None
    close_stand: bool = False
    cash_delta: Cents = 0  # negative = fine; clamped so cash never goes below 0


@dataclass(frozen=True, slots=True)
class DayResult:
    day: int
    weather: Weather
    temp_f: int
    potential_customers: int
    cups_sold: int
    lost_sales: dict[LossReason, int]
    stop_reason: StopReason | None
    revenue: Cents
    spend: Cents  # supplies + upgrades + fees
    profit: Cents
    ice_melted: int
    spoiled: dict[Item, int]
    effects: tuple[Effect, ...]
    events: tuple[str, ...]
    reputation_delta: float
    feedback: tuple[str, ...]
    purchased: dict[Item, int] = field(default_factory=dict)  # units bought today
    consumed: dict[Item, int] = field(default_factory=dict)  # units used by sales
    taste_score: float = 0.0
    buy_prob: float = 0.0
    cash_end: Cents = 0  # cash at the end of this day (for charts / stats)
    achievements_unlocked: tuple[str, ...] = ()  # achievement ids first unlocked this day


@dataclass(frozen=True, slots=True)
class Loan:
    principal: Cents
    rate_pct: int
    due_day: int


@dataclass(frozen=True, slots=True)
class GameState:
    seed: int
    day: int
    cash: Cents
    inventory: Inventory
    reputation: float  # 0.0..1.0
    upgrades: frozenset[str]
    forecast: Forecast  # for the upcoming day
    history: tuple[DayResult, ...]
    loan: Loan | None = None
    achievements: frozenset[str] = frozenset()
    status: GameStatus = GameStatus.PLAYING
    difficulty: str = "normal"


@dataclass(frozen=True, slots=True)
class DayContext:
    """Read-only bundle handed to modifiers, events and upgrade handlers."""

    state: GameState  # after purchases were applied
    plan: DayPlan
    weather: Weather
    temp_f: int
    day_of_week: int  # 0..6, day 1 = 0
    holiday: str | None
    rng: random.Random
    cfg: Config


@dataclass(frozen=True, slots=True)
class PlanPreview:
    """Live numbers for the plan screen footer."""

    cost: Cents
    cash_after: Cents
    cups_makeable: int
