"""UI test setup: no animations, so Pilot tests never wait on tweens."""

import os

os.environ.setdefault("TEXTUAL_ANIMATIONS", "none")
