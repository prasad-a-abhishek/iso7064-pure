"""AC1: import smoke + package metadata.

This module asserts that ``iso7064_pure`` imports cleanly from a fresh
sys.path (no external installation required) and that the package
metadata is present.
"""

from __future__ import annotations

from . import (
    ALPHABET_ALNUM,
    ALPHABET_DIGITS,
    ISO7064Error,
    MOD_11_2,
    MOD_97_10,
    Mode,
    System,
    __version__,
    compute,
    verify,
)


class TestImportSmoke:
    """AC1."""

    def test_version_is_string(self):
        assert isinstance(__version__, str)
        assert __version__  # non-empty

    def test_alphabet_constants_defined(self):
        # Digits + A-Z alphanumeric; ``*`` belongs only to MOD_37_2's
        # internal alphabet, not to the public module constants.
        assert ALPHABET_DIGITS == "0123456789"
        assert ALPHABET_ALNUM == "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        assert len(ALPHABET_DIGITS) == 10
        assert len(ALPHABET_ALNUM) == 36

    def test_singletons_are_systems(self):
        for sys_ in (MOD_11_2, MOD_97_10):
            assert isinstance(sys_, System)

    def test_mode_enum_has_five_members(self):
        assert set(m.value for m in Mode) == {
            "MOD_11_2",
            "MOD_37_2",
            "MOD_97_10",
            "MOD_661_26",
            "MOD_1271_36",
        }
        assert len(list(Mode)) == 5

    def test_dispatch_helpers_present(self):
        assert callable(compute)
        assert callable(verify)
        assert callable(MOD_11_2.compute)
        assert callable(MOD_11_2.verify)

    def test_iso7064_error_is_value_error(self):
        # ISO7064Error must be a ValueError subclass so callers can catch it
        # as a generic ValueError.
        assert issubclass(ISO7064Error, ValueError)
        e = ISO7064Error("test")
        assert e.message == "test"
        assert str(e) == "test"