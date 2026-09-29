from lemonade.engine.rng import day_rng


def draws(seed: int, day: int, stream: str) -> list[float]:
    rng = day_rng(seed, day, stream)
    return [rng.random() for _ in range(5)]


def test_same_inputs_give_same_sequence() -> None:
    assert draws(42, 3, "sales") == draws(42, 3, "sales")


def test_streams_days_and_seeds_are_independent() -> None:
    base = draws(42, 3, "sales")
    assert draws(42, 3, "weather") != base
    assert draws(42, 4, "sales") != base
    assert draws(43, 3, "sales") != base
