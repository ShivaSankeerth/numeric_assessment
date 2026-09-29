"""Money / percent formatting and parsing. The only place cents become text."""

from decimal import Decimal, InvalidOperation

from lemonade.engine.types import Cents


def fmt_cents(cents: Cents) -> str:
    """1234 -> '$12.34', -150 -> '-$1.50'."""
    sign = "-" if cents < 0 else ""
    whole, part = divmod(abs(cents), 100)
    return f"{sign}${whole:,}.{part:02d}"


def fmt_pct(fraction: float) -> str:
    """0.456 -> '46%'."""
    return f"{round(fraction * 100)}%"


def parse_cents(text: str) -> Cents:
    """Parse a dollar amount typed by the player: '0.5', '$1.25', '2' -> cents.

    Raises ValueError for anything else (including fractions of a cent).
    """
    cleaned = text.strip().removeprefix("$").strip()
    try:
        amount = Decimal(cleaned) * 100
    except InvalidOperation:
        raise ValueError(f"not a dollar amount: {text!r}") from None
    if amount != amount.to_integral_value() or amount < 0:
        raise ValueError(f"not a valid price: {text!r}")
    return int(amount)


def achievement_name(achievement_id: str, cfg: object) -> str:
    """Display name for an achievement: from `cfg.achievements` when the engine provides it."""
    entry = getattr(cfg, "achievements", {}).get(achievement_id)
    name = getattr(entry, "name", None)
    return name or achievement_id.replace("_", " ").capitalize()
