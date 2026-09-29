"""Game facade: the only entry points the UI and bots need.

`play_day` = status guard -> `simulation.simulate_day` -> `end_day` (bankruptcy, later win and
achievements).
"""

from __future__ import annotations

from dataclasses import replace

from lemonade.engine import inventory, market, weather
from lemonade.engine.config import Config
from lemonade.engine.errors import ConfigError, GameOverError
from lemonade.engine.models import DayPlan, DayResult, GameState, Inventory, PlanPreview
from lemonade.engine.recipes import effective_recipe
from lemonade.engine.rng import day_rng
from lemonade.engine.simulation import simulate_day
from lemonade.engine.types import GameStatus


def new_game(seed: int, cfg: Config, difficulty: str = "normal") -> GameState:
    """Day 1 with the difficulty's starting cash, empty inventory and a forecast for day 1.

    `difficulty` is a key of `cfg.difficulties` ("easy", "normal", "hard"); its traffic and
    supplier price multipliers apply every day. Raises ConfigError for an unknown difficulty.
    """
    if difficulty not in cfg.difficulties:
        known = ", ".join(sorted(cfg.difficulties))
        raise ConfigError(f"Unknown difficulty '{difficulty}' (choose from: {known})")
    return GameState(
        seed=seed,
        day=1,
        cash=cfg.difficulties[difficulty].starting_cash,
        inventory=Inventory.empty(),
        reputation=cfg.game.starting_reputation,
        upgrades=frozenset(),
        forecast=weather.generate_forecast(day_rng(seed, 1, "forecast"), cfg),
        history=(),
        difficulty=difficulty,
    )


def is_bankrupt(state: GameState, cfg: Config) -> bool:
    """Assumption A3: cash can't cover what's missing to serve even one minimal cup.

    Cash 0 with a servable cup in stock is NOT bankrupt (the cost to make one is then 0).
    """
    return state.cash < market.cost_to_make_one_cup(state, cfg)


def end_day(state: GameState, cfg: Config) -> GameState:
    """Apply end-of-day game status (bankruptcy now; win/achievements later)."""
    if is_bankrupt(state, cfg):
        return replace(state, status=GameStatus.BANKRUPT)
    return state


def play_day(state: GameState, plan: DayPlan, cfg: Config) -> tuple[GameState, DayResult]:
    """Play one day. Raises GameOverError if the game is over, InvalidPlan/InsufficientFunds
    if the plan is illegal (state unchanged)."""
    if state.status is not GameStatus.PLAYING:
        raise GameOverError(f"The game is over ({state.status.value}); start a new game")
    new_state, result = simulate_day(state, plan, cfg)
    return end_day(new_state, cfg), result


def preview_plan(state: GameState, plan: DayPlan, cfg: Config) -> PlanPreview:
    """Cart cost, cash left and cups makeable if this plan were started (for the plan screen).

    Never raises: purchases with fewer than 1 pack are ignored for the stock estimate.
    """
    cost = market.plan_cost(state, plan, cfg)
    sane = replace(plan, purchases=tuple(p for p in plan.purchases if p.packs > 0))
    stocked, _ = market.apply_purchases(state, sane, cfg)
    return PlanPreview(
        cost=cost,
        cash_after=state.cash - cost,
        cups_makeable=inventory.cups_makeable(
            stocked.inventory,
            effective_recipe(stocked, plan.recipe, cfg),
            cfg.game.cups_per_pitcher,
        ),
    )
