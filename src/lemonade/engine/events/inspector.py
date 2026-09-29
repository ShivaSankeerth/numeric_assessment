"""Health inspector: visits at random and fines bad lemonade at the end of the day.

Fails inspection if anything was sold and either the taste score is below `taste_threshold`
or cups were served without ice on a hot day. The fine is `fine` cents (cash never below 0).
"""

from lemonade.engine.market import dollars
from lemonade.engine.models import DayContext, DayResult, EventOutcome
from lemonade.engine.registry import BaseEvent, register_event
from lemonade.engine.types import Weather


def _violation(ctx: DayContext, result: DayResult) -> str | None:
    params = ctx.cfg.events[Inspector.id].params
    if result.taste_score < params["taste_threshold"]:
        return "the lemonade tastes awful"
    if ctx.weather is Weather.HOT and ctx.plan.recipe.ice_per_cup == 0:
        return "warm lemonade on a hot day"
    return None


@register_event
class Inspector(BaseEvent):
    id = "inspector"

    def chance(self, ctx: DayContext) -> float:
        return ctx.cfg.events[self.id].base_chance

    def on_day_end(self, ctx: DayContext, result: DayResult) -> EventOutcome:
        if result.cups_sold == 0:
            return EventOutcome()
        problem = _violation(ctx, result)
        if problem is None:
            return EventOutcome(message="The health inspector visited and was satisfied.")
        fine = int(ctx.cfg.events[self.id].params["fine"])
        return EventOutcome(
            message=f"The health inspector fined you {dollars(fine)}: {problem}.",
            cash_delta=-fine,
        )
