from factories import make_ctx, make_inventory, make_plan, make_state
from lemonade.engine.config import Config
from lemonade.engine.registry import UPGRADE_HANDLERS
from lemonade.engine.simulation import simulate_day
from lemonade.engine.types import Factor

sign = UPGRADE_HANDLERS["sign"]


def test_sign_boosts_traffic_every_day() -> None:
    (effect,) = sign.effects(make_ctx())
    assert (effect.factor, effect.op, effect.value) == (Factor.TRAFFIC, "mul", 1.15)
    assert effect.reason == "Sign: +15% foot traffic"
    assert effect.source == "sign"


def test_owned_sign_raises_potential_customers(cfg: Config) -> None:
    stock = make_inventory(lemon=60, sugar=40, ice=600, cup=200)
    _, without = simulate_day(make_state(inventory=stock), make_plan(), cfg)
    state = make_state(inventory=stock, upgrades=frozenset({"sign"}))
    _, with_sign = simulate_day(state, make_plan(), cfg)
    assert with_sign.potential_customers > without.potential_customers
    assert "sign" in {e.source for e in with_sign.effects}
