"""Bots play many seeded games without exceptions; the CLI prints a balance report."""

import pytest

from factories import make_state
from lemonade.engine.config import Config
from lemonade.engine.errors import InvalidPlan
from lemonade.engine.game import preview_plan
from lemonade.engine.models import DayPlan, GameState
from lemonade.sim import runner
from lemonade.sim.strategies import STRATEGIES

GAMES, DAYS = 100, 20  # ~2s for all strategies together


@pytest.mark.parametrize("name", sorted(STRATEGIES))
def test_strategy_plays_100_seeded_games(name: str, cfg: Config) -> None:
    summary = runner.run_games(name, GAMES, DAYS, seed_start=0, cfg=cfg)
    assert summary.games == GAMES
    assert summary.invalid_plans == 0
    assert 0 <= summary.bankruptcy_rate <= 1
    assert 0 < summary.mean_days_survived <= DAYS
    assert summary.mean_cash >= 0


@pytest.mark.parametrize("name", sorted(STRATEGIES))
def test_strategy_plans_are_affordable(name: str, cfg: Config) -> None:
    for cash in (0, 300, 2000):
        state = make_state(cash=cash)
        assert preview_plan(state, STRATEGIES[name](state, cfg), cfg).cash_after >= 0


def test_run_is_deterministic(cfg: Config) -> None:
    a = runner.run_games("greedy", 5, 5, seed_start=7, cfg=cfg)
    b = runner.run_games("greedy", 5, 5, seed_start=7, cfg=cfg)
    assert a == b


def test_invalid_plan_does_not_crash_the_run(cfg: Config, monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(state: GameState, cfg: Config) -> DayPlan:
        raise InvalidPlan("nope")

    monkeypatch.setitem(STRATEGIES, "broken", broken)
    summary = runner.run_games("broken", 2, 3, seed_start=0, cfg=cfg)
    assert summary.invalid_plans >= 2
    assert summary.mean_days_survived >= 1


def test_cli_prints_a_report(capsys: pytest.CaptureFixture[str]) -> None:
    runner.main(["--games", "3", "--days", "3", "--strategy", "all", "--seed-start", "1"])
    out = capsys.readouterr().out
    assert "Balance report: 3 games x 3 days" in out
    for name in STRATEGIES:
        assert name in out


def test_cli_rejects_unknown_strategy() -> None:
    with pytest.raises(SystemExit):
        runner.main(["--strategy", "nope"])
