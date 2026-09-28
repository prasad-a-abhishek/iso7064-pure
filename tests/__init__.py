"""Imports and helpers shared across the test suite."""

from __future__ import annotations

import sys
from pathlib import Path

# Make the in-tree ``src/`` layout importable without an editable install.
_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import iso7064_pure  # noqa: E402  (intentional after sys.path mutation)

import pytest  # noqa: E402  (declared after path fix-up)

from iso7064_pure import (  # noqa: E402
    ALPHABET_ALNUM,
    ALPHABET_DIGITS,
    ISO7064Error,
    MOD_11_2,
    MOD_37_2,
    MOD_97_10,
    MOD_661_26,
    MOD_1271_36,
    Mode,
    System,
    __version__,
    compute,
    verify,
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
    "__version__",
    "compute",
    "pytest",
    "verify",
]