"""Recipe adjustments from owned upgrades (the recipe the stand actually uses)."""

from __future__ import annotations

import math
from dataclasses import replace

from lemonade.engine.config import Config
from lemonade.engine.models import GameState, Recipe
from lemonade.engine.registry import active_upgrades

# Guards float noise like 5 / 1.25 = 4.000000000000001 before ceil.
_ROUND_DIGITS = 9


def lemon_yield_bonus(state: GameState, cfg: Config) -> float:
    """Total extra juice per lemon from owned upgrades (0.25 = +25%)."""
    return sum(h.lemon_yield_bonus(cfg) for h in active_upgrades(state))


def effective_recipe(state: GameState, recipe: Recipe, cfg: Config) -> Recipe:
    """The recipe as consumed from stock: lemons per pitcher / (1 + yield bonus), ceil, min 1.

    Taste is still judged on the player's recipe (the juicer makes the same lemonade from fewer
    lemons). Use the state AFTER purchases so an upgrade bought today applies today.
    """
    bonus = lemon_yield_bonus(state, cfg)
    if bonus <= 0:
        return recipe
    lemons = math.ceil(round(recipe.lemons_per_pitcher / (1 + bonus), _ROUND_DIGITS))
    return replace(recipe, lemons_per_pitcher=max(1, lemons))
