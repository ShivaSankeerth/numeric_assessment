"""Game over: final score and a short summary."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from lemonade.engine.models import GameState
from lemonade.ui.format import fmt_cents

if TYPE_CHECKING:
    from lemonade.ui.app import LemonadeApp


def summary_text(state: GameState) -> str:
    days = len(state.history)
    cups = sum(r.cups_sold for r in state.history)
    best = max(state.history, key=lambda r: r.profit, default=None)
    best_line = f"Best day: day {best.day} ({fmt_cents(best.profit)})" if best else ""
    return (
        f"You went bankrupt after {days} day{'s' if days != 1 else ''}.\n"
        f"Final cash (score): {fmt_cents(state.cash)}\n"
        f"Cups sold: {cups}\n{best_line}"
    )


class GameOverScreen(Screen[None]):
    BINDINGS = [Binding("n", "new_game", "New game", priority=True)]

    def __init__(self, state: GameState) -> None:
        super().__init__()
        self.state = state

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Game over", classes="headline")
        yield Static(summary_text(self.state), id="summary", classes="panel")
        yield Static("Press [b]n[/b] for a new game or [b]q[/b] to quit.")
        yield Footer()

    def action_new_game(self) -> None:
        cast("LemonadeApp", self.app).restart()
