"""AC8: MOD 37-2 (alphanumeric, ISO 7776)."""

from __future__ import annotations

import pytest

from . import ISO7064Error, MOD_37_2, Mode, compute, verify


class TestMod37_2_Canonical:
    """AC8 partial — known reference vectors."""

    def test_stdnum_vector(self):
        # The python-stdnum ``mod_37_2`` module documents the worked example
        # ``G123489654321`` -> ``Y``.
        assert MOD_37_2.compute("G123489654321") == "G123489654321Y"
        assert MOD_37_2.verify("G123489654321Y") is True

    def test_hello_round_trip(self):
        # AC8 demands a round-trip on ``HELLO`` specifically.
        full = MOD_37_2.compute("HELLO")
        assert MOD_37_2.verify(full) is True

    def test_hello_check_char_is_alnum(self):
        check = MOD_37_2.check_character("HELLO")
        assert len(check) == 1
        assert check in "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ*"

    def test_check_character_returns_one_char(self):
        assert len(MOD_37_2.check_character("HELLO")) == 1


class TestMod37_2_RoundTrip:
    """AC8 — round-trip property for arbitrary inputs."""

    @pytest.mark.parametrize(
        "data",
        [
            "HELLO",
            "HELLOWORLD",
            "A",
            "ABC",
            "1234567890",
            "ABCDEF12345",
            "ZZZZZZZZ",
            "00000000",
            "FOO",
            "BAR123",
        ],
    )
    def test_round_trip(self, data):
        full = MOD_37_2.compute(data)
        assert MOD_37_2.verify(full) is True
        assert len(full) == len(data) + 1

    def test_full_string_matches_compute_output(self):
        data = "HELLO"
        assert MOD_37_2.verify(MOD_37_2.compute(data)) is True
        # Also confirm the explicit ``check_character`` round-trip path.
        assert MOD_37_2.verify(data + MOD_37_2.check_character(data)) is True


class TestMod37_2_DigitOnly:
    """Digits-only input is also accepted."""

    @pytest.mark.parametrize("body", ["0", "1", "123", "9876543210"])
    def test_digit_only_round_trip(self, body):
        full = MOD_37_2.compute(body)
        assert MOD_37_2.verify(full) is True


class TestMod37_2_Rejection:
    """AC9 partial — lowercase + non-alphanumeric errors."""

    def test_lowercase_raises(self):
        with pytest.raises(ISO7064Error) as exc:
            MOD_37_2.compute("hello")
        assert "lowercase" in str(exc.value)

    def test_lowercase_single_char_raises(self):
        with pytest.raises(ISO7064Error) as exc:
            MOD_37_2.compute("ABCdEF")
        assert "lowercase" in str(exc.value)

    def test_punctuation_raises(self):
        with pytest.raises(ISO7064Error) as exc:
            MOD_37_2.compute("AB CD")
        assert "non-alphanumeric" in str(exc.value)

    def test_punctuation_raises_other_form(self):
        with pytest.raises(ISO7064Error) as exc:
            MOD_37_2.compute("AB!")
        assert "non-alphanumeric" in str(exc.value)

    def test_empty_raises(self):
        with pytest.raises(ISO7064Error):
            MOD_37_2.compute("")

    def test_non_string_raises(self):
        with pytest.raises(ISO7064Error):
            MOD_37_2.compute(b"BYTES")  # type: ignore[arg-type]

    def test_verify_garbage_returns_false(self):
        assert MOD_37_2.verify("") is False
        assert MOD_37_2.verify("garbage?") is False


class TestMod37_2_Dispatch:
    """AC10 partial."""

    def test_compute_dispatch(self):
        assert compute("G123489654321", mode=Mode.MOD_37_2) == MOD_37_2.compute(
            "G123489654321"
        )

    def test_verify_dispatch(self):
        assert verify("G123489654321Y", mode=Mode.MOD_37_2) == MOD_37_2.verify(
            "G123489654321Y"
        )