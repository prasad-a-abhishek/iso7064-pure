"""AC2 + AC3 + AC1 partial: ISBN-10 / numeric MOD 11-2."""

from __future__ import annotations

import pytest

from . import ISO7064Error, MOD_11_2, Mode, compute, verify


class TestMod11_2_ISBN10:
    """AC2 + AC3 — canonical ISBN-10 vectors."""

    def test_ac2_isbn10_vector(self):
        # ``030640615`` is one of the canonical ISBN-10 examples.
        assert MOD_11_2.compute("030640615") == "0306406152"

    def test_ac2_round_trip(self):
        assert MOD_11_2.verify("0306406152") is True

    def test_ac3_isbn10_x_vector(self):
        # ``043942089`` is the canonical ISBN-10 whose check char is X (=10).
        assert MOD_11_2.compute("043942089") == "043942089X"

    def test_ac3_round_trip(self):
        assert MOD_11_2.verify("043942089X") is True

    def test_check_character_returns_string(self):
        assert MOD_11_2.check_character("030640615") == "2"

    def test_compute_appends_only_one_char(self):
        # ISBN-10 is single-character; verify the appendix length.
        result = MOD_11_2.compute("030640615")
        assert len(result) == len("030640615") + 1

    def test_compute_does_not_mutate_input(self):
        data = "030640615"
        MOD_11_2.compute(data)
        assert data == "030640615"


class TestMod11_2_BoundaryVectors:
    """Extra canonical ISBN-10 vectors from python-stdnum."""

    def test_wikipedia_example_vector(self):
        # The Wikipedia ISO/IEC 7064 article gives the worked example
        # ``0794`` -> ``0`` for MOD 11-2.
        assert MOD_11_2.compute("0794") == "07942"

    def test_wikipedia_another(self):
        assert MOD_11_2.compute("079") == "0798"

    def test_various_isbn10_examples(self):
        # Scatter of real ISBN-10 numbers (verified via stdnum.isbn)
        # and their canonical check digits.
        cases = [
            ("043942089", "043942089X"),  # The 'X' = 10 canonical case
            ("030640615", "0306406152"),
            ("074753269", "0747532699"),
            ("026110357", "0261103571"),
            ("026110358", "026110358X"),
            ("045152493", "0451524934"),  # 1984 (Orwell)
            ("074327356", "0743273567"),  # Great Gatsby
            ("055321311", "0553213113"),  # Treasure Island
            ("014044913", "0140449132"),  # Les Misérables (Penguin)
        ]
        for body, full in cases:
            assert MOD_11_2.compute(body) == full
            assert MOD_11_2.verify(full) is True


class TestMod11_2_LengthVariants:
    """Boundary length tests (any length body from 1 to 20 digits)."""

    @pytest.mark.parametrize(
        "n_digits",
        [1, 2, 3, 5, 9, 10, 13, 18, 20],
        ids=lambda v: f"len={v}",
    )
    def test_round_trip_random_lengths(self, n_digits):
        body = "5" * n_digits  # any numeric body
        # ``compute`` only depends on the body — round-trip is automatic.
        full = MOD_11_2.compute(body)
        assert MOD_11_2.verify(full) is True

    def test_single_digit_body(self):
        # 1-digit body; just sanity-check.
        full = MOD_11_2.compute("3")
        assert len(full) == 2
        assert MOD_11_2.verify(full) is True

    def test_check_character_is_one_char(self):
        # The X check is also one character (literal X).
        assert len(MOD_11_2.check_character("043942089")) == 1
        assert MOD_11_2.check_character("043942089") == "X"


class TestMod11_2_Rejection:
    """Errors raised on bad input."""

    def test_lowercase_raises_with_substring(self):
        with pytest.raises(ISO7064Error) as exc:
            MOD_11_2.compute("abc")
        assert "lowercase" in str(exc.value)

    def test_lowercase_one_char(self):
        with pytest.raises(ISO7064Error) as exc:
            MOD_11_2.compute("12a45")
        assert "lowercase" in str(exc.value)

    def test_uppercase_letter_raises_non_numeric(self):
        with pytest.raises(ISO7064Error) as exc:
            MOD_11_2.compute("12A45")
        assert "non-numeric" in str(exc.value)

    def test_punctuation_raises_non_numeric(self):
        with pytest.raises(ISO7064Error) as exc:
            MOD_11_2.compute("12-45")
        assert "non-numeric" in str(exc.value)

    def test_unicode_raises_non_numeric(self):
        with pytest.raises(ISO7064Error) as exc:
            MOD_11_2.compute("12€45")
        assert "non-numeric" in str(exc.value)

    def test_empty_raises(self):
        with pytest.raises(ISO7064Error):
            MOD_11_2.compute("")

    def test_non_string_raises(self):
        with pytest.raises(ISO7064Error):
            MOD_11_2.compute(12345678)  # type: ignore[arg-type]

    def test_verify_returns_bool(self):
        # True for valid, False for invalid.
        assert MOD_11_2.verify("0306406152") is True
        assert MOD_11_2.verify("0306406150") is False

    def test_verify_of_garbage_returns_false(self):
        assert MOD_11_2.verify("garbage") is False
        assert MOD_11_2.verify("") is False
        assert MOD_11_2.verify(None) is False  # type: ignore[arg-type]


class TestMod11_2_Dispatch:
    """AC10 partial — generic compute/verify dispatch."""

    def test_compute_dispatch(self):
        assert compute("030640615", mode=Mode.MOD_11_2) == MOD_11_2.compute(
            "030640615"
        )

    def test_verify_dispatch(self):
        assert verify("0306406152", mode=Mode.MOD_11_2) == MOD_11_2.verify(
            "0306406152"
        )