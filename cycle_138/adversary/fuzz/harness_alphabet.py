"""Atheris harness for the alphabet / encoding surface (Surface 4).

Surface 4 of the cycle_138 adversary workstream.

This is the deepest, narrowest surface: the alphabet constants
(``ALPHABET_DIGITS``, ``ALPHABET_ALNUM``) and the per-character value
encoder ``_letter_value(ch) -> int`` that EVERY alphanumeric ISO 7064
system depends on.  It's a separate surface because:

* A bug here (e.g. accepting lowercase, off-by-one in A=10) breaks
  every system that uses it.
* It's exercised by an order of magnitude more often than compute()
  itself (once per character vs once per call).
* It has its own validation branches (``lowercase`` vs
  ``non-alphanumeric`` error messages) that the other surfaces only
  hit transitively.

Specifically we test:

* ``_letter_value("0") == 0`` ... ``_letter_value("9") == 9`` (digits).
* ``_letter_value("A") == 10`` ... ``_letter_value("Z") == 35``
  (ISO 7064 letter encoding, A=10..Z=35).
* ``_letter_value("a")`` MUST raise :class:`ISO7064Error` with
  ``"lowercase"`` in the message.
* ``_letter_value("!")`` MUST raise :class:`ISO7064Error` with
  ``"non-alphanumeric"`` in the message.
* ``_letter_value("")`` MUST raise :class:`ISO7064Error` (empty string
  is not a digit nor a letter).
* ``ALPHABET_ALNUM[P // 36] + ALPHABET_ALNUM[P % 36]`` must be the
  inverse of ``_letter_value`` for any valid input — round-trip
  consistency for the MOD_1271_36 two-char encoding path.
* Random single-char inputs MUST either succeed (in which case the
  value is in ``[0..35]``) or raise :class:`ISO7064Error`.  NO
  :class:`KeyError`, :class:`AttributeError`, or
  :class:`UnicodeError` may leak.

Run::

    python3 harness_alphabet.py -atheris_runs=100000 -max_total_time=5
"""
from __future__ import annotations

import sys

import atheris  # type: ignore[import-not-found]

with atheris.instrument_imports():  # type: ignore[attr-defined]
    from iso7064_pure import (
        ALPHABET_ALNUM,
        ALPHABET_DIGITS,
        ISO7064Error,
    )
    from iso7064_pure._systems import _letter_value  # type: ignore[import-not-found]


# Reference tables for property-based assertions.
_DIGITS_VALUES: dict[str, int] = {str(i): i for i in range(10)}
_UPPER_LETTERS: str = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_LETTER_VALUES: dict[str, int] = {ch: 10 + i for i, ch in enumerate(_UPPER_LETTERS)}


