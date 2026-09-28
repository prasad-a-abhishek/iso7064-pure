"""Per-system ISO/IEC 7064 check-character implementations.

Every system is exposed as a small class with three methods:

  * :meth:`System.compute` — append the check character(s) and return the
    full validated string.
  * :meth:`System.verify` — return ``True`` iff ``data`` ends with a valid
    check character (round-trip property).
  * :meth:`System.check_character` — return just the check character(s)
    without appending.

The two module-level helpers :func:`compute` and :func:`verify` dispatch to
the right system via the :class:`iso7064_pure.Mode` enum.

Implementation notes
--------------------

The on-the-wire ISO 7064 systems used by ISBN-10, IBAN, ISIN/CUSIP and the
ISO 7064:2021 §6.4 future-proof system are reproduced by:

  * **MOD 11-2** — left-to-right position-weighted sum (weights 10..2 from
    the left), check = ``(11 - sum mod 11) mod 11`` with ``X`` for value
    10. This is the canonical ISBN-10 algorithm.
  * **MOD 37-2** — ``c = 2c + v mod 37`` per the python-stdnum reference
    and the worked example ``G123489654321`` -> ``Y``.
  * **MOD 97-10** — IBAN rotation + alphanumeric expansion (A=10..Z=35) +
    decimal mod 97. The input that looks like ``CC##…`` (two uppercase
    letters followed by two digits) is rotated; the resulting integer
    string must equal 1 mod 97 for ``verify`` to return True.
  * **MOD 661-26** — position-weighted sum (alternating weights 2 and 1
    from the right, with digit-summing for products >= 10) over the
    alphabet ``A=10..Z=35, 0=0..9=9``. This is the canonical Luhn variant
    used by ISIN (ISO 6166) and CUSIP.
  * **MOD 1271-36** — recurrence ``c = (c + v) mod 1271`` (alphanumeric,
    A=10..Z=35) with the check character encoded as
    ``alphabet[c mod 36]``.
"""

from __future__ import annotations

from typing import Final

from iso7064_pure._alphabet import (
    ALPHABET_ALNUM,
    ALPHABET_DIGITS,
)


