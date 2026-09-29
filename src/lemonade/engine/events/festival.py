"""Town festival: a rare, big boost to foot traffic (never during a storm)."""

from lemonade.engine.demand import fmt_mul
from lemonade.engine.models import DayContext, Effect, EventOutcome
from lemonade.engine.registry import BaseEvent, register_event
from lemonade.engine.types import Factor, Weather


@register_event
class Festival(BaseEvent):
    id = "festival"

    def chance(self, ctx: DayContext) -> float:
        if ctx.weather is Weather.STORM:
            return 0.0
        return ctx.cfg.events[self.id].base_chance

    def on_day_start(self, ctx: DayContext) -> EventOutcome:
        mul = ctx.cfg.events[self.id].params["traffic_mul"]
        reason = f"Town festival: {fmt_mul(mul)} foot traffic"
        effect = Effect(Factor.TRAFFIC, "mul", mul, reason, self.id)
        return EventOutcome(effects=(effect,), message="A festival fills the town with visitors!")
