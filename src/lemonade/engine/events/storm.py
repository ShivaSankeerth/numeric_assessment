"""Storm closure: on stormy days, a chance the stand must close (no sales at all)."""

from lemonade.engine.models import DayContext, EventOutcome
from lemonade.engine.registry import BaseEvent, register_event
from lemonade.engine.types import Weather


@register_event
class StormClosure(BaseEvent):
    id = "storm"

    def chance(self, ctx: DayContext) -> float:
        if ctx.weather is not Weather.STORM:
            return 0.0
        return ctx.cfg.events[self.id].base_chance

    def on_day_start(self, ctx: DayContext) -> EventOutcome:
        return EventOutcome(
            message="A violent storm forced you to close the stand for the day.",
            close_stand=True,
        )
