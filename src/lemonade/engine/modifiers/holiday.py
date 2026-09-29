"""Holidays (fixed game days in game.toml) bring crowds."""

from lemonade.engine import dates
from lemonade.engine.demand import fmt_mul
from lemonade.engine.models import DayContext, Effect
from lemonade.engine.registry import register_modifier
from lemonade.engine.types import Factor


@register_modifier
class HolidayModifier:
    id = "holiday"

    def effects(self, ctx: DayContext) -> list[Effect]:
        holiday = dates.holiday_on(ctx.state.day, ctx.cfg)
        if holiday is None:
            return []
        mul = holiday.traffic_mul
        reason = f"Holiday ({holiday.name}): {fmt_mul(mul)} foot traffic"
        return [Effect(Factor.TRAFFIC, "mul", mul, reason, self.id)]
