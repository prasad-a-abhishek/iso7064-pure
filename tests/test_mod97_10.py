"""AC4: MOD 97-10 (IBAN)."""

from __future__ import annotations

import pytest

from . import ISO7064Error, MOD_97_10, Mode, compute, verify


class TestMod97_10_IBANCanonical:
    """AC4 — canonical SWIFT-published IBAN vector."""

    def test_ac4_valid_iban(self):
        assert MOD_97_10.verify("GB82WEST12345698765432") is True

    def test_ac4_invalid_iban(self):
        # One digit flipped in the BBAN portion (…98765499 instead of
        # …98765432). The exact IBAN specification calls for false here.
        assert MOD_97_10.verify("GB82WEST12345698765499") is False

    def test_compute_appends_two_digits(self):
        # Using ``GB00WEST12345698765432`` as the body with ``00`` placeholders.
        # ``compute`` replaces the placeholder at positions 2-3 with the
        # actual check digits, so the returned string is the same length
        # as the input (22 chars) and ends in the same last-2 characters
        # of the canonical IBAN (``...32``).
        full = MOD_97_10.compute("GB00WEST12345698765432")
        assert len(full) == 22  # replace, not append
        assert full.endswith("32")  # body's last 2 chars are unchanged
        # The replaced positions 2-3 hold the canonical check digits.
        assert full[2:4] == "82"

    def test_placeholder_compute_round_trip(self):
        body = "GB00WEST12345698765432"
        full = MOD_97_10.compute(body)
        assert MOD_97_10.verify(full) is True
        # Replacing the placeholder yields the canonical IBAN.
        assert full == "GB82WEST12345698765432"


class TestMod97_10_IBANExtra:
    """Extra canonical IBAN vectors for round-trip safety."""

    @pytest.mark.parametrize(
        "iban",
        [
            "GB82WEST12345698765432",
            "DE89370400440532013000",
            "FR1420041010050500013M02606",
            "GB29NWBK60161331926819",
            "GR1601101250000000012300695",
        ],
    )
    def test_external_ibans_verify(self, iban):
        # Known-valid IBANs from SWIFT / banking sample lists. We do not
        # ship any one as a hard-coded constant in the package; the
        # ``verify`` check is sufficient.
        assert MOD_97_10.verify(iban) is True

    @pytest.mark.parametrize(
        "iban",
        [
            "GB82WEST12345698765499",  # last 2 digits flipped from canonical
            "GB82WEST12345698765400",  # different mutation
            "GB82WEST123456987654",  # too short (no check)
        ],
    )
    def test_mutation_breaks_verify(self, iban):
        assert MOD_97_10.verify(iban) is False


class TestMod97_10_GenericMod97Ten:
    """The pure MOD 97-10 path (no IBAN rotation) for numeric inputs."""

    def test_numeric_input_no_rotation(self):
        # A pure-digit body that does not look like an IBAN.
        # The check digit is computed such that the full integer string
        # ``mod 97 == 1`` after the digit-flip.
        full = MOD_97_10.compute("12345678")
        assert MOD_97_10.verify(full) is True

    def test_check_characters_are_two_digits(self):
        check = MOD_97_10.check_character("12345678")
        assert len(check) == 2
        assert check.isdigit()


class TestMod97_10_Rejection:
    """AC9 partial — IBAN-only errors."""

    def test_lowercase_raises(self):
        with pytest.raises(ISO7064Error) as exc:
            MOD_97_10.compute("gb82west12345698765432")
        assert "lowercase" in str(exc.value)

    def test_punctuation_raises(self):
        # ``MOD_97_10`` is a numeric system; punctuation in any input
        # shape raises ``non-numeric`` (whether the input looks like an
        # IBAN or not).
        with pytest.raises(ISO7064Error) as exc:
            MOD_97_10.compute("GB82 WEST")
        assert "non-numeric" in str(exc.value)

    def test_empty_raises(self):
        with pytest.raises(ISO7064Error):
            MOD_97_10.compute("")

    def test_non_string_raises(self):
        with pytest.raises(ISO7064Error):
            MOD_97_10.compute(12345)  # type: ignore[arg-type]


class TestMod97_10_Dispatch:
    """AC10 partial."""

    def test_compute_dispatch(self):
        assert compute(
            "GB00WEST12345698765432", mode=Mode.MOD_97_10
        ) == MOD_97_10.compute("GB00WEST12345698765432")

    def test_verify_dispatch(self):
        assert verify("GB82WEST12345698765432", mode=Mode.MOD_97_10) == MOD_97_10.verify(
            "GB82WEST12345698765432"
        )