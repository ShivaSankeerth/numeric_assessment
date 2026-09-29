"""Help overlay: keys and a short how-to-play."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

HELP_TEXT = """\
[b]How to play[/b]
Every morning you plan the day, then the day plays out on its own.
 1. [b]Shop[/b]: buy supplies in packs. Bigger orders get bulk discounts;
    prices change daily. Ice melts overnight, lemons spoil.
 2. [b]Recipe[/b]: lemons and sugar per pitcher (12 cups), ice per cup.
    Hot days want more ice. The taste hint shows what customers will say.
 3. [b]Price[/b]: too high and people walk past; too low and you lose money.
 4. [b]Upgrades[/b]: one-off purchases that help every day after.
Then start the day and read the report to see [i]why[/i] you sold what you sold.
You go bankrupt when you can't afford to make even one cup.

[b]Keys[/b]
 enter      start the day / next day
 1 2 3 4    Shop / Recipe / Price / Upgrades tab
 tab        move between inputs
 t          stats (cash chart, best day, achievements)
 ?          this help
 n          new game (on the game over screen)
 q          quit (ctrl+q works everywhere)

Letter keys don't work while you're typing in a box: press tab until the
Start button is highlighted, or use enter to start the day.
[dim]escape or ? to close[/dim]"""


class HelpScreen(ModalScreen[None]):
    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("question_mark", "close", "Close", show=False),
    ]

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="help-box"):
            yield Static(HELP_TEXT, id="help-text")

    def action_close(self) -> None:
        self.app.pop_screen()
