"""Game over: final score and a summary; n starts a new game (choosing a difficulty)."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Footer, Header, Static

from lemonade.engine import stats
from lemonade.engine.config import Config
from lemonade.engine.models import GameState
from lemonade.engine.types import GameStatus
from lemonade.ui.format import achievement_name, fmt_cents

if TYPE_CHECKING:
    from lemonade.ui.app import LemonadeApp


def difficulty_levels(cfg: Config) -> dict[str, tuple[str, str]]:
    """{id: (name, description)} from `cfg.difficulties` if the engine has them, else {}."""
    levels = getattr(cfg, "difficulties", None) or {}
    return {
        key: (getattr(d, "name", key.capitalize()), getattr(d, "description", ""))
        for key, d in levels.items()
    }


def difficulty_name(state: GameState, cfg: Config) -> str:
    return difficulty_levels(cfg).get(state.difficulty, (state.difficulty.capitalize(), ""))[0]


def summary_text(state: GameState, cfg: Config) -> str:
    t = stats.totals(state)
    best = stats.best_day(state)
    if state.status is GameStatus.WON:
        verdict = f"You won after {t.days} day{'s' if t.days != 1 else ''}!"
    else:
        verdict = f"You went bankrupt after {t.days} day{'s' if t.days != 1 else ''}."
    lines = [
        verdict,
        "",
        f"Final cash (score): [b]{fmt_cents(state.cash)}[/b]",
        f"Days survived:      {t.days}",
        f"Cups sold:          {t.cups_sold} of {t.customers} passers-by",
        f"Total profit:       {fmt_cents(t.profit)}",
        f"Difficulty:         {difficulty_name(state, cfg)}",
    ]
    if best:
        lines.append(f"Best day:           day {best.day} ({fmt_cents(best.profit)} profit)")
    if state.achievements:
        names = ", ".join(achievement_name(a, cfg) for a in sorted(state.achievements))
        lines.append(f"Achievements:       {names}")
    return "\n".join(lines)


class DifficultyScreen(ModalScreen[str]):
    """Pick a difficulty: number keys or first letters (e/n/h), or click; escape = normal."""

    BINDINGS = [Binding("escape", "pick('normal')", "Normal")]

    def __init__(self, cfg: Config, current: str = "normal") -> None:
        super().__init__()
        self.levels = difficulty_levels(cfg)
        self.current = current

    def compose(self) -> ComposeResult:
        with Vertical(id="difficulty-box"):
            yield Static("[b]New game — choose a difficulty[/b]", classes="panel-title")
            for i, (key, (name, desc)) in enumerate(self.levels.items(), 1):
                yield Button(f"{i}. {name}", id=f"difficulty-{key}", classes="difficulty")
                yield Static(desc, classes="upgrade-desc")

    def on_mount(self) -> None:
        if self.current in self.levels:
            self.query_one(f"#difficulty-{self.current}", Button).focus()

    def on_key(self, event: events.Key) -> None:
        key = event.key
        for i, level in enumerate(self.levels, 1):
            if key in (str(i), level[:1]):
                self.action_pick(level)
                return

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.action_pick((event.button.id or "").removeprefix("difficulty-"))

    def action_pick(self, level: str) -> None:
        self.dismiss(level if level in self.levels else "normal")


class GameOverScreen(Screen[None]):
    BINDINGS = [Binding("n", "new_game", "New game", priority=True)]

    def __init__(self, state: GameState) -> None:
        super().__init__()
        self.state = state

    def compose(self) -> ComposeResult:
        cfg = cast("LemonadeApp", self.app).cfg
        yield Header()
        yield Static("Game over", classes="headline")
        yield Static(summary_text(self.state, cfg), id="summary", classes="panel")
        yield Static("Press [b]n[/b] for a new game or [b]q[/b] to quit.", classes="hint")
        yield Footer()

    def action_new_game(self) -> None:
        app = cast("LemonadeApp", self.app)
        if len(difficulty_levels(app.cfg)) < 2:
            app.restart()
            return
        app.push_screen(DifficultyScreen(app.cfg, self.state.difficulty), app.restart)
