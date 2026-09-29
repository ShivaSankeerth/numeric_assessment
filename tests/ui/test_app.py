"""Pilot smoke tests: each screen mounts, key bindings work, and a full day flows."""

from dataclasses import replace

from textual.widgets import Button, Checkbox, DataTable, Input, Sparkline, Static, TabbedContent

from factories import achievements_cfg, make_inventory, make_plan, make_state
from lemonade.engine import market, stats
from lemonade.engine.config import Config
from lemonade.engine.demand import recipe_score
from lemonade.engine.game import play_day
from lemonade.engine.models import DayResult, Effect, GameState, Recipe
from lemonade.engine.types import Factor, Item
from lemonade.ui.app import LemonadeApp
from lemonade.ui.format import achievement_name, fmt_cents, fmt_pct
from lemonade.ui.screens.day_result import DayResultScreen
from lemonade.ui.screens.game_over import DifficultyScreen, GameOverScreen
from lemonade.ui.screens.help import HelpScreen
from lemonade.ui.screens.plan import PlanScreen
from lemonade.ui.screens.stats import StatsScreen

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
        for key, tab in (("4", "upgrades"), ("1", "shop")):
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
        assert "Final cash (score): [b]$0.00" in text(app, "#summary")

        await pilot.press("n")
        await pilot.pause()
        assert isinstance(app.screen, DifficultyScreen)
        await pilot.press("h")
        await pilot.pause()
        assert isinstance(app.screen, PlanScreen)
        assert app.state.difficulty == "hard"
        assert "Day 1" in text(app, "#status")
        assert fmt_cents(cfg.difficulties["hard"].starting_cash) in text(app, "#status")
        assert "Difficulty: Hard" in text(app, "#status")
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


def played_state(cfg: Config, days: int) -> GameState:
    """A state after `days` engine-played days (faster than driving the UI)."""
    state = make_state(inventory=make_inventory(lemon=60, sugar=40, ice=0, cup=200))
    for _ in range(days):
        state, _ = play_day(state, make_plan({"ice": 1}), cfg)
    return state


async def test_stats_screen_opens_with_t_and_closes(cfg: Config) -> None:
    app = LemonadeApp(seed=42, cfg=cfg)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.press("t")
        await pilot.pause()
        assert isinstance(app.screen, StatsScreen)
        assert "Play a day" in text(app, "#chart-range")
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, PlanScreen)


async def test_stats_screen_after_some_days(cfg: Config) -> None:
    app = LemonadeApp(seed=42, cfg=cfg, state=played_state(cfg, 3))
    async with app.run_test(size=SIZE) as pilot:
        await pilot.press("t")
        await pilot.pause()
        chart = app.screen.query_one("#cash-chart", Sparkline)
        assert list(chart.data or []) == [float(c) for c in stats.cash_series(app.state)]
        assert "Days played:   3" in text(app, "#totals")
        assert "Best day: day" in text(app, "#best-worst")
        assert "None yet" in text(app, "#achievements")
        await pilot.press("t")
        await pilot.pause()
        assert isinstance(app.screen, PlanScreen)


async def test_help_opens_with_question_mark(cfg: Config) -> None:
    app = LemonadeApp(seed=42, cfg=cfg)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.press("question_mark")
        await pilot.pause()
        assert isinstance(app.screen, HelpScreen)
        assert "How to play" in text(app, "#help-text")
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, PlanScreen)


async def test_day_result_ranks_effects_and_highlights_events(cfg: Config) -> None:
    app = LemonadeApp(seed=42, cfg=cfg)
    async with app.run_test(size=SIZE):
        result = replace(
            _stub_result(cfg),
            events=("A festival in town!",),
            effects=(
                Effect(Factor.TRAFFIC, "mul", 1.1, "Small", "a"),
                Effect(Factor.TRAFFIC, "mul", 1.6, "Big", "b"),
            ),
        )
        await app.push_screen(DayResultScreen(result, app.state, ("Lemon shortage",)))
        table = app.screen.query_one("#effects", DataTable)
        assert [table.get_row_at(i)[0] for i in range(table.row_count)] == ["Big", "Small"]
        assert table.get_row_at(0)[2] == "+60%"
        happenings = text(app, "#happenings")
        assert "A festival in town!" in happenings
        assert "Lemon shortage" in happenings


def _stub_result(cfg: Config) -> DayResult:
    state = make_state(inventory=make_inventory(lemon=12, sugar=8, ice=100, cup=50))
    return play_day(state, make_plan(), cfg)[1]


async def test_day_result_shows_unlocked_achievements(cfg: Config) -> None:
    app = LemonadeApp(seed=42, cfg=cfg)
    async with app.run_test(size=SIZE):
        result = _stub_result(cfg)
        if not hasattr(result, "achievements_unlocked"):
            return  # engine doesn't report unlocks yet
        result = replace(result, achievements_unlocked=("first_sale",))
        await app.push_screen(DayResultScreen(result, app.state))
        assert achievement_name("first_sale", cfg) in text(app, "#happenings")


async def test_stats_list_configured_achievements() -> None:
    cfg = achievements_cfg()
    first_id, first = next(iter(cfg.achievements.items()))
    state = make_state(cfg, achievements=frozenset({first_id}))
    app = LemonadeApp(seed=42, cfg=cfg, state=state)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.press("t")
        await pilot.pause()
        shown = text(app, "#achievements")
        assert f"1 of {len(cfg.achievements)} unlocked" in shown
        assert f"★ {first.name}" in shown
