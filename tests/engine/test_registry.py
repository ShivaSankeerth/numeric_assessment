import pytest

from factories import make_ctx, make_state
from lemonade.engine import registry
from lemonade.engine.config import Config
from lemonade.engine.registry import (
    EVENTS,
    MODIFIERS,
    UPGRADE_HANDLERS,
    BaseEvent,
    BaseUpgrade,
    active_upgrades,
    register_modifier,
)


@pytest.fixture
def empty_modifiers(monkeypatch: pytest.MonkeyPatch) -> dict:
    fresh: dict = {}
    monkeypatch.setattr(registry, "MODIFIERS", fresh)
    return fresh


def test_decorator_registers_an_instance_and_returns_class(empty_modifiers: dict) -> None:
    @register_modifier
    class Dummy:
        id = "dummy"

        def effects(self, ctx):  # type: ignore[no-untyped-def]
            return []

    assert isinstance(empty_modifiers["dummy"], Dummy)
    assert Dummy.id == "dummy"


def test_duplicate_id_raises(empty_modifiers: dict) -> None:
    class A:
        id = "same"

    register_modifier(A)
    with pytest.raises(ValueError, match="duplicate"):
        register_modifier(A)


def test_missing_id_raises(empty_modifiers: dict) -> None:
    class NoId:
        pass

    with pytest.raises(ValueError, match="id"):
        register_modifier(NoId)


def test_example_plugins_registered() -> None:
    assert "weather" in MODIFIERS
    assert "heat_wave" in EVENTS
    assert "cooler" in UPGRADE_HANDLERS


def test_every_upgrade_in_content_has_a_handler_and_vice_versa(cfg: Config) -> None:
    assert set(cfg.upgrades) == set(UPGRADE_HANDLERS)


def test_every_registered_event_has_content(cfg: Config) -> None:
    assert set(EVENTS) <= set(cfg.events)


def test_base_classes_are_inert(cfg: Config) -> None:
    assert BaseUpgrade().ice_retention(cfg) == 0.0
    assert BaseUpgrade().lemon_yield_bonus(cfg) == 0.0


def test_base_event_defaults() -> None:
    ctx = make_ctx()
    assert BaseEvent().chance(ctx) == 0.0
    assert BaseEvent().on_day_start(ctx).effects == ()


def test_active_upgrades_only_owned() -> None:
    assert active_upgrades(make_state()) == []
    owned = active_upgrades(make_state(upgrades=frozenset({"cooler", "not_a_handler"})))
    assert [h.id for h in owned] == ["cooler"]
