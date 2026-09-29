"""Textual app: owns the current GameState and routes between screens."""

from __future__ import annotations

import argparse
import random

from textual.app import App
from textual.binding import Binding

from lemonade.engine import game, market
from lemonade.engine.config import Config, load_config
from lemonade.engine.errors import LemonadeError
from lemonade.engine.models import DayPlan, GameState
from lemonade.engine.types import GameStatus
from lemonade.ui.screens.day_result import DayResultScreen
from lemonade.ui.screens.game_over import GameOverScreen
from lemonade.ui.screens.help import HelpScreen
from lemonade.ui.screens.plan import PlanScreen
from lemonade.ui.screens.stats import StatsScreen


class LemonadeApp(App[None]):
    CSS_PATH = "theme.tcss"
    TITLE = "Lemonade Stand Tycoon"
    # Textual never lets a letter binding fire while an Input has focus (the Input may want to
    # type it), so q quits whenever no input is focused; Textual's ctrl+q always works.
    BINDINGS = [Binding("q", "quit", "Quit")]

    def __init__(self, seed: int, cfg: Config, state: GameState | None = None) -> None:
        super().__init__()
        self.seed = seed
        self.cfg = cfg
        self.state = state or game.new_game(seed, cfg)

    def on_mount(self) -> None:
        self.push_screen(PlanScreen())

    def start_day(self, plan: DayPlan) -> None:
        """Play the day via the engine; engine errors become notifications, never crashes."""
        notes = market.market_notes(self.state, self.cfg)
        try:
            self.state, result = game.play_day(self.state, plan, self.cfg)
        except LemonadeError as err:
            self.notify(str(err), title="Can't start the day", severity="error")
            return
        self.push_screen(DayResultScreen(result, self.state, notes))

    def show_stats(self) -> None:
        self.push_screen(StatsScreen(self.state, self.cfg))

    def show_help(self) -> None:
        self.push_screen(HelpScreen())

    def finish_day(self) -> None:
        """Leave the day result: game over if bankrupt, otherwise back to planning."""
        if self.state.status is GameStatus.BANKRUPT:
            self.switch_screen(GameOverScreen(self.state))
        else:
            self.pop_screen()

    def restart(self) -> None:
        """Start a fresh game with the next seed and return to planning."""
        self.seed += 1
        self.state = game.new_game(self.seed, self.cfg)
        self.pop_screen()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="lemonade", description="Lemonade Stand Tycoon")
    parser.add_argument("--seed", type=int, default=None, help="seed for a reproducible game")
    args = parser.parse_args(argv)
    seed = args.seed if args.seed is not None else random.SystemRandom().randrange(1_000_000)
    LemonadeApp(seed=seed, cfg=load_config()).run()


if __name__ == "__main__":
    main()
