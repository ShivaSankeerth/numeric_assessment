"""Difficulty level scales foot traffic (e.g. Hard: -15%)."""

from lemonade.engine.demand import fmt_mul
from lemonade.engine.models import DayContext, Effect
from lemonade.engine.registry import register_modifier
from lemonade.engine.types import Factor


@register_modifier
class DifficultyModifier:
    id = "difficulty"

    def effects(self, ctx: DayContext) -> list[Effect]:
        level = ctx.cfg.difficulties.get(ctx.state.difficulty)
        if level is None or level.traffic_mul == 1.0:
            return []
        mul = level.traffic_mul
        reason = f"{level.name} difficulty: {fmt_mul(mul)} foot traffic"
        return [Effect(Factor.TRAFFIC, "mul", mul, reason, self.id)]
