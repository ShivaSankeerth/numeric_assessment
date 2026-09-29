"""Pure game engine: no I/O, no UI imports.

Plugin packages (modifiers, events, upgrades) are imported here so their registries populate.
"""

from lemonade.engine import events as events
from lemonade.engine import modifiers as modifiers
from lemonade.engine import upgrades as upgrades