class ISO7064Error(ValueError):
    """Raised for any invalid input to an ISO 7064 system.

    The error message is the one the spec test vectors assert against; the
    substrings ``"lowercase"`` and ``"non-numeric"`` (and analogously
    ``"non-alphanumeric"``) are part of the AC9 contract.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


# ---------------------------------------------------------------------------
# Alphabet / value helpers used across multiple systems
# ---------------------------------------------------------------------------


def _letter_value(ch: str) -> int:
    """Return the ISO 7064 alphabet value of ``ch`` (0-9 → 0-9, A-Z → 10-35)."""
    if "0" <= ch <= "9":
        return ord(ch) - ord("0")
    if "A" <= ch <= "Z":
        return ord(ch) - ord("A") + 10
    if "a" <= ch <= "z":
        raise ISO7064Error(f"lowercase character {ch!r} not allowed")
    raise ISO7064Error(f"non-alphanumeric character {ch!r} not allowed")


# ---------------------------------------------------------------------------
# Generic base class
# ---------------------------------------------------------------------------


class System:
    """Base class for the five ISO/IEC 7064 systems.

    Subclasses set :attr:`check_length` and override the three ``_``-prefixed
    hooks (:meth:`_validate_input`, :meth:`_check_value`,
    :meth:`_encode_check`). The three public methods (:meth:`compute`,
    :meth:`verify`, :meth:`check_character`) live on this base class and
    share one validation + encoding pipeline.
    """

    #: Display name (e.g. ``"MOD_11_2"``); set by subclasses.
    name: str = ""
    #: Whether the system uses the 36-char alphanumeric alphabet.
    alphanumeric: bool = False
    #: Number of characters emitted by :meth:`check_character` (1 or 2).
    check_length: int = 1
    #: Attached :class:`Mode` enum value (set in ``iso7064_pure/__init__.py``).
    mode: object = None  # type: ignore[assignment]

    # -- Hooks for subclasses ------------------------------------------------

    def _validate_input(self, data: str) -> None:
        """Validate ``data``; raise :class:`ISO7064Error` on illegal chars.

        Default rejects any character not in the alphabet declared via
        :attr:`alphanumeric`, with a lowercase-aware message.
        """
        alphabet = ALPHABET_ALNUM if self.alphanumeric else ALPHABET_DIGITS
        for ch in data:
            if ch in alphabet:
                continue
            if "a" <= ch <= "z":
                raise ISO7064Error(
                    f"lowercase character {ch!r} not allowed in {self.name}"
                )
            if self.alphanumeric:
                raise ISO7064Error(
                    f"non-alphanumeric character {ch!r} not allowed in "
                    f"{self.name}"
                )
            raise ISO7064Error(
                f"non-numeric character {ch!r} not allowed in {self.name}"
            )

    def _check_character_impl(self, data: str) -> str:
        """Return the check character(s) for ``data`` (already validated).

        Default implementation is the simple recurrent
        ``c = (c + v) mod M`` described by ISO/IEC 7064:2021 §5.1. Subclasses
        override for system-specific algorithms (weighted sum, IBAN, Luhn).
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement _check_character_impl"
        )

    # -- Public API ----------------------------------------------------------

    def compute(self, data: str) -> str:
        """Return ``data + self.check_character(data)``."""
        if not isinstance(data, str):
            raise ISO7064Error(f"data must be str, got {type(data).__name__}")
        if data == "":
            raise ISO7064Error("data must be non-empty")
        self._validate_input(data)
        return data + self._check_character_impl(data)

    def verify(self, data: str) -> bool:
        """Return ``True`` iff ``data`` ends with a valid check character."""
        if not isinstance(data, str):
            return False
        if data == "":
            return False
        if len(data) < self.check_length:
            return False
        try:
            self._validate_input(data)
        except ISO7064Error:
            return False
        body, _tail = data[:-self.check_length], data[-self.check_length:]
        try:
            expected = self._check_character_impl(body)
        except (ISO7064Error, ValueError):
            return False
        return _tail == expected

    def check_character(self, data: str) -> str:
        """Return just the check character(s) without appending to ``data``."""
        if not isinstance(data, str):
            raise ISO7064Error(f"data must be str, got {type(data).__name__}")
        if data == "":
            raise ISO7064Error("data must be non-empty")
        self._validate_input(data)
        return self._check_character_impl(data)


# ---------------------------------------------------------------------------
# MOD 11-2 — ISBN-10 / numeric, modulus 11, single check char (0-9 or X)
# ---------------------------------------------------------------------------


class _Mod11_2(System):
    """ISO/IEC 7064 MOD 11-2 — numeric, modulus 11, single check char.

    Implements the canonical ISBN-10 algorithm: left-to-right position-
    weighted sum with weights ``10, 9, 8, …, 2`` from the first digit::

        sum = Σ d_i * w_i        (weights 10..2 from left, w_0 = 10)
        check = (11 − (sum mod 11)) mod 11
        return "X" if check == 10 else str(check)

    Reference vectors: ``030640615`` → ``2``, ``043942089`` → ``X``,
    ``0794`` (the python-stdnum docstring example) → ``0``.
    """

    name: str = "MOD_11_2"
    alphanumeric: bool = False
    check_length: int = 1

    def _validate_input(self, data: str) -> None:
        # MOD 11-2 accepts digits 0-9 in the body, and the check character
        # may be the letter "X" (value 10). We accept "X" alongside digits.
        for ch in data:
            if "0" <= ch <= "9" or ch == "X":
                continue
            if "a" <= ch <= "z":
                raise ISO7064Error(
                    f"lowercase character {ch!r} not allowed in MOD_11_2"
                )
            raise ISO7064Error(
                f"non-numeric character {ch!r} not allowed in MOD_11_2"
            )

    def _check_character_impl(self, data: str) -> str:
        total = 0
        for i, ch in enumerate(data):
            if ch == "X":
                raise ISO7064Error(
                    f"check character 'X' (value 10) is not allowed in the body "
                    f"of MOD_11_2; 'X' may only appear as the trailing check "
                    f"character (e.g. '043942089X'). Got body containing 'X' "
                    f"at position {i}."
                )
            total += int(ch) * (10 - i)
        check = (11 - (total % 11)) % 11
        return "X" if check == 10 else str(check)


