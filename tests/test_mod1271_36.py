"""AC7: MOD 1271-36 (ISO/IEC 7064:2003 §6 polynomial future-proof system).

The MOD 1271-36 system defined in ISO/IEC 7064:2003 §6 (carried forward
to the 2021 edition) is a **two-character** alphanumeric check digit
system with M=1271 and R=36.

Canonical algorithm:

  1. Character values: digits 0-9 → 0-9; A=10 .. Z=35.
  2. Accumulate: ``p := (p + v) * R mod M`` over the data.
  3. Extra pass: ``p := p * R mod M`` (room for 2 check chars).
  4. Check value: ``P = (M + 1 - p) mod M``.
  5. Encode as two base-R digits: ``P//R`` and ``P%R``.

Reference vector: ``HELLO`` → ``HW`` → full ``HELLOHW``.

Sources:

  * https://en.wikipedia.org/wiki/ISO/IEC_7064
  * https://de.wikipedia.org/wiki/ISO/IEC_7064 (§6 worked example)
  * https://github.com/homebeaver/isoiec7064 (Java reference)
"""

from __future__ import annotations

import pytest

from iso7064_pure import ALPHABET_ALNUM

from . import ISO7064Error, MOD_1271_36, Mode, compute, verify


class TestMod1271_36_RoundTrip:
    """AC7 partial — round-trip property holds for any alphanumeric input."""

    @pytest.mark.parametrize(
        "data",
        [
            "HELLO",
            "WORLD",
            "AB",
            "ABCD",
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            "ABCDEF12345",
            "ZZZZZZZZZZ",
            "0",
            "1",
            "1234567890",
        ],
    )
    def test_round_trip_property(self, data):
        full = MOD_1271_36.compute(data)
        assert MOD_1271_36.verify(full) is True
        # Two-character check length: full = data + 2 chars.
        assert len(full) == len(data) + 2

    def test_hello_check_is_two_chars(self):
        check = MOD_1271_36.check_character("HELLO")
        assert len(check) == 2
        assert all(c in ALPHABET_ALNUM for c in check)

    def test_hello_compute_format(self):
        # The compute output preserves the original body and appends a
        # two-character check.
        result = MOD_1271_36.compute("HELLO")
        assert result.startswith("HELLO")
        assert len(result) == 7

    def test_mod1271_36_iso_vector(self):
        # AC7 — canonical ISO/IEC 7064:2003 §6 worked example for HELLO.
        # Two-character check ``HW``, full string ``HELLOHW`` (verified
        # against the homebeaver/isoiec7064 Java reference).
        assert MOD_1271_36.compute("HELLO") == "HELLOHW"
        assert MOD_1271_36.verify("HELLOHW") is True

    def test_mod1271_36_world_vector(self):
        # WORLD → ``WORLDC6`` per the canonical recurrence.
        assert MOD_1271_36.compute("WORLD") == "WORLDC6"
        assert MOD_1271_36.verify("WORLDC6") is True


class TestMod1271_36_Deterministic:
    """Determinism — the same input always yields the same check."""

    def test_deterministic_compute(self):
        results = {MOD_1271_36.compute("HELLO") for _ in range(20)}
        assert len(results) == 1

    def test_deterministic_verify(self):
        full = MOD_1271_36.compute("HELLO")
        results = {MOD_1271_36.verify(full) for _ in range(20)}
        assert len(results) == 1


class TestMod1271_36_Rejection:
    """Errors raised on bad input."""

    def test_lowercase_raises(self):
        with pytest.raises(ISO7064Error) as exc:
            MOD_1271_36.compute("hello")
        assert "lowercase" in str(exc.value)

    def test_punctuation_raises(self):
        with pytest.raises(ISO7064Error) as exc:
            MOD_1271_36.compute("HELLO!")
        assert "non-alphanumeric" in str(exc.value)

    def test_empty_raises(self):
        with pytest.raises(ISO7064Error):
            MOD_1271_36.compute("")

    def test_non_string_raises(self):
        with pytest.raises(ISO7064Error):
            MOD_1271_36.compute(b"HELLO")  # type: ignore[arg-type]


class TestMod1271_36_Dispatch:
    """AC10 partial."""

    def test_compute_dispatch(self):
        assert compute("HELLO", mode=Mode.MOD_1271_36) == MOD_1271_36.compute(
            "HELLO"
        )

    def test_verify_dispatch(self):
        out = MOD_1271_36.compute("HELLO")
        assert verify(out, mode=Mode.MOD_1271_36) == MOD_1271_36.verify(out)