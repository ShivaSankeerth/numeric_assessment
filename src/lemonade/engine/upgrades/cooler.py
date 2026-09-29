"""Cooler: keeps part of the leftover ice from melting overnight."""

from lemonade.engine.config import Config
from lemonade.engine.registry import BaseUpgrade, register_upgrade


@register_upgrade
class Cooler(BaseUpgrade):
    id = "cooler"

    def ice_retention(self, cfg: Config) -> float:
        return cfg.upgrades[self.id].params["ice_retention"]