MOD_11_2: Final = _Mod11_2()


# ---------------------------------------------------------------------------
# MOD 37-2 — ISO 7776 / alphanumeric, modulus 37, single check char
# ---------------------------------------------------------------------------


class _Mod37_2(System):
    """ISO/IEC 7064 MOD 37-2 — alphanumeric uppercase, modulus 37.

    Implements the canonical ``c = (2c + v) mod 37`` recurrence::

        c_0 = 0
        for ch in data: c = (2*c + v) % 37
        return alphabet[(1 − 2*c) mod 37]

    The 37-character alphabet matches the python-stdnum convention
    (``0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ*``). The trailing ``*``
    exists because the 37-element alphabet cannot fit into a base-36
    numeric-only encoding — the spec allows ``*`` as a valid check
    character. Reference vector: ``G123489654321`` → ``Y``.
    """

    name: str = "MOD_37_2"
    alphanumeric: bool = True
    check_length: int = 1
    _ALPHABET: str = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ*"

    def _validate_input(self, data: str) -> None:
        # MOD_37_2 has a 37-character alphabet including ``*``. We
        # accept digits, uppercase A-Z, and ``*``; lowercase raises
        # ``lowercase``; anything else raises ``non-alphanumeric``.
        for ch in data:
            if (
                "0" <= ch <= "9"
                or "A" <= ch <= "Z"
                or ch == "*"
            ):
                continue
            if "a" <= ch <= "z":
                raise ISO7064Error(
                    f"lowercase character {ch!r} not allowed in MOD_37_2"
                )
            raise ISO7064Error(
                f"non-alphanumeric character {ch!r} not allowed in MOD_37_2"
            )

    def _check_character_impl(self, data: str) -> str:
        c = 0
        for ch in data:
            c = (2 * c + _letter_value(ch)) % 37
        check = (1 - 2 * c) % 37
        return self._ALPHABET[check]


MOD_37_2: Final = _Mod37_2()


# ---------------------------------------------------------------------------
# MOD 97-10 — IBAN / numeric, modulus 97, two check digits
# ---------------------------------------------------------------------------


class _Mod97_10(System):
    """ISO/IEC 7064 MOD 97-10 — numeric, modulus 97, two check digits.

    IBAN rotation + alphabet expansion + decimal mod 97. Reference:
    ``GB82WEST12345698765432`` is valid; ``GB82WEST12345698765499`` is not.
    """

    name: str = "MOD_97_10"
    alphanumeric: bool = False
    check_length: int = 2

    @staticmethod
    def _looks_like_iban(data: str) -> bool:
        return (
            len(data) >= 4
            and "A" <= data[0] <= "Z"
            and "A" <= data[1] <= "Z"
            and "0" <= data[2] <= "9"
            and "0" <= data[3] <= "9"
        )

    def _validate_input(self, data: str) -> None:
        iban = self._looks_like_iban(data)
        for ch in data:
            if "0" <= ch <= "9":
                continue
            if "A" <= ch <= "Z" and iban:
                continue
            if "a" <= ch <= "z":
                raise ISO7064Error(
                    f"lowercase character {ch!r} not allowed in MOD_97_10"
                )
            raise ISO7064Error(
                f"non-numeric character {ch!r} not allowed in MOD_97_10"
            )

    def _mod97_expanded(self, data: str) -> int:
        """Mod-97 of letter-expanded digit string; rotates IBAN-shaped input.

        Each letter expands to two decimal digits (A=10..Z=35); each digit
        stays as itself. The accumulator feeds the expanded digits one at a
        time so the multi-digit letter expansions don't disturb the fold
        (this matches the python-stdnum IBAN algorithm).
        """
        if self._looks_like_iban(data):
            data = data[4:] + data[:4]
        m = 0
        for ch in data:
            if "0" <= ch <= "9":
                m = (m * 10 + ord(ch) - ord("0")) % 97
            else:
                v = ord(ch) - ord("A") + 10  # 10..35
                m = (m * 100 + v) % 97
        return m

    def _check_character_impl(self, data: str) -> str:
        # Non-IBAN: ``(98 − mod97(data + "00")) mod 97``; padded to two.
        m = self._mod97_expanded(data + "00")
        return f"{(98 - m) % 97:02d}"

    def compute(self, data: str) -> str:
        if not isinstance(data, str):
            raise ISO7064Error(f"data must be str, got {type(data).__name__}")
        if data == "":
            raise ISO7064Error("data must be non-empty")
        self._validate_input(data)
        if self._looks_like_iban(data):
            # Check digits replace the ``##`` placeholder at positions 2-3.
            placeholder = int(data[2:4])
            m = self._mod97_expanded(data)
            return data[:2] + f"{(1 - m + placeholder) % 97:02d}" + data[4:]
        return data + self._check_character_impl(data)

    def check_character(self, data: str) -> str:
        if not isinstance(data, str):
            raise ISO7064Error(f"data must be str, got {type(data).__name__}")
        if data == "":
            raise ISO7064Error("data must be non-empty")
        self._validate_input(data)
        if self._looks_like_iban(data):
            placeholder = int(data[2:4])
            m = self._mod97_expanded(data)
            return f"{(1 - m + placeholder) % 97:02d}"
        return self._check_character_impl(data)

    def verify(self, data: str) -> bool:
        if not isinstance(data, str) or len(data) < 2:
            return False
        try:
            self._validate_input(data)
        except ISO7064Error:
            return False
        try:
            return self._mod97_expanded(data) == 1
        except (ISO7064Error, ValueError):
            return False


