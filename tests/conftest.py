"""Shared fixtures. Factory functions live in `tests/factories.py` (importable as `factories`)."""

import pytest

from factories import default_cfg
from lemonade.engine.config import Config


@pytest.fixture(scope="session")
def cfg() -> Config:
    return default_cfg()
