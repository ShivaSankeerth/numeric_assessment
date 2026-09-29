import pytest

from factories import fixed_rng, make_inventory
from lemonade.engine.config import Config
from lemonade.engine.demand import DemandBreakdown
from lemonade.engine.models import Inventory, Recipe
from lemonade.engine.sales import sell
from lemonade.engine.types import Item, LossReason, StopReason

PLENTY = {"lemon": 600, "sugar": 400, "ice": 3000, "cup": 1000}


def demand(buy_prob: float, pf: float = 1.0, taste: float = 1.0) -> DemandBreakdown:
    return DemandBreakdown(100, 50.0, pf, taste, (), buy_prob)


def run(cfg: Config, inv: Inventory, buy_prob: float = 1.0, customers: int = 100):  # type: ignore[no-untyped-def]
    return sell(customers, demand(buy_prob), inv, Recipe(6, 4, 3), cfg, fixed_rng())


def test_everyone_buys_with_plenty_of_stock(cfg: Config) -> None:
    out = run(cfg, make_inventory(**PLENTY))
    assert out.cups_sold == 100
    assert out.stop_reason is None
    # 100 cups = 9 pitchers (the 9th only partly sold; leftovers are discarded)
    assert out.consumed == {Item.LEMON: 54, Item.SUGAR: 36, Item.ICE: 300, Item.CUP: 100}
    assert out.inventory.count(Item.CUP) == 900


def test_nobody_buys(cfg: Config) -> None:
    out = run(cfg, make_inventory(**PLENTY), buy_prob=0.0)
    assert out.cups_sold == 0
    assert out.lost_sales[LossReason.NOT_INTERESTED] == 100
    assert out.consumed == {item: 0 for item in Item}


@pytest.mark.parametrize(
    ("limit", "stop", "sold"),
    [
        ({"cup": 7}, StopReason.SOLD_OUT_CUPS, 7),
        ({"ice": 30}, StopReason.SOLD_OUT_ICE, 10),
        ({"lemon": 12}, StopReason.SOLD_OUT_LEMONS, 24),
        ({"sugar": 4}, StopReason.SOLD_OUT_SUGAR, 12),
    ],
)
def test_selling_out_mid_day_sets_stop_reason(
    cfg: Config, limit: dict[str, int], stop: StopReason, sold: int
) -> None:
    out = run(cfg, make_inventory(**{**PLENTY, **limit}))
    assert out.stop_reason is stop
    assert out.cups_sold == sold
    assert out.lost_sales[LossReason.SOLD_OUT] == 100 - sold


def test_every_customer_is_accounted_for(cfg: Config) -> None:
    out = run(cfg, make_inventory(cup=20, **{k: v for k, v in PLENTY.items() if k != "cup"}), 0.5)
    assert out.cups_sold + sum(out.lost_sales.values()) == 100


def test_input_inventory_untouched(cfg: Config) -> None:
    inv = make_inventory(**PLENTY)
    run(cfg, inv)
    assert inv.count(Item.CUP) == 1000
