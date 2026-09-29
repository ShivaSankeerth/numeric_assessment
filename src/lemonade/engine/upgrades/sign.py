"""Sign: a flat boost to foot traffic every day."""

from lemonade.engine.demand import fmt_mul
from lemonade.engine.models import DayContext, Effect
from lemonade.engine.registry import BaseUpgrade, register_upgrade
from lemonade.engine.types import Factor


@register_upgrade
class Sign(BaseUpgrade):
    id = "sign"

    def effects(self, ctx: DayContext) -> list[Effect]:
        mul = ctx.cfg.upgrades[self.id].params["traffic_mul"]
        return [Effect(Factor.TRAFFIC, "mul", mul, f"Sign: {fmt_mul(mul)} foot traffic", self.id)]
