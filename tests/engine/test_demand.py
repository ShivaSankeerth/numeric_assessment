import pytest

from factories import make_ctx, make_plan, make_state
from lemonade.engine.config import Config
from lemonade.engine.demand import (
    DemandBreakdown,
    buy_probability,
    combine,
    compute_demand,
    fair_price,
    fmt_mul,
    ideal_ice,
    loss_reason,
    price_factor,
    recipe_score,
    reputation_delta,
    satisfaction,
    traffic,
)
from lemonade.engine.models import Effect, Recipe
from lemonade.engine.types import Factor, LossReason


def eff(factor: Factor, op: str, value: float) -> Effect:
    return Effect(factor, op, value, "test", "test")  # type: ignore[arg-type]


def test_combine_multiplies_muls_and_sums_adds_per_factor() -> None:
    effects = [
        eff(Factor.TRAFFIC, "mul", 1.5),
        eff(Factor.TRAFFIC, "mul", 2.0),
        eff(Factor.TRAFFIC, "add", 10),
        eff(Factor.TASTE, "mul", 9.0),
    ]
    assert combine(effects, Factor.TRAFFIC) == (3.0, 10.0)
    assert combine([], Factor.TRAFFIC) == (1.0, 0.0)


def test_traffic_never_negative() -> None:
    assert traffic(100, [eff(Factor.TRAFFIC, "mul", 1.3)]) == 130
    assert traffic(100, [eff(Factor.TRAFFIC, "add", -500)]) == 0


def test_fair_price_scales_with_tolerance(cfg: Config) -> None:
    assert fair_price([], cfg) == 50
    assert fair_price([eff(Factor.PRICE_TOLERANCE, "mul", 1.2)], cfg) == pytest.approx(60)


@pytest.mark.parametrize(("price", "expected"), [(50, 1.0), (100, 0.0), (500, 0.0), (5, 1.2)])
def test_price_factor(cfg: Config, price: int, expected: float) -> None:
    assert price_factor(price, 50, cfg) == pytest.approx(expected)


def test_ideal_ice_rises_with_temperature(cfg: Config) -> None:
    assert ideal_ice(75, cfg) == 3
    assert ideal_ice(95, cfg) == 5
    assert ideal_ice(55, cfg) == 1
    assert ideal_ice(300, cfg) == cfg.game.recipe_limits.ice[1]


def test_ideal_recipe_scores_one(cfg: Config) -> None:
    score, notes = recipe_score(Recipe(6, 4, 3), 75, cfg)
    assert score == 1.0
    assert notes == ("Perfect lemonade!",)


@pytest.mark.parametrize(
    ("recipe", "note"),
    [
        (Recipe(6, 1, 3), "Too sour!"),
        (Recipe(6, 9, 3), "Too sweet!"),
        (Recipe(2, 4, 3), "Tastes watery."),
        (Recipe(10, 4, 3), "Way too lemony!"),
        (Recipe(6, 4, 0), "Needs more ice!"),
        (Recipe(6, 4, 9), "Too much ice!"),
    ],
)
def test_recipe_feedback(cfg: Config, recipe: Recipe, note: str) -> None:
    score, notes = recipe_score(recipe, 75, cfg)
    assert note in notes
    assert score < 1.0


def test_buy_probability_is_capped_before_buy_prob_effects(cfg: Config) -> None:
    assert buy_probability(1.2, 1.0, 1.0, [], cfg) == cfg.demand.max_buy_prob
    boosted = buy_probability(1.2, 1.0, 1.0, [eff(Factor.BUY_PROB, "mul", 2.0)], cfg)
    assert boosted == 1.0  # final clamp


def test_buy_probability_floor_and_monotonic_in_price(cfg: Config) -> None:
    assert buy_probability(0.0, 1.0, 0.3, [], cfg) == pytest.approx(cfg.demand.base_prob)
    probs = [buy_probability(price_factor(p, 50, cfg), 0.8, 0.3, [], cfg) for p in range(5, 200, 5)]
    assert probs == sorted(probs, reverse=True)


def test_compute_demand_applies_effects(cfg: Config) -> None:
    ctx = make_ctx(plan=make_plan(price_per_cup=60), temp_f=75)
    effects = (
        eff(Factor.TRAFFIC, "mul", 1.5),
        eff(Factor.PRICE_TOLERANCE, "mul", 1.2),
        eff(Factor.TASTE, "add", -0.5),
    )
    b = compute_demand(ctx, effects)
    assert b.customers == int(cfg.locations["park"].base_traffic * 1.5)
    assert b.fair_price == pytest.approx(60)
    assert b.price_factor == pytest.approx(1.0)
    assert b.taste == pytest.approx(0.5)
    assert 0 < b.buy_prob <= cfg.demand.max_buy_prob


def breakdown(pf: float, taste: float) -> DemandBreakdown:
    return DemandBreakdown(100, 50.0, pf, taste, (), 0.5)


@pytest.mark.parametrize(
    ("pf", "taste", "reason"),
    [
        (0.2, 0.2, LossReason.TOO_EXPENSIVE),
        (1.0, 0.2, LossReason.BAD_TASTE),
        (1.0, 1.0, LossReason.NOT_INTERESTED),
    ],
)
def test_loss_reason_picks_weakest_factor(
    cfg: Config, pf: float, taste: float, reason: LossReason
) -> None:
    assert loss_reason(breakdown(pf, taste), cfg) is reason


def test_reputation_delta(cfg: Config) -> None:
    assert reputation_delta(breakdown(1.0, 1.0), 10, cfg) > 0
    assert reputation_delta(breakdown(0.2, 0.3), 10, cfg) < 0
    assert reputation_delta(breakdown(1.0, 1.0), 0, cfg) == 0


def test_fmt_mul() -> None:
    assert fmt_mul(1.4) == "+40%"
    assert fmt_mul(0.45) == "-55%"


def test_default_state_demand_is_sane(cfg: Config) -> None:
    b = compute_demand(make_ctx(state=make_state()), ())
    assert b.customers == cfg.locations["park"].base_traffic


def test_satisfaction_blends_taste_and_value(cfg: Config) -> None:
    assert satisfaction(breakdown(1.0, 1.0), cfg) == pytest.approx(1.0)
    assert satisfaction(breakdown(1.2, 1.0), cfg) == pytest.approx(1.0)  # bargains cap at 1
    assert satisfaction(breakdown(0.0, 1.0), cfg) == pytest.approx(0.6)
    assert satisfaction(breakdown(1.0, 0.0), cfg) == pytest.approx(0.4)


def test_reputation_delta_bounds_and_neutral_point(cfg: Config) -> None:
    rate = cfg.demand.reputation_rate
    full = cfg.demand.reputation_full_volume
    assert reputation_delta(breakdown(1.0, 1.0), full, cfg) == pytest.approx(rate)
    assert reputation_delta(breakdown(0.0, 0.0), full, cfg) == pytest.approx(-rate)
    assert reputation_delta(breakdown(0.5, 0.5), full, cfg) == pytest.approx(0.0)


def test_reputation_delta_scales_with_cups_sold(cfg: Config) -> None:
    full = cfg.demand.reputation_full_volume
    good = breakdown(1.0, 1.0)
    assert reputation_delta(good, full // 2, cfg) == pytest.approx(
        reputation_delta(good, full, cfg) / 2
    )
    assert reputation_delta(good, full * 3, cfg) == reputation_delta(good, full, cfg)
