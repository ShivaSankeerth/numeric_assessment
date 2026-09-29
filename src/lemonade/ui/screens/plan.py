"""Plan screen (main hub): status, stock and forecast on the left; Shop / Recipe / Price /
Upgrades tabs on the right; live cart line at the bottom."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import (
    Button,
    Checkbox,
    Footer,
    Header,
    Input,
    Label,
    Static,
    TabbedContent,
    TabPane,
)

from lemonade.engine import dates, market
from lemonade.engine.demand import recipe_score
from lemonade.engine.game import preview_plan
from lemonade.engine.models import DayPlan, Purchase, Recipe
from lemonade.engine.types import Item
from lemonade.ui.format import fmt_cents, fmt_pct, parse_cents
from lemonade.ui.screens.game_over import difficulty_name

if TYPE_CHECKING:
    from lemonade.engine.config import Config
    from lemonade.ui.app import LemonadeApp

RECIPE_FIELDS = (
    ("lemons_per_pitcher", "Lemons / pitcher"),
    ("sugar_per_pitcher", "Sugar / pitcher"),
    ("ice_per_cup", "Ice cubes / cup"),
)
ITEM_UNITS = {Item.LEMON: "lemons", Item.SUGAR: "cups", Item.ICE: "cubes", Item.CUP: "cups"}
TABS = ("shop", "recipe", "price", "upgrades")
SHOP_COLUMNS = (
    ("Item", "c-item"),
    ("Packs", "c-packs"),
    ("Price/pack", "c-price"),
    ("Line", "c-line"),
    ("Bulk", "c-tier"),
)


def _field(label: str, input_id: str, value: str, input_type: str = "integer") -> Horizontal:
    return Horizontal(
        Label(label, classes="field-label"),
        Input(value=value, id=input_id, type=input_type, compact=True),
        classes="field",
    )


def tier_hint(item: Item, cfg: Config) -> str:
    """Bulk tiers from content, e.g. '3+:-10% 6+:-20%' (display only)."""
    tiers = cfg.items[item].tiers
    if not tiers:
        return "—"
    return " ".join(f"{t.min_packs}+:-{t.discount_pct}%" for t in tiers)


def upgrade_label(up_id: str, cfg: Config, owned: bool) -> str:
    up = cfg.upgrades[up_id]
    suffix = "  (owned)" if owned else ""
    return f"{up.name} — {fmt_cents(up.cost)}{suffix}"


class PlanScreen(Screen[None]):
    BINDINGS = [
        Binding("enter", "start_day", "Start day"),
        Binding("t", "stats", "Stats"),
        Binding("question_mark", "help", "Help"),
        *(
            Binding(str(i), f"tab('{tab}')", tab.capitalize(), show=False)
            for i, tab in enumerate(TABS, 1)
        ),
    ]
    # Start on the button so enter/q/t/? work immediately: Textual 8 never fires a letter binding
    # while an Input has focus. Tab or click into inputs to edit; enter in an input still
    # starts the day (Input.Submitted).
    AUTO_FOCUS = "#start"

    @property
    def lemonade(self) -> LemonadeApp:
        return cast("LemonadeApp", self.app)

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="plan-body"):
            with Vertical(id="left"):
                yield Static(id="status", classes="panel")
                yield Static(id="inventory", classes="panel")
                yield Static(id="forecast", classes="panel")
            with TabbedContent(id="tabs"):
                with TabPane("Shop", id="tab-shop"), VerticalScroll():
                    yield from self._compose_shop()
                with TabPane("Recipe", id="tab-recipe"), VerticalScroll():
                    defaults = Recipe()
                    for name, label in RECIPE_FIELDS:
                        yield _field(label, f"recipe-{name}", str(getattr(defaults, name)))
                    yield Static(id="taste", classes="hint")
                with TabPane("Price", id="tab-price"), VerticalScroll():
                    yield _field("Price per cup ($)", "price", "0.50", "text")
                    yield Static(self._price_hint(), classes="hint")
                with TabPane("Upgrades", id="tab-upgrades"), VerticalScroll():
                    yield from self._compose_upgrades()
        with Horizontal(id="cart-bar"):
            yield Static(id="cart")
            yield Button("Start day ⏎", id="start")
        yield Footer()

    def _price_hint(self) -> str:
        fair = fmt_cents(self.lemonade.cfg.demand.base_fair_price)
        return (
            f"Customers think about {fair} is fair on an ordinary day; hot weather raises that.\n"
            "Charge much more and they walk away; charge less and more of them buy."
        )

    def _compose_shop(self) -> ComposeResult:
        cfg = self.lemonade.cfg
        with Horizontal(classes="shop-row shop-head"):
            for text, cls in SHOP_COLUMNS:
                yield Label(text, classes=cls)
        for item in Item:
            with Horizontal(classes="shop-row"):
                size = cfg.items[item].pack_size
                name = f"{item.value.capitalize()} x{size} {ITEM_UNITS[item]}"
                yield Label(name, classes="c-item")
                yield Input(
                    value="0",
                    id=f"buy-{item.value}",
                    type="integer",
                    compact=True,
                    classes="c-packs",
                )
                yield Static(id=f"price-{item.value}", classes="c-price")
                yield Static(id=f"line-{item.value}", classes="c-line")
                yield Static(tier_hint(item, cfg), classes="c-tier")
        yield Static(id="market-notes", classes="hint")
        yield Static(id="shop-total", classes="total")

    def _compose_upgrades(self) -> ComposeResult:
        cfg = self.lemonade.cfg
        if not cfg.upgrades:
            yield Static("No upgrades available.", classes="hint")
        for up_id, up in cfg.upgrades.items():
            owned = up_id in self.lemonade.state.upgrades
            yield Checkbox(
                upgrade_label(up_id, cfg, owned),
                value=False,
                id=f"upgrade-{up_id}",
                disabled=owned,
                compact=True,
            )
            yield Static(up.description, classes="upgrade-desc")

    def on_mount(self) -> None:
        self.refresh_view()

    def on_screen_resume(self) -> None:
        for item in Item:
            self.query_one(f"#buy-{item.value}", Input).value = "0"
        cfg, state = self.lemonade.cfg, self.lemonade.state
        for up_id in cfg.upgrades:
            box = self.query_one(f"#upgrade-{up_id}", Checkbox)
            owned = up_id in state.upgrades
            box.value = False
            box.disabled = owned
            box.label = upgrade_label(up_id, cfg, owned)
        self.refresh_view()
        self.query_one("#start", Button).focus()

    def build_plan(self) -> DayPlan:
        """Read the inputs into a DayPlan. Raises ValueError on unparseable input."""
        purchases = []
        for item in Item:
            packs = int(self.query_one(f"#buy-{item.value}", Input).value or "0")
            if packs:
                purchases.append(Purchase(item, packs))
        recipe = Recipe(
            **{
                name: int(self.query_one(f"#recipe-{name}", Input).value or "0")
                for name, _ in RECIPE_FIELDS
            }
        )
        price = parse_cents(self.query_one("#price", Input).value)
        upgrades = tuple(
            up_id
            for up_id in self.lemonade.cfg.upgrades
            if self.query_one(f"#upgrade-{up_id}", Checkbox).value
        )
        return DayPlan(
            purchases=tuple(purchases),
            recipe=recipe,
            price_per_cup=price,
            upgrade_purchases=upgrades,
        )

    def refresh_view(self) -> None:
        state, cfg = self.lemonade.state, self.lemonade.cfg
        level = difficulty_name(state, cfg)
        self.query_one("#status", Static).update(
            f"[b]Day {state.day}[/b] · {dates.day_name(state.day, cfg)}\n"
            f"Cash: [b]{fmt_cents(state.cash)}[/b]\n"
            f"Reputation: {fmt_pct(state.reputation)}"
            + (f"\nDifficulty: {level}" if state.difficulty != "normal" else "")
        )
        stock = "\n".join(
            f"{item.value.capitalize():<6} {state.inventory.count(item):>5}" for item in Item
        )
        self.query_one("#inventory", Static).update(f"[b]Inventory[/b]\n{stock}")
        fc = state.forecast
        self.query_one("#forecast", Static).update(
            f"[b]Forecast[/b]\n{fc.predicted.value.capitalize()}, {fc.predicted_temp_f}°F"
            + self._calendar_note()
        )
        prices = market.todays_pack_prices(state, cfg)
        for item in Item:
            self.query_one(f"#price-{item.value}", Static).update(fmt_cents(prices[item]))
        notes = market.market_notes(state, cfg)
        self.query_one("#market-notes", Static).update(
            "\n".join(f"• {n}" for n in notes) if notes else "Market: normal prices today."
        )
        self.refresh_cart()

    def _calendar_note(self) -> str:
        day, cfg = self.lemonade.state.day, self.lemonade.cfg
        holiday = dates.holiday_name(day, cfg)
        if holiday:
            return f"\n[b #f5d547]{holiday}![/]"
        return "\nWeekend crowds" if dates.is_weekend(day, cfg) else ""

    def _refresh_lines(self) -> None:
        state, cfg = self.lemonade.state, self.lemonade.cfg
        prices = market.todays_pack_prices(state, cfg)
        for item in Item:
            line = self.query_one(f"#line-{item.value}", Static)
            try:
                packs = int(self.query_one(f"#buy-{item.value}", Input).value or "0")
            except ValueError:
                packs = 0
            if packs <= 0:
                line.update("—")
                continue
            cost = market.purchase_cost(item, packs, prices[item], cfg)
            pct = market.discount_pct(item, packs, cfg)
            line.update(fmt_cents(cost) + (f" [green]-{pct}%[/green]" if pct else ""))

    def _refresh_taste(self, plan: DayPlan) -> None:
        temp = self.lemonade.state.forecast.predicted_temp_f
        score, notes = recipe_score(plan.recipe, temp, self.lemonade.cfg)
        said = "  ".join(f'"{n}"' for n in notes) or "No complaints expected."
        self.query_one("#taste", Static).update(
            f"Taste at the forecast {temp}°F: [b]{fmt_pct(score)}[/b]\n{said}"
        )

    def refresh_cart(self) -> None:
        self._refresh_lines()
        cart = self.query_one("#cart", Static)
        start = self.query_one("#start", Button)
        try:
            plan = self.build_plan()
        except ValueError:
            cart.update("[red]Check your inputs[/red]")
            self.query_one("#taste", Static).update("")
            start.disabled = False  # start_day explains what's wrong
            return
        preview = preview_plan(self.lemonade.state, plan, self.lemonade.cfg)
        self._refresh_taste(plan)
        over = preview.cash_after < 0
        after = fmt_cents(preview.cash_after)
        cart.update(
            f"Cart: {fmt_cents(preview.cost)}   "
            f"Cash after: {f'[red]{after}[/red]' if over else after}   "
            f"Cups makeable: {preview.cups_makeable}"
        )
        self.query_one("#shop-total", Static).update(
            f"Cart total: [b]{fmt_cents(preview.cost)}[/b]"
            + ("   [red]more than you have![/red]" if over else "")
        )
        start.disabled = over

    def on_input_changed(self, _: Input.Changed) -> None:
        self.refresh_cart()

    def on_checkbox_changed(self, _: Checkbox.Changed) -> None:
        self.refresh_cart()

    def on_input_submitted(self, _: Input.Submitted) -> None:
        self.action_start_day()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "start":
            self.action_start_day()

    def action_tab(self, tab: str) -> None:
        self.query_one("#tabs", TabbedContent).active = f"tab-{tab}"

    def action_stats(self) -> None:
        self.lemonade.show_stats()

    def action_help(self) -> None:
        self.lemonade.show_help()

    def action_start_day(self) -> None:
        try:
            plan = self.build_plan()
        except ValueError as err:
            self.notify(str(err), title="Invalid input", severity="error")
            return
        self.lemonade.start_day(plan)
