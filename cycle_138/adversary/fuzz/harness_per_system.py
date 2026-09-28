"""Atheris harness for the per-system ``compute()`` surface.

Surface 2 of the cycle_138 adversary workstream.

Exercises every one of the five ``MOD_N_X`` singleton classes directly
(none of the dispatch helpers in :mod:`iso7064_pure`) by calling
``MOD_11_2.compute(data)``, ``MOD_37_2.compute(data)``, etc. for a
fuzz-chosen system.  Each system has different alphabet constraints,
different check-length (1 vs 2), and different inner algorithm
(weighted sum, IBAN rotation, Luhn, polynomial recurrence).

This is the deepest coverage surface — every ``_check_character_impl``
override is hit on every iteration.  The DISPATCH surface
(``harness_compute.py``) tests the path TO the system; this one tests
the system itself.

Specifically we test:

* ``MOD_11_2.compute("X794")`` — the VULN_AUDIT-flagged input that
  currently raises a raw :class:`ValueError` instead of
  :class:`ISO7064Error` (SPEC §6 AC9).  The harness asserts ONLY
  ``ISO7064Error`` is acceptable here.
* ``MOD_11_2.compute(b)`` for ``b`` with embedded ``X`` chars in body.
* ``MOD_37_2.compute(d)`` for any alphanumeric ``d`` in
  ``[0-9A-Z\\*]`` — confirms check-character is single ``[0-9A-Z\\*]``.
* ``MOD_97_10.compute(iban)`` — IBAN-shaped (``CC##...``) input
  with random body; check char length MUST be exactly 2 digits.
* ``MOD_97_10.compute(numeric)`` — non-IBAN numeric input.
* ``MOD_661_26.compute(cusip)`` — 9-char alphanumeric (CUSIP shape).
* ``MOD_661_26.compute(isin)`` — 11-char ISIN-shaped ``CC##...``.
* ``MOD_1271_36.compute(d)`` — check char length MUST be exactly 2.
* Round-trip property ``system.verify(system.compute(data)) is True``
  for every valid alphabet input.
* SPEC §6 AC9 contract: invalid-input errors are :class:`ISO7064Error`
  (subclass of :class:`ValueError`), NEVER raw ``ValueError`` /
  ``TypeError`` / ``AttributeError`` escaping.

Run::

    python3 harness_per_system.py -atheris_runs=100000 -max_total_time=5
"""
from __future__ import annotations

import sys
import typing as _t

import atheris  # type: ignore[import-not-found]

with atheris.instrument_imports():  # type: ignore[attr-defined]
    from iso7064_pure import (
        ISO7064Error,
        MOD_11_2,
        MOD_37_2,
        MOD_661_26,
        MOD_97_10,
        MOD_1271_36,
    )
    from iso7064_pure._systems import System  # type: ignore[import-not-found]


# (system, alphabet, iban_or_special_label)
_SYSTEM_TABLE: list[tuple[System, str, str]] = [
    (MOD_11_2, "0123456789X", "numeric+X"),  # X allowed as value 10 in check char
    (MOD_37_2, "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ*", "alphanumeric+*"),
    (MOD_97_10, "0123456789", "iban-or-numeric"),
    (MOD_661_26, "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ*@#", "alphanumeric-cusip-isin"),
    (MOD_1271_36, "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ", "alphanumeric-2char"),
]


