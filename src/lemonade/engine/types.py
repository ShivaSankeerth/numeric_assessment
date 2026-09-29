"""Small value types and enums shared across the engine."""

from enum import StrEnum

Cents = int


class Item(StrEnum):
    LEMON = "lemon"  # unit: each
    SUGAR = "sugar"  # unit: cup of sugar
    ICE = "ice"  # unit: cube
    CUP = "cup"  # unit: paper cup


class Weather(StrEnum):
    SUNNY = "sunny"
    HOT = "hot"
    CLOUDY = "cloudy"
    RAINY = "rainy"
    STORM = "storm"


class Factor(StrEnum):
    TRAFFIC = "traffic"
    PRICE_TOLERANCE = "price_tolerance"
    TASTE = "taste"
    BUY_PROB = "buy_prob"


class LossReason(StrEnum):
    TOO_EXPENSIVE = "too_expensive"
    BAD_TASTE = "bad_taste"
    SOLD_OUT = "sold_out"
    NOT_INTERESTED = "not_interested"


class StopReason(StrEnum):
    SOLD_OUT_CUPS = "sold_out_cups"
    SOLD_OUT_LEMONS = "sold_out_lemons"
    SOLD_OUT_SUGAR = "sold_out_sugar"
    SOLD_OUT_ICE = "sold_out_ice"
    STAND_CLOSED = "stand_closed"


class GameStatus(StrEnum):
    PLAYING = "playing"
    BANKRUPT = "bankrupt"
    WON = "won"