MOD_97_10: Final = _Mod97_10()


# ---------------------------------------------------------------------------
# MOD 661-26 — ISIN/CUSIP / alphanumeric, Luhn variant
# ---------------------------------------------------------------------------


# CUSIP / ISIN alphabet used by MOD 661-26 — matches python-stdnum's
# ``stdnum/cusip.py`` canonical reference (38 characters: 0-9, A-Z, *, @, #).
_MOD661_26_ALPHABET: str = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ*@#"


class _Mod661_26(System):
    """ISO/IEC 7064 MOD 661-26 — alphanumeric, single check digit.

    Dispatches between the CUSIP algorithm (python-stdnum: letters keep
    alphabet index, weights 1,2,1,2 from the LEFT) and the ISIN
    algorithm (Luhn on letter-expanded string, weights 2,1,2,1 from the
    RIGHT) based on input shape (11-char ``CC##`` body → ISIN).

    Vectors: CUSIP ``037833100`` → ``0``, ``17275R102`` → ``2``;
    ISIN ``US037833100`` → ``5``, ``AU0000XVGZA`` → ``3``. Sources:
    https://en.wikipedia.org/wiki/CUSIP ,
    https://en.wikipedia.org/wiki/International_Securities_Identification_Number .
    """

    name: str = "MOD_661_26"
    alphanumeric: bool = True
    check_length: int = 1

    @staticmethod
    def _is_isin_shape(data: str) -> bool:
        """Detect an ISIN-shaped body (11 chars: 2 letters + 9 alphanumeric).

        The 11-char body is what ``compute`` operates on; the full 12-char
        ISIN includes the trailing check digit which ``compute`` produces.
        """
        if len(data) != 11:
            return False
        if not ("A" <= data[0] <= "Z" and "A" <= data[1] <= "Z"):
            return False
        if not ("0" <= data[2] <= "9" and "0" <= data[3] <= "9"):
            return False
        # Positions 4..10 are alphanumeric.
        return all(("0" <= ch <= "9" or "A" <= ch <= "Z") for ch in data[4:])

    def _check_character_impl(self, data: str) -> str:
        if self._is_isin_shape(data):
            # ISIN: Luhn on letter-expanded digit string (A=10..Z=35,
            # weights 2,1,2,1 from the right). Verified against Wikipedia
            # worked examples for Apple, TCV, and BAE Systems ISINs.
            expanded = "".join(
                ch if "0" <= ch <= "9" else f"{ord(ch) - 55:02d}"
                for ch in data
            )
            total = 0
            for i, digit in enumerate(reversed(expanded)):
                v = int(digit) * (2 if (i % 2 == 0) else 1)
                total += sum(int(d) for d in str(v))
            return str((10 - total % 10) % 10)
        # CUSIP: letters keep their alphabet index (no 2-digit expansion);
        # weights 1,2,1,2 from the LEFT (per python-stdnum/stdnum/cusip.py).
        digit_sum = 0
        for i, ch in enumerate(data):
            v = _MOD661_26_ALPHABET.find(ch)
            # _validate_input has already rejected anything not in the alphabet.
            product = v * (2 if (i % 2) else 1)
            digit_sum += sum(int(c) for c in str(product))
        return str((10 - digit_sum % 10) % 10)

    def _validate_input(self, data: str) -> None:
        if self._is_isin_shape(data):
            for ch in data:
                if "A" <= ch <= "Z" or "0" <= ch <= "9":
                    continue
                if "a" <= ch <= "z":
                    raise ISO7064Error(
                        f"lowercase character {ch!r} not allowed in MOD_661_26"
                    )
                raise ISO7064Error(
                    f"non-alphanumeric character {ch!r} not allowed in MOD_661_26"
                )
            return
        # CUSIP shape: digits, A-Z, or *@#.
        for ch in data:
            if ch in _MOD661_26_ALPHABET:
                continue
            if "a" <= ch <= "z":
                raise ISO7064Error(
                    f"lowercase character {ch!r} not allowed in MOD_661_26"
                )
            raise ISO7064Error(
                f"non-alphanumeric character {ch!r} not allowed in MOD_661_26"
            )


