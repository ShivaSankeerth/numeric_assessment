import pytest

from factories import cfg_with, make_inventory, make_plan, make_state
from lemonade.engine.config import Config
from lemonade.engine.errors import InsufficientFunds, InvalidPlan
from lemonade.engine.models import DayContext, EventOutcome, Forecast
from lemonade.engine.registry import EVENTS, BaseEvent
from lemonade.engine.rng import day_rng
from lemonade.engine.simulation import simulate_day
from lemonade.engine.types import Item, LossReason, StopReason, Weather
from lemonade.engine.weather import generate_forecast

STOCK = {"lemon": 60, "sugar": 40, "ice": 600, "cup": 200}


def test_day_advances_and_records_history(cfg: Config) -> None:
    state = make_state(inventory=make_inventory(**STOCK))
    new, result = simulate_day(state, make_plan(), cfg)
    assert new.day == 2
    assert new.history == (result,)
    assert result.day == 1
    assert new.forecast == generate_forecast(day_rng(state.seed, 2, "forecast"), cfg)
    assert result.revenue == result.cups_sold * 50
    assert result.profit == new.cash - state.cash
    assert result.cash_end == new.cash


def test_purchases_are_charged_and_stocked(cfg: Config) -> None:
    state = make_state()
    new, result = simulate_day(state, make_plan({"lemon": 1, "cup": 1}), cfg)
    assert result.spend == 650
    assert result.purchased[Item.LEMON] == 12
    assert new.cash == 2000 - 650 + result.revenue


def test_invalid_plan_rejected_and_state_untouched(cfg: Config) -> None:
    state = make_state()
    with pytest.raises(InvalidPlan):
        simulate_day(state, make_plan(price_per_cup=0), cfg)
    with pytest.raises(InsufficientFunds):
        simulate_day(state, make_plan({"lemon": 20}), cfg)
    assert state == make_state()


def test_selling_out_mid_day_sets_stop_reason(cfg: Config) -> None:
    state = make_state(inventory=make_inventory(**{**STOCK, "cup": 3}))
    _, result = simulate_day(state, make_plan(price_per_cup=10), cfg)
    assert result.cups_sold == 3
    assert result.stop_reason is StopReason.SOLD_OUT_CUPS
    assert result.lost_sales[LossReason.SOLD_OUT] > 0


def test_ice_melts_without_cooler(cfg: Config) -> None:
    new, result = simulate_day(make_state(inventory=make_inventory(**STOCK)), make_plan(), cfg)
    assert new.inventory.count(Item.ICE) == 0
    assert result.ice_melted > 0


def test_cooler_keeps_half_the_ice(cfg: Config) -> None:
    state = make_state(inventory=make_inventory(ice=1000), upgrades=frozenset({"cooler"}))
    new, result = simulate_day(state, make_plan(), cfg)  # no cups -> nothing sold
    assert new.inventory.count(Item.ICE) == 500
    assert result.ice_melted == 500


def test_lemons_spoil_at_end_of_last_usable_day(cfg: Config) -> None:
    state = make_state(inventory=make_inventory(expires_on_day=1, lemon=12))
    new, result = simulate_day(state, make_plan(), cfg)
    assert result.spoiled == {Item.LEMON: 12}
    assert new.inventory.count(Item.LEMON) == 0


def test_forced_heat_wave_shows_in_effects_and_events() -> None:
    cfg = cfg_with(event_chances={"heat_wave": 1.0}, accuracy=1.0)
    state = make_state(forecast=Forecast(Weather.HOT, 92), inventory=make_inventory(**STOCK))
    _, result = simulate_day(state, make_plan(), cfg)
    assert "heat_wave" in {e.source for e in result.effects}
    assert any("heat wave" in m.lower() for m in result.events)


def test_every_effect_is_explained(cfg: Config) -> None:
    _, result = simulate_day(make_state(inventory=make_inventory(**STOCK)), make_plan(), cfg)
    assert result.effects
    assert all(e.reason and e.source for e in result.effects)


class _Closer(BaseEvent):
    id = "test_closer"

    def chance(self, ctx: DayContext) -> float:
        return 1.0

    def on_day_start(self, ctx: DayContext) -> EventOutcome:
        return EventOutcome(message="Closed by test", close_stand=True, cash_delta=-100_000)


def test_event_can_close_stand_and_fine_without_negative_cash(
    cfg: Config, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(EVENTS, "test_closer", _Closer())
    state = make_state(inventory=make_inventory(**STOCK))
    new, result = simulate_day(state, make_plan(), cfg)
    assert result.cups_sold == 0
    assert result.stop_reason is StopReason.STAND_CLOSED
    assert "Closed by test" in result.events
    assert new.cash == 0


def test_same_seed_and_plan_is_deterministic(cfg: Config) -> None:
    state = make_state(inventory=make_inventory(**STOCK))
    assert simulate_day(state, make_plan(), cfg) == simulate_day(state, make_plan(), cfg)
