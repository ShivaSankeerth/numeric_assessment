"""Pilot smoke tests: each screen mounts, key bindings work, and a full day flows."""

from textual.widgets import Input, Static

from factories import make_state
from lemonade.engine.config import Config
from lemonade.ui.app import LemonadeApp
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