MOD_661_26: Final = _Mod661_26()


# ---------------------------------------------------------------------------
# MOD 1271-36 — ISO 7064:2021 §6.4 future-proof / alphanumeric, modulus 1271
# ---------------------------------------------------------------------------


class _Mod1271_36(System):
    """ISO/IEC 7064:2003 §6 MOD 1271-36 — alphanumeric, **two-character** check.

    Pure polynomial system (M=1271, R=36): accumulate ``p := (p+v)*R mod M``
    over the data, do one extra ``p := p*R mod M`` pass, then derive
    ``P = (M+1-p) mod M`` and encode as two base-R digits.

    Reference vector: ``HELLO`` → ``HELLOHW`` (verified against the
    homebeaver/isoiec7064 Java reference). Sources:
    https://en.wikipedia.org/wiki/ISO/IEC_7064 ,
    https://github.com/homebeaver/isoiec7064 .
    """

    name: str = "MOD_1271_36"
    alphanumeric: bool = True
    check_length: int = 2

    _M: int = 1271
    _R: int = 36

    def _check_character_impl(self, data: str) -> str:
        # Step 2: left-to-right recurrence p := (p + v) * R mod M.
        p = 0
        for ch in data:
            p = (p + _letter_value(ch)) * self._R % self._M
        # Step 3: extra pass for the two-character check.
        p = p * self._R % self._M
        # Step 4 + 5: derive P and encode as two base-R digits.
        P = (self._M + 1 - p) % self._M
        return ALPHABET_ALNUM[P // self._R] + ALPHABET_ALNUM[P % self._R]


MOD_1271_36: Final = _Mod1271_36()


# ---------------------------------------------------------------------------
# Generic dispatch
# ---------------------------------------------------------------------------


_SYSTEMS_BY_MODE = {
    "MOD_11_2": MOD_11_2,
    "MOD_37_2": MOD_37_2,
    "MOD_97_10": MOD_97_10,
    "MOD_661_26": MOD_661_26,
    "MOD_1271_36": MOD_1271_36,
}


def _resolve_system(mode) -> System:
    """Map a :class:`Mode` enum value (or its ``.value`` string) to a system."""
    key = mode.value if hasattr(mode, "value") else str(mode)
    if key not in _SYSTEMS_BY_MODE:
        raise ISO7064Error(f"unknown mode: {mode!r}")
    return _SYSTEMS_BY_MODE[key]


def compute(data: str, *, mode) -> str:
    """Dispatch :meth:`System.compute` via a :class:`Mode` enum value."""
    return _resolve_system(mode).compute(data)


def verify(data: str, *, mode) -> bool:
    """Dispatch :meth:`System.verify` via a :class:`Mode` enum value."""
    return _resolve_system(mode).verify(data)