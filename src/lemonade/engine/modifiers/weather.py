"""Weather drives foot traffic; hot days also raise the price customers will accept."""

from lemonade.engine.demand import fmt_mul
from lemonade.engine.models import DayContext, Effect
from lemonade.engine.registry import register_modifier
from lemonade.engine.types import Factor


@register_modifier
class WeatherModifier:
    id = "weather"

    def effects(self, ctx: DayContext) -> list[Effect]:
        name = ctx.weather.value.capitalize()
        traffic = ctx.cfg.weather.traffic[ctx.weather]
        effects = [
            Effect(
                Factor.TRAFFIC,
                "mul",
                traffic,
                f"{name} weather: {fmt_mul(traffic)} foot traffic",
                self.id,
            )
        ]
        tolerance = ctx.cfg.weather.price_tolerance[ctx.weather]
        if tolerance != 1.0:
            reason = f"{name} weather: customers accept {fmt_mul(tolerance)} prices"
            effects.append(Effect(Factor.PRICE_TOLERANCE, "mul", tolerance, reason, self.id))
        return effects
