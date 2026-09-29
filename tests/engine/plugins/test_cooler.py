from factories import make_ctx
from lemonade.engine.config import Config
from lemonade.engine.registry import UPGRADE_HANDLERS


def test_cooler_retains_half_the_ice(cfg: Config) -> None:
    cooler = UPGRADE_HANDLERS["cooler"]
    assert cooler.ice_retention(cfg) == 0.5
    assert cooler.lemon_yield_bonus(cfg) == 0.0
    assert cooler.effects(make_ctx()) == []
