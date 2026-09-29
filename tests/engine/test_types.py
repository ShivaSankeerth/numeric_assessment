from lemonade.engine.types import Factor, GameStatus, Item, LossReason, StopReason, Weather


def test_enum_values_are_stable_strings() -> None:
    # Values are persisted in TOML / saves, so they must never change.
    assert [i.value for i in Item] == ["lemon", "sugar", "ice", "cup"]
    assert {w.value for w in Weather} == {"sunny", "hot", "cloudy", "rainy", "storm"}
    assert Factor.TRAFFIC == "traffic"
    assert LossReason.SOLD_OUT == "sold_out"
    assert StopReason.STAND_CLOSED == "stand_closed"
    assert GameStatus.PLAYING == "playing"
