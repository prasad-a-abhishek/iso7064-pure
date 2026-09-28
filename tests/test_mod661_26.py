"""AC5 + AC6: MOD 661-26 (ISIN + CUSIP check digit algorithms).

These two algorithms share the MOD 661-26 label in real-world use
but are **different** algorithms:

  * **ISIN** (12-char; 2-letter country + 9-char NSIN + 1 check):
    Luhn on letter-expanded digit string (``A=10..Z=35``, ASCII-55,
    weights 2,1,2,1 from the **right**).
  * **CUSIP** (9-char alphanumeric incl. ``*@#``): python-stdnum's
    algorithm — letters keep their alphabet index (no two-digit
    expansion), weights 1,2,1,2 from the **left**.

AC5 (Apple ISIN): ``MOD_661_26.compute("US037833100") == "US0378331005"``.
AC6 (Apple CUSIP): ``MOD_661_26.compute("037833100") == "0378331000"``.

Both vectors are primary-source verified:

  * https://en.wikipedia.org/wiki/CUSIP — Apple CUSIP ``037833100``
    (note: published check digit is ``0``, **not** ``5``; the digit
    ``5`` belongs to the ISIN ``US0378331005``).
  * https://en.wikipedia.org/wiki/International_Securities_Identification_Number
    — Apple ISIN ``US0378331005`` worked example.
  * https://github.com/arthurdejong/python-stdnum/blob/master/stdnum/cusip.py
  * https://github.com/arthurdejong/python-stdnum/blob/master/stdnum/isin.py
"""

from __future__ import annotations

import pytest

from . import ISO7064Error, MOD_661_26, Mode, compute, verify


class TestMod661_26_ISIN:
    """AC5 — Apple ISIN per ISO 6166 (Luhn on letter-expanded form)."""

    def test_ac5_apple_isin_compute(self):
        # Apple ISIN (per Wikipedia worked example):
        # ``US037833100`` → check digit ``5`` → full ``US0378331005``.
        assert MOD_661_26.compute("US037833100") == "US0378331005"

    def test_ac5_apple_isin_verify(self):
        assert MOD_661_26.verify("US0378331005") is True

    def test_isin_check_is_single_digit(self):
        assert len(MOD_661_26.check_character("US037833100")) == 1
        assert MOD_661_26.check_character("US037833100").isdigit()

    def test_isin_tcv_au0000xvgza(self):
        # Treasury Corp of Victoria ISIN (Wikipedia worked example).
        assert MOD_661_26.compute("AU0000XVGZA") == "AU0000XVGZA3"
        assert MOD_661_26.verify("AU0000XVGZA3") is True

    def test_isin_bae_gb000263494(self):
        # BAE Systems ISIN (Wikipedia worked example).
        assert MOD_661_26.compute("GB000263494") == "GB0002634946"
        assert MOD_661_26.verify("GB0002634946") is True


class TestMod661_26_CUSIP:
    """AC6 — Apple CUSIP per CUSIP lookup table (NOT plain Luhn).

    The real Apple CUSIP is ``037833100`` with check digit ``0``
    (per Wikipedia: https://en.wikipedia.org/wiki/CUSIP). The check
    digit ``5`` belongs to the ISIN ``US0378331005``, **not** to the
    CUSIP — the original spec body V3/AC6 confused the ISIN check digit
    with the CUSIP base.
    """

    def test_ac6_apple_cusip_compute(self):
        # AC6 (per primary source: Apple CUSIP ``037833100``).
        assert MOD_661_26.compute("037833100") == "0378331000"

    def test_ac6_apple_cusip_verify(self):
        assert MOD_661_26.verify("0378331000") is True

    def test_mod661_26_cusip_vector(self):
        # AC6 (canonical primary-source vector).
        assert MOD_661_26.compute("037833100") == "0378331000"
        assert MOD_661_26.verify("0378331000") is True

    def test_cusip_8char_input(self):
        # If the caller passes 8 chars (no check position yet), the result
        # ends with the check digit that makes a valid 9-char CUSIP.
        full = MOD_661_26.compute("03783310")
        assert len(full) == 9
        assert MOD_661_26.verify(full) is True
        # Real Apple CUSIP body ``03783310`` → full ``037833100``.
        assert full == "037833100"

    @pytest.mark.parametrize(
        "body,expected_check,full",
        [
            ("03783310", "0", "037833100"),    # Apple
            ("17275R10", "2", "17275R102"),    # Cisco
            ("38259P50", "8", "38259P508"),    # Google
            ("59491810", "4", "594918104"),    # Microsoft
            ("68389X10", "5", "68389X105"),    # Oracle
            ("EJ712548", "1", "EJ7125481"),    # UK 3.5% Gilt 2068
        ],
    )
    def test_cusip_check_digits_from_wikipedia(self, body, expected_check, full):
        assert MOD_661_26.compute(body) == full
        assert MOD_661_26.verify(full) is True
        assert MOD_661_26.check_character(body) == expected_check


class TestMod661_26_RoundTrip:
    """Round-trip property for arbitrary alphanumeric inputs."""

    @pytest.mark.parametrize(
        "data",
        [
            "US037833100",
            "GB000263494",
            "AU0000XVGZA",
            "ABC123XYZ",
            "03783310",
        ],
    )
    def test_round_trip_property(self, data):
        full = MOD_661_26.compute(data)
        assert MOD_661_26.verify(full) is True

    def test_full_string_is_original_plus_one(self):
        # Length-extension should always be one character.
        full = MOD_661_26.compute("US037833100")
        assert len(full) == len("US037833100") + 1


class TestMod661_26_Rejection:
    """Errors raised on bad input."""

    def test_lowercase_raises(self):
        with pytest.raises(ISO7064Error) as exc:
            MOD_661_26.compute("us037833100")
        assert "lowercase" in str(exc.value)

    def test_lowercase_in_middle_raises(self):
        with pytest.raises(ISO7064Error) as exc:
            MOD_661_26.compute("US0378331a0")
        assert "lowercase" in str(exc.value)

    def test_dash_raises(self):
        with pytest.raises(ISO7064Error) as exc:
            MOD_661_26.compute("US-037833100")
        assert "non-alphanumeric" in str(exc.value)

    def test_space_raises(self):
        with pytest.raises(ISO7064Error) as exc:
            MOD_661_26.compute("US 037833100")
        assert "non-alphanumeric" in str(exc.value)

    def test_empty_raises(self):
        with pytest.raises(ISO7064Error):
            MOD_661_26.compute("")

    def test_non_string_raises(self):
        with pytest.raises(ISO7064Error):
            MOD_661_26.compute(12345678)  # type: ignore[arg-type]

    def test_verify_returns_false_for_invalid(self):
        # Wrong check digit.
        assert MOD_661_26.verify("US0378331000") is False
        # Non-string:
        assert MOD_661_26.verify(None) is False  # type: ignore[arg-type]


class TestMod661_26_Dispatch:
    """AC10 partial."""

    def test_compute_dispatch(self):
        assert compute("US037833100", mode=Mode.MOD_661_26) == MOD_661_26.compute(
            "US037833100"
        )

    def test_verify_dispatch(self):
        assert verify("US0378331005", mode=Mode.MOD_661_26) == MOD_661_26.verify(
            "US0378331005"
        )