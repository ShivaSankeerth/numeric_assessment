"""Heat wave: on sunny or hot days, a chance of a big boost to foot traffic."""

from lemonade.engine.demand import fmt_mul
from lemonade.engine.models import DayContext, Effect, EventOutcome
from lemonade.engine.registry import BaseEvent, register_event
from lemonade.engine.types import Factor, Weather


@register_event
class HeatWave(BaseEvent):
    id = "heat_wave"

    def chance(self, ctx: DayContext) -> float:
        if ctx.weather not in (Weather.SUNNY, Weather.HOT):
            return 0.0
        return ctx.cfg.events[self.id].base_chance

    def on_day_start(self, ctx: DayContext) -> EventOutcome:
        mul = ctx.cfg.events[self.id].params["traffic_mul"]
        effect = Effect(
            Factor.TRAFFIC, "mul", mul, f"Heat wave: {fmt_mul(mul)} foot traffic", self.id
        )
        return EventOutcome(effects=(effect,), message="A heat wave hits! Everyone is thirsty.")
