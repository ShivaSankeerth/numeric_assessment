"""Juicer: more juice per lemon, so pitchers need fewer lemons (`recipes.effective_recipe`)."""

from lemonade.engine.config import Config
from lemonade.engine.registry import BaseUpgrade, register_upgrade


@register_upgrade
class Juicer(BaseUpgrade):
    id = "juicer"

    def lemon_yield_bonus(self, cfg: Config) -> float:
        return cfg.upgrades[self.id].params["lemon_yield_bonus"]
