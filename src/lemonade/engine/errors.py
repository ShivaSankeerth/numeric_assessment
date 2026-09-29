"""Domain exceptions. The UI surfaces these as notifications."""


class LemonadeError(Exception):
    """Base class for all expected, user-facing engine errors."""


class InvalidPlan(LemonadeError):
    """The day plan breaks a rule (bad recipe, unknown upgrade, duplicate purchase, ...)."""


class InsufficientFunds(LemonadeError):
    """The day plan costs more than the cash on hand."""


class GameOverError(LemonadeError):
    """An action was attempted on a game that is no longer being played."""


class ConfigError(LemonadeError):
    """Content TOML is missing a key or holds an invalid value."""
