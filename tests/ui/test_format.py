import pytest

from lemonade.ui.format import fmt_cents, fmt_pct, parse_cents


@pytest.mark.parametrize(
    ("cents", "text"),
    [(0, "$0.00"), (5, "$0.05"), (1234, "$12.34"), (-150, "-$1.50"), (123456, "$1,234.56")],
)
def test_fmt_cents(cents: int, text: str) -> None:
    assert fmt_cents(cents) == text


def test_fmt_pct() -> None:
    assert fmt_pct(0.456) == "46%"


@pytest.mark.parametrize(
    ("text", "cents"), [("0.5", 50), ("$1.25", 125), (" 2 ", 200), ("0.05", 5)]
)
def test_parse_cents(text: str, cents: int) -> None:
    assert parse_cents(text) == cents


@pytest.mark.parametrize("text", ["", "abc", "0.505", "-1"])
def test_parse_cents_rejects_bad_input(text: str) -> None:
    with pytest.raises(ValueError):
        parse_cents(text)


@pytest.mark.parametrize("cents", [0, 7, 50, 999, 12345])
def test_round_trip(cents: int) -> None:
    assert parse_cents(fmt_cents(cents).replace(",", "")) == cents
