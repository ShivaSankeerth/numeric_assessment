"""Hypothesis strategies for day plans (within recipe/price limits, any purchase amounts)."""

from hypothesis import strategies as st

from factories import default_cfg
from lemonade.engine.models import DayPlan, Purchase, Recipe
from lemonade.engine.types import Item

_limits = default_cfg().game.recipe_limits
_price_low, _ = default_cfg().game.price_limits

any_recipe = st.builds(
    Recipe,
    lemons_per_pitcher=st.integers(*_limits.lemons),
    sugar_per_pitcher=st.integers(*_limits.sugar),
    ice_per_cup=st.integers(*_limits.ice),
)
sensible_recipe = st.builds(
    Recipe,
    lemons_per_pitcher=st.integers(3, 8),
    sugar_per_pitcher=st.integers(1, 6),
    ice_per_cup=st.integers(0, 5),
)
recipes = st.sampled_from([sensible_recipe] * 3 + [any_recipe]).flatmap(lambda r: r)

# Buying all four items is what makes a day actually sell, so bias strongly towards it;
# random subsets and empty carts still exercise partial stock and carried-over inventory.
# Kit sizes keep the cost (max $16.50) affordable from the $20 start.
_kit_packs = {Item.LEMON: (1, 2), Item.SUGAR: (1, 1), Item.ICE: (1, 2), Item.CUP: (1, 1)}
full_kit = st.tuples(*[st.integers(*_kit_packs[item]) for item in Item]).map(
    lambda packs: tuple(Purchase(item, n) for item, n in zip(Item, packs, strict=True))
)
random_cart = st.dictionaries(st.sampled_from(list(Item)), st.integers(1, 4), max_size=4).map(
    lambda d: tuple(Purchase(item, packs) for item, packs in d.items())
)
_carts = {"kit": full_kit, "random": random_cart, "empty": st.just(())}
purchases = st.sampled_from(["kit"] * 4 + ["random", "empty"]).flatmap(lambda k: _carts[k])

plans = st.builds(
    DayPlan,
    purchases=purchases,
    recipe=recipes,
    price_per_cup=st.one_of(st.integers(20, 80), st.integers(_price_low, 300)),
    upgrade_purchases=st.sampled_from([(), (), (), ("cooler",)]),
)

seeds = st.integers(0, 10_000)
plan_sequences = st.lists(plans, min_size=1, max_size=6)
