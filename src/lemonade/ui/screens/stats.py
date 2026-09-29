"""Stats: cash over time, best/worst day, totals and achievements."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Sparkline, Static

from lemonade.engine import stats
from lemonade.engine.config import Config
from lemonade.engine.models import DayResult, GameState
from lemonade.ui.format import achievement_name, fmt_cents, fmt_pct


def _day_line(label: str, r: DayResult | None) -> str:
    if r is None:
        return f"{label}: —"
    return (
        f"{label}: day {r.day}  {fmt_cents(r.profit)} profit  "
        f"({r.cups_sold} cups, {r.weather.value}, {r.temp_f}°F)"
    )


def totals_text(state: GameState) -> str:
    t = stats.totals(state)
    return "\n".join(
        (
            f"Days played:   {t.days}",
            f"Passers-by:    {t.customers}",
            f"Cups sold:     {t.cups_sold}   ({fmt_pct(stats.sell_through(state))} bought)",
            f"Revenue:       {fmt_cents(t.revenue)}",
            f"Spend:         {fmt_cents(t.spend)}",
            f"Profit:        {fmt_cents(t.profit)}",
        )
    )


def achievements_text(state: GameState, cfg: Config) -> str:
    """Every configured achievement (★ unlocked, ☆ locked); just the owned ones otherwise."""
    catalog = getattr(cfg, "achievements", None) or {}
    if catalog:
        n = len(state.achievements & set(catalog))
        lines = [f"{n} of {len(catalog)} unlocked"]
        for key, ach in catalog.items():
            owned = key in state.achievements
            desc = getattr(ach, "description", "")
            name = achievement_name(key, cfg)
            lines.append(f"[b]★ {name}[/b]" if owned else f"[dim]☆ {name} — {desc}[/dim]")
        return "\n".join(lines)
    if not state.achievements:
        return "None yet — keep selling!"
    return "\n".join(f"★ {achievement_name(a, cfg)}" for a in sorted(state.achievements))


class StatsScreen(Screen[None]):
    BINDINGS = [
        Binding("escape", "close", "Back"),
        Binding("t", "close", "Back", show=False),
    ]

    def __init__(self, state: GameState, cfg: Config) -> None:
        super().__init__()
        self.state = state
        self.cfg = cfg

    def compose(self) -> ComposeResult:
        series = stats.cash_series(self.state)
        yield Header()
        with VerticalScroll():
            yield Static("Stats", classes="headline")
            with Vertical(id="chart", classes="panel"):
                yield Static("[b]Cash over time[/b]", classes="panel-title")
                if series:
                    yield Sparkline([float(c) for c in series], id="cash-chart")
                    yield Static(
                        f"start {fmt_cents(series[0])}   low {fmt_cents(min(series))}   "
                        f"high {fmt_cents(max(series))}   now {fmt_cents(series[-1])}",
                        id="chart-range",
                    )
                else:
                    yield Static("Play a day to see your cash chart.", id="chart-range")
            with Horizontal(id="stats-row"):
                yield Static(
                    "[b]Totals[/b]\n" + totals_text(self.state), id="totals", classes="panel"
                )
                yield Static(
                    "[b]Achievements[/b]\n" + achievements_text(self.state, self.cfg),
                    id="achievements",
                    classes="panel",
                )
            yield Static(
                _day_line("Best day", stats.best_day(self.state))
                + "\n"
                + _day_line("Worst day", stats.worst_day(self.state)),
                id="best-worst",
                classes="panel",
            )
        yield Footer()

    def action_close(self) -> None:
        self.app.pop_screen()
