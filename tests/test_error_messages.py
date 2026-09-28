"""AC9 — error contract: all five systems surface consistent messages."""

from __future__ import annotations

import pytest

from . import ISO7064Error, Mode, compute, verify


class TestAllSystems_RejectionMessages:
    """AC9 — error substrings are part of the contract."""

    @pytest.mark.parametrize(
        "mode",
        [Mode.MOD_11_2, Mode.MOD_37_2, Mode.MOD_97_10, Mode.MOD_661_26, Mode.MOD_1271_36],
    )
    def test_lowercase_raises_lowercase_substring(self, mode):
        # Each system should reject lowercase input with a message that
        # contains the substring ``"lowercase"``.
        with pytest.raises(ISO7064Error) as exc:
            compute("abc", mode=mode)
        assert "lowercase" in str(exc.value)

    @pytest.mark.parametrize(
        "mode",
        [Mode.MOD_11_2, Mode.MOD_97_10],
    )
    def test_non_numeric_raises_non_numeric_substring(self, mode):
        # Numeric systems (MOD 11-2 + MOD 97-10) must reject non-numeric
        # input with a message containing ``"non-numeric"``.
        with pytest.raises(ISO7064Error) as exc:
            compute("12A45", mode=mode)
        assert "non-numeric" in str(exc.value)

    @pytest.mark.parametrize(
        "mode",
        [Mode.MOD_37_2, Mode.MOD_661_26, Mode.MOD_1271_36],
    )
    def test_non_alphanumeric_raises_non_alphanumeric_substring(self, mode):
        # Alphanumeric systems reject punctuation with a message
        # containing ``"non-alphanumeric"``.
        with pytest.raises(ISO7064Error) as exc:
            compute("AB CD", mode=mode)
        assert "non-alphanumeric" in str(exc.value)

    @pytest.mark.parametrize(
        "mode",
        [Mode.MOD_11_2, Mode.MOD_37_2, Mode.MOD_97_10, Mode.MOD_661_26, Mode.MOD_1271_36],
    )
    def test_empty_raises(self, mode):
        # Each system raises on the empty string.
        with pytest.raises(ISO7064Error):
            compute("", mode=mode)


class TestAllSystems_BoundaryCase:
    """Beyond the alphabetic-Z boundary the error must still trigger."""

    def test_unicode_character(self):
        # Anything outside the declared alphabet should trigger an error
        # with a descriptive substring.
        with pytest.raises(ISO7064Error) as exc:
            compute("12€45", mode=Mode.MOD_11_2)
        assert "non-numeric" in str(exc.value)

    def test_extended_unicode_alphanum(self):
        with pytest.raises(ISO7064Error) as exc:
            compute("HEL—O", mode=Mode.MOD_37_2)
        assert "non-alphanumeric" in str(exc.value)

    def test_newline_raises(self):
        with pytest.raises(ISO7064Error) as exc:
            compute("123\n456", mode=Mode.MOD_11_2)
        assert "non-numeric" in str(exc.value)


class TestAllSystems_VerifyReturnsBool:
    """AC9 partial — non-string inputs to ``verify`` must return False
    rather than raising."""

    @pytest.mark.parametrize(
        "mode",
        [Mode.MOD_11_2, Mode.MOD_37_2, Mode.MOD_97_10, Mode.MOD_661_26, Mode.MOD_1271_36],
    )
    def test_verify_non_string_returns_false(self, mode):
        assert verify(12345, mode=mode) is False  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        "mode",
        [Mode.MOD_11_2, Mode.MOD_37_2, Mode.MOD_97_10, Mode.MOD_661_26, Mode.MOD_1271_36],
    )
    def test_verify_empty_string_returns_false(self, mode):
        assert verify("", mode=mode) is False