"""Weekends bring more foot traffic."""

from lemonade.engine import dates
from lemonade.engine.demand import fmt_mul
from lemonade.engine.models import DayContext, Effect
from lemonade.engine.registry import register_modifier
from lemonade.engine.types import Factor


@register_modifier
class DayOfWeekModifier:
    id = "day_of_week"

    def effects(self, ctx: DayContext) -> list[Effect]:
        day = ctx.state.day
        mul = ctx.cfg.calendar.weekend_traffic_mul
        if not dates.is_weekend(day, ctx.cfg) or mul == 1.0:
            return []
        reason = f"Weekend ({dates.day_name(day, ctx.cfg)}): {fmt_mul(mul)} foot traffic"
        return [Effect(Factor.TRAFFIC, "mul", mul, reason, self.id)]