@atheris.instrument_func  # type: ignore[attr-defined]
def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)  # type: ignore[attr-defined]

    # Choose a character: 0=raw random, 1=digit, 2=upper letter,
    # 3=lowercase letter, 4=symbol, 5=non-ASCII, 6=empty string, 7=unicode cat.
    kind = fdp.ConsumeIntInRange(0, 7)

    if kind == 0:
        # Raw random bytes → utf-8 decode (lossy).
        try:
            ch = fdp.ConsumeUnicodeNoSurrogates(1)
        except UnicodeEncodeError:
            return
    elif kind == 1:
        ch = fdp.ConsumeIntInRange(0, 9).__str__()
    elif kind == 2:
        ch = _UPPER_LETTERS[fdp.ConsumeIntInRange(0, 25)]
    elif kind == 3:
        ch = chr(ord("a") + fdp.ConsumeIntInRange(0, 25))
    elif kind == 4:
        # Pick from a curated list of punctuation / symbols that are
        # NOT in the alphanumeric alphabet.
        symbols: tuple[str, ...] = ("!", "@", "#", "$", "%", "^", "&", "*",
                                     "(", ")", "-", "_", "+", "=", "[", "]",
                                     "{", "}", "|", "\\", ":", ";", '"', "'",
                                     ",", ".", "<", ">", "/", "?",
                                     "`", "~", " ", "\t", "\n")
        ch = symbols[fdp.ConsumeIntInRange(0, len(symbols) - 1)]
    elif kind == 5:
        # Non-ASCII: Greek, Cyrillic, CJK, emoji, etc.
        non_ascii: tuple[str, ...] = ("α", "β", "γ", "Ж", "З", "И", "中", "文",
                                       "日", "本", "🐍", "🦀", "€", "£", "¥",
                                       "‽", "✓", "✗", "♠", "♣")
        ch = non_ascii[fdp.ConsumeIntInRange(0, len(non_ascii) - 1)]
    elif kind == 6:
        ch = ""
    else:
        # kind == 7: arbitrary unicode code point.
        ch = chr(fdp.ConsumeIntInRange(0, 0x10FFFF))

    # === _letter_value() ===
    # Decide whether this character is expected to be valid.
    if ch in _DIGITS_VALUES:
        expected = _DIGITS_VALUES[ch]
        try:
            v = _letter_value(ch)
        except ISO7064Error as exc:
            raise AssertionError(
                f"_letter_value({ch!r}) on valid digit raised ISO7064Error: "
                f"{exc!r}"
            ) from exc
        except Exception as exc:
            raise AssertionError(
                f"_letter_value({ch!r}) on valid digit raised "
                f"{type(exc).__name__}: {exc!r}"
            ) from exc
        assert v == expected, f"_letter_value({ch!r}) = {v}, want {expected}"
    elif ch in _LETTER_VALUES:
        expected = _LETTER_VALUES[ch]
        try:
            v = _letter_value(ch)
        except ISO7064Error as exc:
            raise AssertionError(
                f"_letter_value({ch!r}) on valid upper letter raised "
                f"ISO7064Error: {exc!r}"
            ) from exc
        except Exception as exc:
            raise AssertionError(
                f"_letter_value({ch!r}) on valid upper letter raised "
                f"{type(exc).__name__}: {exc!r}"
            ) from exc
        assert v == expected, f"_letter_value({ch!r}) = {v}, want {expected}"
    elif ch and "a" <= ch <= "z":
        # Lowercase — must raise ISO7064Error with "lowercase" in message.
        try:
            v = _letter_value(ch)
        except ISO7064Error as exc:
            assert "lowercase" in str(exc), (
                f"_letter_value({ch!r}) raised ISO7064Error without "
                f"'lowercase' substring: {exc!r}"
            )
        except Exception as exc:
            raise AssertionError(
                f"_letter_value({ch!r}) on lowercase raised wrong "
                f"{type(exc).__name__}: {exc!r}"
            ) from exc
        else:
            raise AssertionError(
                f"_letter_value({ch!r}) on lowercase returned {v!r} — "
                f"should have raised ISO7064Error"
            )
    else:
        # Anything else (symbol, non-ASCII, empty, multi-char — though
        # ConsumeUnicodeNoSurrogates(1) always gives length 1) MUST raise
        # ISO7064Error with "non-alphanumeric" in the message.
        try:
            v = _letter_value(ch)
        except ISO7064Error as exc:
            assert "non-alphanumeric" in str(exc), (
                f"_letter_value({ch!r}) raised ISO7064Error without "
                f"'non-alphanumeric' substring: {exc!r}"
            )
        except Exception as exc:
            raise AssertionError(
                f"_letter_value({ch!r}) on invalid char raised wrong "
                f"{type(exc).__name__}: {exc!r}"
            ) from exc
        else:
            raise AssertionError(
                f"_letter_value({ch!r}) on invalid char returned {v!r} — "
                f"should have raised ISO7064Error"
            )

    # === Alphabet constants ===
    # ALPHABET_DIGITS must be the 10 digits in order.
    assert ALPHABET_DIGITS == "0123456789", (
        f"ALPHABET_DIGITS changed: {ALPHABET_DIGITS!r}"
    )
    # ALPHABET_ALNUM must be 36 chars: digits 0-9 then A-Z.
    assert len(ALPHABET_ALNUM) == 36, (
        f"ALPHABET_ALNUM length {len(ALPHABET_ALNUM)} != 36: {ALPHABET_ALNUM!r}"
    )
    assert ALPHABET_ALNUM == "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ", (
        f"ALPHABET_ALNUM changed: {ALPHABET_ALNUM!r}"
    )
    # Round-trip: ALPHABET_ALNUM[i] → i for i in [0..35]
    # This validates that the alphabet is index-aligned with _letter_value().
    for i, ch_at in enumerate(ALPHABET_ALNUM):
        if ch_at in _DIGITS_VALUES:
            assert _DIGITS_VALUES[ch_at] == i, (
                f"ALPHABET_ALNUM[{i}]={ch_at!r} digit value mismatch"
            )
        else:
            assert _LETTER_VALUES[ch_at] == i, (
                f"ALPHABET_ALNUM[{i}]={ch_at!r} letter value mismatch"
            )

    # === MOD_1271_36 two-char encoding round-trip ===
    # Pick any non-negative P < 36*36 = 1296 (the valid range for two
    # base-36 digits).
    P = fdp.ConsumeIntInRange(0, 1295)
    enc = ALPHABET_ALNUM[P // 36] + ALPHABET_ALNUM[P % 36]
    assert len(enc) == 2, (
        f"two-char encoding {enc!r} (P={P}) has wrong length {len(enc)}"
    )
    # Decode the two chars back to a value and confirm the round-trip.
    v0 = _letter_value(enc[0])
    v1 = _letter_value(enc[1])
    decoded = v0 * 36 + v1
    assert decoded == P, (
        f"two-char encoding round-trip failed: P={P}, "
        f"enc={enc!r}, v0={v0}, v1={v1}, decoded={decoded}"
    )


def main() -> int:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
