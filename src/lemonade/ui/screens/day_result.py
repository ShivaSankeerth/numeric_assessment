"""Day result: money, sales, why sales were what they were, and what happened."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Static

from lemonade.engine.config import Config
from lemonade.engine.demand import fmt_mul
from lemonade.engine.models import DayResult, Effect, GameState
from lemonade.engine.stats import ranked_effects
from lemonade.ui.format import achievement_name, fmt_cents, fmt_pct

if TYPE_CHECKING:
    from lemonade.ui.app import LemonadeApp


def effect_impact(e: Effect) -> str:
    """'+40%' for multipliers, '+0.10' for additive effects."""
    return fmt_mul(e.value) if e.op == "mul" else f"{e.value:+.2f}"


def _profit(cents: int) -> str:
    color = "green" if cents > 0 else "red" if cents < 0 else "white"
    return f"[{color}]{fmt_cents(cents)}[/{color}]"


def summary_text(r: DayResult) -> str:
    stop = r.stop_reason.value.replace("_", " ") if r.stop_reason else "served everyone"
    lost = ", ".join(
        f"{reason.value.replace('_', ' ')}: {n}" for reason, n in r.lost_sales.items() if n
    )
    spoiled = ", ".join(f"{item.value} {n}" for item, n in r.spoiled.items() if n) or "nothing"
    lines = [
        f"Weather: {r.weather.value.capitalize()}, {r.temp_f}°F",
        f"Revenue: {fmt_cents(r.revenue)}   Spend: {fmt_cents(r.spend)}   "
        f"Profit: {_profit(r.profit)}   Cash now: {fmt_cents(r.cash_end)}",
        f"Cups sold: {r.cups_sold} of {r.potential_customers} passers-by   ({stop})",
        f"Buy chance: {fmt_pct(r.buy_prob)}   Taste: {fmt_pct(r.taste_score)}   "
        f"Reputation: {r.reputation_delta:+.1%}",
        f"Lost sales: {lost or 'none'}",
        f"Ice melted: {r.ice_melted}   Spoiled: {spoiled}",
    ]
    if r.feedback:
        lines.append("Customers said: " + " ".join(f'"{f}"' for f in r.feedback))
    return "\n".join(lines)


def happenings_text(r: DayResult, market_notes: tuple[str, ...], cfg: Config) -> str:
    """Events, market notes and new achievements, highlighted; '' if nothing happened."""
    lines = [f"[b #f5d547]⚡ {e}[/]" for e in r.events]
    lines += [f"[b]$[/b] {n}" for n in market_notes]
    unlocked = getattr(r, "achievements_unlocked", ()) or ()
    lines += [f"[b green]★ Achievement: {achievement_name(a, cfg)}[/]" for a in unlocked]
    return "\n".join(lines)


class DayResultScreen(Screen[None]):
    BINDINGS = [Binding("enter", "continue", "Next day", priority=True)]

    def __init__(
        self, result: DayResult, state: GameState, market_notes: tuple[str, ...] = ()
    ) -> None:
        super().__init__()
        self.result = result
        self.state = state
        self.market_notes = market_notes

    def compose(self) -> ComposeResult:
        cfg = cast("LemonadeApp", self.app).cfg
        happened = happenings_text(self.result, self.market_notes, cfg)
        yield Header()
        with VerticalScroll():
            yield Static(f"Day {self.result.day} results", classes="headline")
            yield Static(summary_text(self.result), id="summary", classes="panel")
            if happened:
                yield Static(happened, id="happenings", classes="panel events")
            yield Static("Why? Effects on today's demand (strongest first)", classes="panel-title")
            yield DataTable(id="effects", cursor_type="none", zebra_stripes=True)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#effects", DataTable)
        table.add_columns("Reason", "Factor", "Impact")
        for e in ranked_effects(self.result):
            table.add_row(e.reason, e.factor.value.replace("_", " "), effect_impact(e))

    def action_continue(self) -> None:
        cast("LemonadeApp", self.app).finish_day()
