"""Headless multi-game runner and balance report: `lemonade-sim --games 200 --strategy all`."""

from __future__ import annotations

import argparse
import statistics
from dataclasses import dataclass

from rich.console import Console
from rich.table import Table

from lemonade.engine import game
from lemonade.engine.config import Config, load_config
from lemonade.engine.errors import LemonadeError
from lemonade.engine.models import DayPlan, GameState, Recipe
from lemonade.engine.types import GameStatus
from lemonade.sim.strategies import STRATEGIES, Strategy
from lemonade.ui.format import fmt_cents, fmt_pct

EMPTY_PLAN = DayPlan(purchases=(), recipe=Recipe(), price_per_cup=50)


@dataclass(frozen=True, slots=True)
class Summary:
    strategy: str
    games: int
    days: int
    mean_cash: float  # cents
    median_cash: float  # cents
    bankruptcy_rate: float
    mean_days_survived: float
    mean_cups_sold: float
    invalid_plans: int  # plans the engine rejected (replaced by an empty plan)


def play_game(strategy: Strategy, seed: int, days: int, cfg: Config) -> tuple[GameState, int]:
    """Play up to `days` days. Returns (final state, number of rejected plans)."""
    state = game.new_game(seed, cfg)
    rejected = 0
    for _ in range(days):
        if state.status is not GameStatus.PLAYING:
            break
        try:
            state, _ = game.play_day(state, strategy(state, cfg), cfg)
        except LemonadeError:
            rejected += 1
            try:
                state, _ = game.play_day(state, EMPTY_PLAN, cfg)
            except LemonadeError:
                break
    return state, rejected


def run_games(name: str, games: int, days: int, seed_start: int, cfg: Config) -> Summary:
    """Play `games` seeded games (seeds seed_start..) with one strategy and summarise them."""
    strategy = STRATEGIES[name]
    finals = [play_game(strategy, seed_start + i, days, cfg) for i in range(games)]
    states = [s for s, _ in finals]
    cash = [s.cash for s in states] or [0]
    n = max(1, games)
    return Summary(
        strategy=name,
        games=games,
        days=days,
        mean_cash=statistics.fmean(cash),
        median_cash=statistics.median(cash),
        bankruptcy_rate=sum(s.status is GameStatus.BANKRUPT for s in states) / n,
        mean_days_survived=sum(len(s.history) for s in states) / n,
        mean_cups_sold=sum(r.cups_sold for s in states for r in s.history) / n,
        invalid_plans=sum(r for _, r in finals),
    )


def report(summaries: list[Summary]) -> Table:
    first = summaries[0]
    table = Table(title=f"Balance report: {first.games} games x {first.days} days")
    for col in ("Strategy", "Mean cash", "Median cash", "Bankrupt", "Days survived", "Cups sold"):
        table.add_column(col, justify="left" if col == "Strategy" else "right")
    for s in summaries:
        table.add_row(
            s.strategy,
            fmt_cents(round(s.mean_cash)),
            fmt_cents(round(s.median_cash)),
            fmt_pct(s.bankruptcy_rate),
            f"{s.mean_days_survived:.1f}",
            f"{s.mean_cups_sold:.0f}",
        )
    return table


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="lemonade-sim", description="Headless balance report")
    parser.add_argument("--games", type=int, default=200)
    parser.add_argument("--strategy", choices=[*STRATEGIES, "all"], default="all")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--seed-start", type=int, default=0)
    args = parser.parse_args(argv)
    cfg = load_config()
    names = list(STRATEGIES) if args.strategy == "all" else [args.strategy]
    summaries = [run_games(n, args.games, args.days, args.seed_start, cfg) for n in names]
    console = Console()
    console.print(report(summaries))
    rejected = sum(s.invalid_plans for s in summaries)
    if rejected:
        console.print(f"[yellow]{rejected} plans were rejected and replaced by an empty plan[/]")


if __name__ == "__main__":
    main()
