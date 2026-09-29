"""Required invariants (CLAUDE.md section 11) over random multi-day games."""

from hypothesis import given, settings

from factories import default_cfg
from lemonade.engine import market
from lemonade.engine.errors import LemonadeError
from lemonade.engine.game import new_game, play_day
from lemonade.engine.inventory import cups_makeable
from lemonade.engine.models import DayPlan, DayResult, GameState
from lemonade.engine.types import GameStatus, Item
from strategies import plan_sequences, seeds

CFG = default_cfg()
FAST = settings(max_examples=50, deadline=None)


def play(seed: int, plans: list[DayPlan]) -> list[tuple[GameState, DayPlan, GameState, DayResult]]:
    """Play the plans in order; illegal plans are skipped (state must be unchanged)."""
    state = new_game(seed, CFG)
    days = []
    for plan in plans:
        if state.status is not GameStatus.PLAYING:
            break
        try:
            after, result = play_day(state, plan, CFG)
        except LemonadeError:
            continue
        days.append((state, plan, after, result))
        state = after
    return days


@FAST
@given(seeds, plan_sequences)
def test_cash_never_negative(seed: int, plans: list[DayPlan]) -> None:
    for _, _, after, _ in play(seed, plans):
        assert after.cash >= 0


@FAST
@given(seeds, plan_sequences)
def test_cannot_sell_more_than_makeable(seed: int, plans: list[DayPlan]) -> None:
    for before, plan, _, result in play(seed, plans):
        stocked, _ = market.apply_purchases(before, plan, CFG)
        limit = cups_makeable(stocked.inventory, plan.recipe, CFG.game.cups_per_pitcher)
        assert result.cups_sold <= limit


@FAST
@given(seeds, plan_sequences)
def test_inventory_is_conserved(seed: int, plans: list[DayPlan]) -> None:
    for before, _, after, result in play(seed, plans):
        for item in Item:
            start = before.inventory.count(item) + result.purchased[item]
            melted = result.ice_melted if item is Item.ICE else 0
            end = (
                result.consumed[item]
                + after.inventory.count(item)
                + melted
                + result.spoiled.get(item, 0)
            )
            assert start == end, item


@FAST
@given(seeds, plan_sequences)
def test_same_seed_and_plans_are_deterministic(seed: int, plans: list[DayPlan]) -> None:
    assert play(seed, plans) == play(seed, plans)


@FAST
@given(seeds, plan_sequences)
def test_ice_is_zero_at_end_of_day_without_cooler(seed: int, plans: list[DayPlan]) -> None:
    for _, _, after, _ in play(seed, plans):
        if "cooler" not in after.upgrades:
            assert after.inventory.count(Item.ICE) == 0
