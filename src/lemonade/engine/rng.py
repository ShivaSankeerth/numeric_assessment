"""Deterministic, per-day, per-purpose random streams."""

import random


def day_rng(seed: int, day: int, stream: str) -> random.Random:
    """Return a fresh RNG for one purpose on one day of one game.

    Streams isolate consumers (e.g. "weather", "sales", "event:heat_wave") so that adding a new
    plugin never shifts the random draws of existing ones. String seeding is stable across runs
    (it does not depend on PYTHONHASHSEED).
    """
    return random.Random(f"{seed}:{day}:{stream}")
