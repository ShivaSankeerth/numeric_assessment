"""Day result: money, sales, why sales were what they were, and what happened."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Static

from lemonade.engine.models import DayResult, GameState
from lemonade.ui.format import fmt_cents, fmt_pct

if TYPE_CHECKING:
    from lemonade.ui.app import LemonadeApp


def _effect_impact(op: str, value: float) -> str:
    return f"x{value:.2f}" if op == "mul" else f"{value:+.2f}"


def summary_text(r: DayResult) -> str:
    stop = r.stop_reason.value.replace("_", " ") if r.stop_reason else "served everyone"
    lost = ", ".join(
        f"{reason.value.replace('_', ' ')}: {n}" for reason, n in r.lost_sales.items() if n
    )
    spoiled = ", ".join(f"{item.value} {n}" for item, n in r.spoiled.items()) or "nothing"
    lines = [
        f"Weather: {r.weather.value.capitalize()}, {r.temp_f}°F",
        f"Revenue: {fmt_cents(r.revenue)}   Spend: {fmt_cents(r.spend)}   "
        f"Profit: {fmt_cents(r.profit)}",
        f"Cups sold: {r.cups_sold} of {r.potential_customers} passers-by   ({stop})",
        f"Buy chance: {fmt_pct(r.buy_prob)}   Taste: {fmt_pct(r.taste_score)}",
        f"Lost sales: {lost or 'none'}",
        f"Ice melted: {r.ice_melted}   Spoiled: {spoiled}",
    ]
    if r.events:
        lines.append("Events: " + " ".join(r.events))
    if r.feedback:
        lines.append("Customers said: " + " ".join(f'"{f}"' for f in r.feedback))
    return "\n".join(lines)


class DayResultScreen(Screen[None]):
    BINDINGS = [Binding("enter", "continue", "Next day", priority=True)]

    def __init__(self, result: DayResult, state: GameState) -> None:
        super().__init__()
        self.result = result
        self.state = state

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll():
            yield Static(f"Day {self.result.day} results", classes="headline")
            yield Static(summary_text(self.result), id="summary", classes="panel")
            yield Static("Why? Effects on today's demand", classes="panel-title")
            yield DataTable(id="effects", cursor_type="none", zebra_stripes=True)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#effects", DataTable)
        table.add_columns("Reason", "Factor", "Impact")
        for e in self.result.effects:
            table.add_row(e.reason, e.factor.value.replace("_", " "), _effect_impact(e.op, e.value))

    def action_continue(self) -> None:
        cast("LemonadeApp", self.app).finish_day()