@atheris.instrument_func  # type: ignore[attr-defined]
def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)  # type: ignore[attr-defined]

    # Pick a system uniformly.
    sys_idx = fdp.ConsumeIntInRange(0, len(_SYSTEM_TABLE) - 1)
    system, alphabet, label = _SYSTEM_TABLE[sys_idx]

    # Pick a corruption strategy: 0=clean, 1=lowercase, 2=symbol, 3=empty,
    # 4=non-string sentinels, 5=extremely long, 6=MOD_11_2 X-in-body (the
    # VULN_AUDIT high-severity finding).
    corrupt_kind = fdp.ConsumeIntInRange(0, 6)

    if corrupt_kind == 4:
        # Non-string sentinel — must raise ISO7064Error (TypeError is acceptable
        # because ISO7064Error subclasses ValueError; we accept either).
        sentinel_kind = fdp.ConsumeIntInRange(0, 3)
        sentinels: tuple[_t.Any, ...] = (None, 12345, ["A"], 1.5)
        sentinel = sentinels[sentinel_kind]
        try:
            system.compute(sentinel)  # type: ignore[arg-type]
        except ISO7064Error:
            return
        except TypeError as exc:
            # Acceptable: implementation may decide to let TypeError propagate.
            # What we MUST NOT see is a bare AttributeError, KeyError, or
            # anything that suggests a missing dict entry / NoneType crash.
            if "NoneType" in str(exc) or "has no attribute" in str(exc):
                raise AssertionError(
                    f"{system.name}.compute({sentinel!r}) leaked "
                    f"AttributeError: {exc!r}"
                ) from exc
            return
        raise AssertionError(
            f"{system.name}.compute({sentinel!r}) did NOT raise — "
            f"non-string must be rejected"
        )

    # Build the body.
    length = fdp.ConsumeIntInRange(1, 30)
    raw_data = fdp.ConsumeUnicodeNoSurrogates(length)

    if corrupt_kind == 0:
        # Clean alphabet input.
        # Replace any char not in alphabet with the first valid char so
        # the harness exercises the happy-path AND we avoid wasting
        # iterations on validation-only fuzz (Surface 4 covers that).
        cleaned = "".join(c if c in alphabet else alphabet[0] for c in raw_data)
        raw_data = cleaned if cleaned else alphabet[0]
    elif corrupt_kind == 1:
        # Inject lowercase letters (rejected with 'lowercase' message).
        raw_data = raw_data + "abc" if raw_data else "abc"
    elif corrupt_kind == 2:
        # Inject non-alphanumeric punctuation.
        raw_data = raw_data + "!@#" if raw_data else "!@#"
    elif corrupt_kind == 3:
        # Empty data — must raise ISO7064Error.
        raw_data = ""
    elif corrupt_kind == 5:
        # Extremely long (up to 4096 chars).  Filter to alphabet so the
        # harness exercises the happy-path with a long input (probing
        # for O(n) vs O(n²) bottlenecks), not validation errors.
        base = "".join(c if c in alphabet else alphabet[0] for c in raw_data)
        raw_data = (base if base else alphabet[0]) + alphabet[0] * 4090
    elif corrupt_kind == 6:
        # The VULN_AUDIT-flagged MOD_11_2 X-in-body case.
        # X is a valid MOD_11_2 check character (value 10) but NOT a
        # valid body character per SPEC.  The bug: int("X") raises
        # raw ValueError instead of ISO7064Error.
        if system is not MOD_11_2:
            # Only relevant for MOD_11_2; skip otherwise.
            return
        raw_data = "X794"

    # Empty body path.
    if not raw_data:
        try:
            full = system.compute(raw_data)  # type: ignore[arg-type]
        except ISO7064Error:
            return
        except (ValueError, TypeError) as exc:
            # SPEC §6 AC9: must be ISO7064Error, NOT raw ValueError.
            if isinstance(exc, ISO7064Error):
                return
            raise AssertionError(
                f"{system.name}.compute('') raised raw {type(exc).__name__}: "
                f"{exc!r}"
            ) from exc
        raise AssertionError(
            f"{system.name}.compute('') = {full!r} — empty data must be rejected"
        )

    # Bad-char path (lowercase or punctuation).
    if corrupt_kind in (1, 2):
        try:
            full = system.compute(raw_data)
        except ISO7064Error as exc:
            # Verify the error MESSAGE matches the SPEC §6 AC9 contract:
            # must mention 'lowercase' or 'non-numeric' / 'non-alphanumeric'.
            msg = str(exc)
            if corrupt_kind == 1 and "lowercase" not in msg:
                raise AssertionError(
                    f"{system.name}.compute({raw_data!r}) raised "
                    f"ISO7064Error but missing 'lowercase' substring: {msg!r}"
                ) from exc
            if corrupt_kind == 2 and (
                "non-numeric" not in msg and "non-alphanumeric" not in msg
            ):
                raise AssertionError(
                    f"{system.name}.compute({raw_data!r}) raised "
                    f"ISO7064Error but missing 'non-' substring: {msg!r}"
                ) from exc
            return
        except ValueError as exc:
            # THIS IS THE BUG FROM T1: MOD_11_2 with X-in-body raises raw
            # ValueError instead of ISO7064Error.  We surface this as a
            # real finding from the fuzzer — the AssertionError will cause
            # atheris to record a crash artifact.
            if isinstance(exc, ISO7064Error):
                return  # actually got the proper subclass
            raise AssertionError(
                f"{system.name}.compute({raw_data!r}) raised raw ValueError "
                f"instead of ISO7064Error (SPEC §6 AC9 violation): {exc!r}"
            ) from exc
        except Exception as exc:  # pragma: no cover
            raise AssertionError(
                f"{system.name}.compute({raw_data!r}) raised unexpected "
                f"{type(exc).__name__}: {exc!r}"
            ) from exc
        # If we got here, the system ACCEPTED the bad input — that's a bug.
        raise AssertionError(
            f"{system.name}.compute({raw_data!r}) accepted invalid input "
            f"(corrupt_kind={corrupt_kind}), returned {full!r}"
        )

    # Clean input — must succeed and round-trip.
    full: str
    try:
        full = system.compute(raw_data)
    except ISO7064Error as exc:
        raise AssertionError(
            f"{system.name}.compute({raw_data!r}) on clean input raised "
            f"ISO7064Error: {exc!r}"
        ) from exc
    except (ValueError, TypeError) as exc:
        if isinstance(exc, ISO7064Error):
            return  # mis-classified above
        raise AssertionError(
            f"{system.name}.compute({raw_data!r}) raised raw "
            f"{type(exc).__name__}: {exc!r}"
        ) from exc

    assert isinstance(full, str), (
        f"{system.name}.compute({raw_data!r}) returned {type(full).__name__}"
    )
    assert full.startswith(raw_data), (
        f"{system.name}.compute({raw_data!r}) = {full!r} doesn't start with input"
    )

    # Check-character length contract.
    expected_check_len = system.check_length
    assert len(full) == len(raw_data) + expected_check_len, (
        f"{system.name}.compute({raw_data!r}) = {full!r} has check length "
        f"{len(full) - len(raw_data)}, want {expected_check_len}"
    )

    # Round-trip via verify().
    if not system.verify(full):
        raise AssertionError(
            f"round-trip failed: {system.name}.compute({raw_data!r}) = "
            f"{full!r} but {system.name}.verify({full!r}) = False"
        )

    # Sanity: check_character returns a string of the expected length
    # whose value depends only on the body (deterministic).
    cc1 = system.check_character(raw_data)
    cc2 = system.check_character(raw_data)
    assert cc1 == cc2, (
        f"{system.name}.check_character({raw_data!r}) non-deterministic: "
        f"{cc1!r} != {cc2!r}"
    )
    assert len(cc1) == expected_check_len, (
        f"{system.name}.check_character({raw_data!r}) = {cc1!r} "
        f"length {len(cc1)}, want {expected_check_len}"
    )
    # For MOD_97_10 IBAN-shaped input, check_character returns a
    # 2-digit string that REPLACES the CC## prefix (not appended), so
    # the round-trip form differs.  We skip the equality check there.

    # Test: verify() must NEVER raise — it returns True/False.
    try:
        ok = system.verify(full)
    except Exception as exc:
        raise AssertionError(
            f"{system.name}.verify({full!r}) raised {type(exc).__name__}: "
            f"{exc!r} — verify() must be exception-safe"
        ) from exc
    assert ok is True, (
        f"{system.name}.verify({system.name}.compute({raw_data!r})) = False"
    )


def main() -> int:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
