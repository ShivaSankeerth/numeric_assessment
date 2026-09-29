"""Umbrella: on rainy/stormy days, only part of the weather's traffic penalty applies.

With weather traffic multiplier t and `rain_penalty_kept` k, the combined traffic becomes
1 - (1 - t) * k, so the umbrella's own multiplier is (1 - (1 - t) * k) / t.
"""

from lemonade.engine.demand import fmt_mul
from lemonade.engine.models import DayContext, Effect
from lemonade.engine.registry import BaseUpgrade, register_upgrade
from lemonade.engine.types import Factor, Weather

WET_WEATHER = (Weather.RAINY, Weather.STORM)


@register_upgrade
class Umbrella(BaseUpgrade):
    id = "umbrella"

    def effects(self, ctx: DayContext) -> list[Effect]:
        t = ctx.cfg.weather.traffic[ctx.weather]
        if ctx.weather not in WET_WEATHER or t <= 0 or t >= 1:
            return []
        kept = ctx.cfg.upgrades[self.id].params["rain_penalty_kept"]
        mul = (1 - (1 - t) * kept) / t
        reason = f"Umbrella: {ctx.weather.value} penalty reduced ({fmt_mul(mul)} foot traffic)"
        return [Effect(Factor.TRAFFIC, "mul", mul, reason, self.id)]
