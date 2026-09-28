"""Shared alphabet constants for ISO 7064:2021 check character systems.

The single source of truth for the character alphabets used by every
system in the package. Per-character value lookups are inlined in
``_systems.py`` (each system needs different expansions and error
messages).
"""

from __future__ import annotations

#: Numeric alphabet (10 characters, 0-9). Used by MOD_11_2 and MOD_97_10.
ALPHABET_DIGITS: str = "0123456789"

#: Alphanumeric alphabet (36 characters, 0-9 + A-Z). Used by MOD_37_2,
#: MOD_1271_36 and as the digit-string encoding base for MOD_661_26.
ALPHABET_ALNUM: str = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

__all__ = ["ALPHABET_DIGITS", "ALPHABET_ALNUM"]