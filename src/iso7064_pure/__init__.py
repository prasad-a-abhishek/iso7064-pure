"""iso7064-pure: zero-dependency ISO/IEC 7064:2021 check character systems.

This package implements the five hybrid MOD-N-X systems defined by ISO/IEC
7064:2021 (MOD 11-2, MOD 37-2, MOD 97-10, MOD 661-26, MOD 1271-36) plus
the dispatch entry points and a single canonical exception type.

Public API
----------

Each system is exposed as a module-level singleton with three methods:

  * ``compute(data)``   — return ``data + check_character(data)``
  * ``verify(data)``    — return ``True`` iff ``data`` ends in a valid
    check character (round-trip)
  * ``check_character(data)`` — return just the check character(s)

Top-level dispatch:
  * ``compute(data, *, mode)`` and ``verify(data, *, mode)``

CLI:
  * ``python -m iso7064_pure compute "..." --mode MOD_11_2``
  * ``python -m iso7064_pure verify "..." --mode MOD_97_10``
"""

from __future__ import annotations

from enum import Enum

from iso7064_pure._alphabet import (
    ALPHABET_ALNUM,
    ALPHABET_DIGITS,
)
from iso7064_pure._systems import (
    ISO7064Error,
    MOD_11_2,
    MOD_37_2,
    MOD_97_10,
    MOD_661_26,
    MOD_1271_36,
    System,
    _resolve_system,
)

__all__ = [
    "ALPHABET_ALNUM",
    "ALPHABET_DIGITS",
    "ISO7064Error",
    "MOD_11_2",
    "MOD_37_2",
    "MOD_97_10",
    "MOD_661_26",
    "MOD_1271_36",
    "Mode",
    "System",
    "compute",
    "verify",
]

__version__: str = "0.1.0"


class Mode(str, Enum):
    """Identifier for the five hybrid MOD-N-X systems.

    The string value matches the public singleton names (``"MOD_11_2"``
    etc.). Use ``Mode.MOD_11_2`` or ``Mode("MOD_11_2")`` interchangeably
    — the dispatch helpers accept either form.
    """

    MOD_11_2 = "MOD_11_2"
    MOD_37_2 = "MOD_37_2"
    MOD_97_10 = "MOD_97_10"
    MOD_661_26 = "MOD_661_26"
    MOD_1271_36 = "MOD_1271_36"


# Attach Mode enum to each singleton so dispatch can go through `mode.value`.
MOD_11_2.mode = Mode.MOD_11_2
MOD_37_2.mode = Mode.MOD_37_2
MOD_97_10.mode = Mode.MOD_97_10
MOD_661_26.mode = Mode.MOD_661_26
MOD_1271_36.mode = Mode.MOD_1271_36


def compute(data: str, *, mode: Mode) -> str:
    """Dispatch :meth:`System.compute` via a :class:`Mode` enum value.

    Parameters
    ----------
    data:
        Input string (numeric, alphanumeric, or IBAN-shaped per ``mode``).
    mode:
        One of :class:`Mode` — selects which check character system to use.
    """
    return _resolve_system(mode).compute(data)


def verify(data: str, *, mode: Mode) -> bool:
    """Dispatch :meth:`System.verify` via a :class:`Mode` enum value.

    Returns ``True`` iff ``data`` ends in a valid check character for the
    selected system (round-trip property).
    """
    return _resolve_system(mode).verify(data)