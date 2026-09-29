"""Plan screen (main hub): status, stock, forecast, purchases, recipe and price."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Static

from lemonade.engine.game import preview_plan
from lemonade.engine.models import DayPlan, Purchase, Recipe
from lemonade.engine.types import Item
from lemonade.ui.format import fmt_cents, fmt_pct, parse_cents

if TYPE_CHECKING:
    from lemonade.ui.app import LemonadeApp

RECIPE_FIELDS = (
    ("lemons_per_pitcher", "Lemons / pitcher"),
    ("sugar_per_pitcher", "Sugar / pitcher"),
    ("ice_per_cup", "Ice cubes / cup"),
)


def _field(label: str, input_id: str, value: str, input_type: str = "integer") -> Horizontal:
    return Horizontal(
        Label(label), Input(value=value, id=input_id, type=input_type), classes="field"
    )


class PlanScreen(Screen[None]):
    BINDINGS = [("enter", "start_day", "Start day")]
    # Start on the button so enter/q work immediately; tab or click into inputs to edit.
    AUTO_FOCUS = "#start"

    @property
    def lemonade(self) -> LemonadeApp:
        return cast("LemonadeApp", self.app)

    def _pack_label(self, item: Item) -> str:
        item_cfg = self.lemonade.cfg.items[item]
        name = item.value.capitalize()
        return f"{name} ({item_cfg.pack_size} @ {fmt_cents(item_cfg.pack_price)})"

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="plan-body"):
            with Vertical(id="left"):
                yield Static(id="status", classes="panel")
                yield Static(id="inventory", classes="panel")
                yield Static(id="forecast", classes="panel")
            with Vertical(id="right"):
                yield Label("Buy packs", classes="panel-title")
                for item in Item:
                    yield _field(self._pack_label(item), f"buy-{item.value}", "0")
                yield Label("Recipe", classes="panel-title")
                defaults = Recipe()
                for name, label in RECIPE_FIELDS:
                    yield _field(label, f"recipe-{name}", str(getattr(defaults, name)))
                yield Label("Price", classes="panel-title")
                yield _field("Price per cup ($)", "price", "0.50", "text")
                yield Static(id="cart")
                yield Button("Start day  (enter)", id="start")
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_view()

    def on_screen_resume(self) -> None:
        for item in Item:
            self.query_one(f"#buy-{item.value}", Input).value = "0"
        self.query_one("#start", Button).focus()
        self.refresh_view()

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
        return DayPlan(purchases=tuple(purchases), recipe=recipe, price_per_cup=price)

    def refresh_view(self) -> None:
        state = self.lemonade.state
        self.query_one("#status", Static).update(
            f"[b]Day {state.day}[/b]\nCash: {fmt_cents(state.cash)}\n"
            f"Reputation: {fmt_pct(state.reputation)}"
        )
        stock = "\n".join(
            f"{item.value.capitalize():<6} {state.inventory.count(item):>5}" for item in Item
        )
        self.query_one("#inventory", Static).update(f"[b]Inventory[/b]\n{stock}")
        fc = state.forecast
        self.query_one("#forecast", Static).update(
            f"[b]Forecast[/b]\n{fc.predicted.value.capitalize()}, {fc.predicted_temp_f}°F"
        )
        self.refresh_cart()

    def refresh_cart(self) -> None:
        try:
            plan = self.build_plan()
        except ValueError:
            self.query_one("#cart", Static).update("Check your inputs")
            return
        preview = preview_plan(self.lemonade.state, plan, self.lemonade.cfg)
        self.query_one("#cart", Static).update(
            f"Cart: {fmt_cents(preview.cost)}   Cash after: {fmt_cents(preview.cash_after)}   "
            f"Cups makeable: {preview.cups_makeable}"
        )

    def on_input_changed(self, _: Input.Changed) -> None:
        self.refresh_cart()

    def on_input_submitted(self, _: Input.Submitted) -> None:
        self.action_start_day()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "start":
            self.action_start_day()

    def action_start_day(self) -> None:
        try:
            plan = self.build_plan()
        except ValueError as err:
            self.notify(str(err), title="Invalid input", severity="error")
            return
        self.lemonade.start_day(plan)
