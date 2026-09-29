"""Plugin registries (the only global mutable state) and their contracts.

To add a feature: create a module in `engine/modifiers|events|upgrades/`, decorate the class with
the matching `register_*` decorator, and import it in that package's `__init__.py`.
Decorators store a stateless instance keyed by `cls.id`; plugins read params from `ctx.cfg`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Protocol, TypeVar

from lemonade.engine.models import DayContext, DayResult, Effect, EventOutcome, GameState

if TYPE_CHECKING:
    from lemonade.engine.config import Config


class Modifier(Protocol):
    id: str

    def effects(self, ctx: DayContext) -> list[Effect]: ...


class GameEvent(Protocol):
    id: str

    def chance(self, ctx: DayContext) -> float: ...  # 0..1, may depend on day/weather
    def on_day_start(self, ctx: DayContext) -> EventOutcome: ...
    def on_day_end(self, ctx: DayContext, result: DayResult) -> EventOutcome: ...


class UpgradeHandler(Protocol):
    id: str  # must match an entry in upgrades.toml

    def effects(self, ctx: DayContext) -> list[Effect]: ...
    def ice_retention(self, cfg: Config) -> float: ...
    def lemon_yield_bonus(self, cfg: Config) -> float: ...


class BaseEvent:
    """Defaults for events: never fires, no effects. Override what you need."""

    id: ClassVar[str]

    def chance(self, ctx: DayContext) -> float:
        return 0.0

    def on_day_start(self, ctx: DayContext) -> EventOutcome:
        return EventOutcome()

    def on_day_end(self, ctx: DayContext, result: DayResult) -> EventOutcome:
        return EventOutcome()


class BaseUpgrade:
    """Defaults for upgrade handlers: no effects, no ice retention, no lemon bonus."""

    id: ClassVar[str]

    def effects(self, ctx: DayContext) -> list[Effect]:
        return []

    def ice_retention(self, cfg: Config) -> float:
        return 0.0

    def lemon_yield_bonus(self, cfg: Config) -> float:
        return 0.0


MODIFIERS: dict[str, Modifier] = {}
EVENTS: dict[str, GameEvent] = {}
UPGRADE_HANDLERS: dict[str, UpgradeHandler] = {}

T = TypeVar("T", bound=type)


def _register(registry: dict, cls: T) -> T:
    plugin_id = getattr(cls, "id", None)
    if not isinstance(plugin_id, str) or not plugin_id:
        raise ValueError(f"{cls.__name__} must define a non-empty string `id`")
    if plugin_id in registry:
        raise ValueError(f"duplicate plugin id '{plugin_id}' ({cls.__name__})")
    registry[plugin_id] = cls()
    return cls


def register_modifier(cls: T) -> T:
    """Class decorator: register a demand modifier (applies every day)."""
    return _register(MODIFIERS, cls)


def register_event(cls: T) -> T:
    """Class decorator: register a random/scheduled event."""
    return _register(EVENTS, cls)


def register_upgrade(cls: T) -> T:
    """Class decorator: register the handler for an upgrade defined in upgrades.toml."""
    return _register(UPGRADE_HANDLERS, cls)


def active_upgrades(state: GameState) -> list[UpgradeHandler]:
    """Handlers for the upgrades the player owns, in a stable (sorted id) order."""
    return [UPGRADE_HANDLERS[u] for u in sorted(state.upgrades) if u in UPGRADE_HANDLERS]
