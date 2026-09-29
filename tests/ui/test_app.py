"""Pilot smoke tests: each screen mounts, key bindings work, and a full day flows."""

from textual.widgets import Button, Checkbox, Input, Static, TabbedContent

from factories import make_state
from lemonade.engine import market
from lemonade.engine.config import Config
from lemonade.engine.demand import recipe_score
from lemonade.engine.models import Recipe
from lemonade.engine.types import Item
from lemonade.ui.app import LemonadeApp
from lemonade.ui.format import fmt_cents, fmt_pct
from lemonade.ui.screens.day_result import DayResultScreen
from lemonade.ui.screens.game_over import GameOverScreen
from lemonade.ui.screens.plan import PlanScreen

SIZE = (120, 50)


def text(app: LemonadeApp, selector: str) -> str:
    return str(app.screen.query_one(selector, Static).content)


def set_input(app: LemonadeApp, selector: str, value: str) -> None:
    app.screen.query_one(selector, Input).value = value


async def test_plan_screen_mounts(cfg: Config) -> None:
    app = LemonadeApp(seed=42, cfg=cfg)
    async with app.run_test(size=SIZE):
        assert isinstance(app.screen, PlanScreen)
        assert "Day 1" in text(app, "#status")
        assert "$20.00" in text(app, "#status")
        assert "Cups makeable: 0" in text(app, "#cart")


async def test_cart_preview_updates_live(cfg: Config) -> None:
    app = LemonadeApp(seed=42, cfg=cfg)
    async with app.run_test(size=SIZE) as pilot:
        for item in ("lemon", "sugar", "ice", "cup"):
            set_input(app, f"#buy-{item}", "1")
        await pilot.pause()
        assert "Cart: $11.00" in text(app, "#cart")
        assert "Cups makeable: 24" in text(app, "#cart")


async def test_tabs_switch_with_number_keys(cfg: Config) -> None:
    app = LemonadeApp(seed=42, cfg=cfg)
    async with app.run_test(size=SIZE) as pilot:
        tabs = app.screen.query_one("#tabs", TabbedContent)
        assert tabs.active == "tab-shop"
        for key, tab in (("2", "recipe"), ("3", "price"), ("4", "upgrades"), ("1", "shop")):
            await pilot.press(key)
            await pilot.pause()
            assert tabs.active == f"tab-{tab}"


async def test_shop_shows_todays_prices_and_bulk_discount(cfg: Config) -> None:
    app = LemonadeApp(seed=42, cfg=cfg)
    async with app.run_test(size=SIZE) as pilot:
        prices = market.todays_pack_prices(app.state, cfg)
        assert text(app, "#price-lemon") == fmt_cents(prices[Item.LEMON])
        set_input(app, "#buy-lemon", "3")
        await pilot.pause()
        cost = market.purchase_cost(Item.LEMON, 3, prices[Item.LEMON], cfg)
        assert fmt_cents(cost) in text(app, "#line-lemon")
        assert "-10%" in text(app, "#line-lemon")
        assert f"Cart total: [b]{fmt_cents(cost)}" in text(app, "#shop-total")


async def test_start_button_disabled_when_overspending(cfg: Config) -> None:
    app = LemonadeApp(seed=42, cfg=cfg)
    async with app.run_test(size=SIZE) as pilot:
        start = app.screen.query_one("#start", Button)
        assert not start.disabled
        set_input(app, "#buy-lemon", "9")
        await pilot.pause()
        assert start.disabled
        set_input(app, "#buy-lemon", "1")
        await pilot.pause()
        assert not start.disabled


async def test_recipe_tab_shows_taste_hint(cfg: Config) -> None:
    app = LemonadeApp(seed=42, cfg=cfg)
    async with app.run_test(size=SIZE) as pilot:
        set_input(app, "#recipe-sugar_per_pitcher", "0")
        await pilot.pause()
        temp = app.state.forecast.predicted_temp_f
        score, notes = recipe_score(Recipe(sugar_per_pitcher=0), temp, cfg)
        assert fmt_pct(score) in text(app, "#taste")
        assert "Too sour!" in notes
        assert "Too sour!" in text(app, "#taste")


async def test_upgrade_checkbox_buys_the_upgrade(cfg: Config) -> None:
    up_id, up = next(iter(cfg.upgrades.items()))
    app = LemonadeApp(seed=42, cfg=cfg, state=make_state(cash=up.cost + 2000))
    async with app.run_test(size=SIZE) as pilot:
        app.screen.query_one(f"#upgrade-{up_id}", Checkbox).value = True
        await pilot.pause()
        assert f"Cart: {fmt_cents(up.cost)}" in text(app, "#cart")
        await pilot.press("enter")
        await pilot.pause()
        assert up_id in app.state.upgrades
        await pilot.press("enter")  # back to planning: now owned and disabled
        await pilot.pause()
        box = app.screen.query_one(f"#upgrade-{up_id}", Checkbox)
        assert box.disabled
        assert not box.value
        assert "(owned)" in str(box.label)


async def test_overspending_notifies_and_stays_on_plan(cfg: Config) -> None:
    app = LemonadeApp(seed=42, cfg=cfg)
    async with app.run_test(size=SIZE) as pilot:
        set_input(app, "#buy-lemon", "9")
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, PlanScreen)
        assert any("only have $20.00" in n.message for n in app._notifications)
        assert app.state.day == 1


async def test_bad_price_input_notifies(cfg: Config) -> None:
    app = LemonadeApp(seed=42, cfg=cfg)
    async with app.run_test(size=SIZE) as pilot:
        set_input(app, "#price", "lots")
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, PlanScreen)
        assert any(n.title == "Invalid input" for n in app._notifications)


async def test_full_day_flow(cfg: Config) -> None:
    app = LemonadeApp(seed=42, cfg=cfg)
    async with app.run_test(size=SIZE) as pilot:
        for item in ("lemon", "sugar", "ice", "cup"):
            set_input(app, f"#buy-{item}", "1")
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, DayResultScreen)
        assert "Revenue:" in text(app, "#summary")
        assert app.screen.query_one("#effects").row_count >= 1

        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, PlanScreen)
        assert "Day 2" in text(app, "#status")
        assert app.screen.query_one("#buy-lemon", Input).value == "0"


async def test_bankruptcy_shows_game_over_and_n_restarts(cfg: Config) -> None:
    app = LemonadeApp(seed=42, cfg=cfg, state=make_state(cash=0))
    async with app.run_test(size=SIZE) as pilot:
        await pilot.press("enter")  # nothing to buy, nothing to sell -> bankrupt
        await pilot.pause()
        assert isinstance(app.screen, DayResultScreen)
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, GameOverScreen)
        assert "bankrupt after 1 day" in text(app, "#summary")

        await pilot.press("n")
        await pilot.pause()
        assert isinstance(app.screen, PlanScreen)
        assert "Day 1" in text(app, "#status")
        assert "$20.00" in text(app, "#status")
        assert app.seed == 43


async def test_enter_in_an_input_starts_the_day(cfg: Config) -> None:
    app = LemonadeApp(seed=42, cfg=cfg)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.press("3")  # Price tab
        await pilot.pause()
        await pilot.click("#price")
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, DayResultScreen)


async def test_q_quits(cfg: Config) -> None:
    app = LemonadeApp(seed=42, cfg=cfg)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.press("q")
        await pilot.pause()
    assert app.return_code == 0
