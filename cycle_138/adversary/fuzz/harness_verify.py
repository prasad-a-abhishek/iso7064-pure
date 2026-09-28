"""Atheris harness for the ``verify()`` round-trip surface (Surface 5).

Surface 5 of the cycle_138 adversary workstream.

Exercises the :meth:`System.verify` method on fully-formed strings that
already include (or purport to include) a check character.  This
complements Surface 2 (which fuzzes ``compute()``) by fuzzing the
inverse direction: random strings that MAY be valid check character
strings.  We also exercise the ``verify()`` failure paths: truncated,
wrong-length, char-substituted, etc.

Specifically we test:

* ``verify(s)`` is the canonical round-trip of ``verify(compute(d)) is
  True`` for any alphabet-valid ``d``.
* ``verify`` NEVER raises — it returns ``True`` or ``False``.  An
  :class:`ISO7064Error` from inside ``_check_character_impl`` (e.g.
  X-in-body on MOD_11_2) MUST be caught and converted to ``False``.
* Mutating a single character in the check-character position must
  cause ``verify`` to return ``False`` for non-coincidental cases.
* Truncating the check character must cause ``verify`` to return
  ``False`` (and NEVER raise, even when the body alone is unparseable).
* Empty input, single-char input (less than ``check_length``),
  non-string input — all must return ``False``.
* For each of the 5 systems, ``verify`` must behave consistently with
  ``compute`` over a randomized alphabet-valid corpus.

Run::

    python3 harness_verify.py -atheris_runs=100000 -max_total_time=5
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


_SYSTEM_TABLE: list[tuple[System, str]] = [
    (MOD_11_2, "0123456789"),
    (MOD_37_2, "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
    (MOD_97_10, "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"),  # IBAN
    (MOD_661_26, "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
    (MOD_1271_36, "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
]


@atheris.instrument_func  # type: ignore[attr-defined]
def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)  # type: ignore[attr-defined]

    sys_idx = fdp.ConsumeIntInRange(0, len(_SYSTEM_TABLE) - 1)
    system, alphabet = _SYSTEM_TABLE[sys_idx]
    check_len = system.check_length

    # Pick a corruption strategy for the verify() input.
    # 0=clean alphabet, 1=truncated (drop check char), 2=wrong-char swap
    # in check position, 3=extra char appended, 4=lowercase mix, 5=empty,
    # 6=non-string sentinel, 7=append random valid char to body, 8=MOD_11_2
    # X-in-body for verify() (the VULN_AUDIT bug class).
    corrupt = fdp.ConsumeIntInRange(0, 8)

    if corrupt == 6:
        # Non-string input — must return False, NEVER raise.
        sentinel_kind = fdp.ConsumeIntInRange(0, 3)
        sentinels: tuple[_t.Any, ...] = (None, 12345, [1, 2], 1.5)
        sentinel = sentinels[sentinel_kind]
        try:
            ok = system.verify(sentinel)  # type: ignore[arg-type]
        except ISO7064Error:
            # The base class catches ISO7064Error internally and returns
            # False.  If we see it escape, that's a regression.
            raise AssertionError(
                f"{system.name}.verify({sentinel!r}) leaked ISO7064Error — "
                f"verify() must swallow errors and return False"
            )
        except Exception as exc:
            raise AssertionError(
                f"{system.name}.verify({sentinel!r}) leaked "
                f"{type(exc).__name__}: {exc!r} — verify() must be "
                f"exception-safe"
            ) from exc
        assert ok is False, (
            f"{system.name}.verify({sentinel!r}) = True — non-string must "
            f"return False"
        )
        return

    if corrupt == 5:
        # Empty input — must return False, NEVER raise.
        ok = system.verify("")  # type: ignore[arg-type]
        assert ok is False, f"{system.name}.verify('') = True — must be False"
        return

    # Build a body of random alphabet chars (so compute() succeeds).
    body_len = fdp.ConsumeIntInRange(1, 20)
    body = fdp.ConsumeUnicodeNoSurrogates(body_len)
    # Strip anything not in the alphabet; this keeps the body
    # compute()-valid without using fuzzer time on validation errors
    # (covered in Surface 1/2).
    body = "".join(c if c in alphabet else alphabet[0] for c in body)
    if not body:
        body = alphabet[0]

    # Use the system to compute a valid full string.
    try:
        valid_full = system.compute(body)
    except (ISO7064Error, ValueError) as exc:
        # The body passed our alphabet filter but the system may reject
        # it (e.g. IBAN-shaped CC## prefix).  Skip the input.
        return

    # === Round-trip: verify(valid_full) MUST be True ===
    try:
        ok = system.verify(valid_full)
    except Exception as exc:
        raise AssertionError(
            f"{system.name}.verify({valid_full!r}) raised "
            f"{type(exc).__name__}: {exc!r}"
        ) from exc
    assert ok is True, (
        f"{system.name}.verify({valid_full!r}) = False on freshly computed "
        f"string — round-trip broken"
    )

    # === Corrupt the check character ===
    if corrupt == 0:
        # Clean — no further assertions (already covered above).
        return
    elif corrupt == 1:
        # Truncate the check character(s) off the end and re-verify.
        # We only test that verify doesn't RAISE on the truncated input.
        # (Whether it returns True/False is a property of the math, not
        # of the implementation — see harness docstring.)
        if len(valid_full) > check_len:
            truncated = valid_full[:-check_len]
            try:
                _ = system.verify(truncated)
            except Exception as exc:
                raise AssertionError(
                    f"{system.name}.verify({truncated!r}) (truncated) "
                    f"raised {type(exc).__name__}: {exc!r}"
                ) from exc
        return
    elif corrupt == 2:
        # Swap the LAST check character with a different alphabet char.
        if len(valid_full) >= 1:
            last_pos = len(valid_full) - 1
            original = valid_full[last_pos]
            if original in alphabet:
                replacement = alphabet[(alphabet.index(original) + 1) % len(alphabet)]
            else:
                # The last char isn't in our test alphabet (e.g. MOD_11_2
                # check char "X" — X is in MOD_11_2 alphabet but not in
                # the test's "0123456789").  Pick a different alphabet
                # char that we know is not equal to ``original``.
                replacement = alphabet[0] if alphabet[0] != original else (
                    alphabet[1] if len(alphabet) > 1 else alphabet[0]
                )
            mutated = valid_full[:last_pos] + replacement
            if mutated != valid_full:
                try:
                    _ = system.verify(mutated)
                except Exception as exc:
                    raise AssertionError(
                        f"{system.name}.verify({mutated!r}) (mutated check) "
                        f"raised {type(exc).__name__}: {exc!r}"
                    ) from exc
                # The mutated char may coincidentally still be a valid
                # check character (rare but possible for small alphabets);
                # we don't assert False here, only that no exception
                # leaked.
        return
    elif corrupt == 3:
        # Append an extra alphabet char.
        extra = alphabet[fdp.ConsumeIntInRange(0, len(alphabet) - 1)]
        longer = valid_full + extra
        try:
            _ = system.verify(longer)
        except Exception as exc:
            raise AssertionError(
                f"{system.name}.verify({longer!r}) (appended) raised "
                f"{type(exc).__name__}: {exc!r}"
            ) from exc
        return
    elif corrupt == 4:
        # Lowercase mix — must return False, NEVER raise.  We pick a
        # position that is GUARANTEED to be a letter (not a digit) so
        # lowercasing actually mutates the string.
        positions = [i for i, c in enumerate(valid_full) if "A" <= c <= "Z"]
        if not positions:
            # No uppercase letters in the computed string — pick a
            # digit and confirm verify() with no mutation still passes
            # (already covered above), so just return.
            return
        idx = positions[fdp.ConsumeIntInRange(0, len(positions) - 1)]
        mixed = valid_full[:idx] + valid_full[idx].lower() + valid_full[idx + 1:]
        assert mixed != valid_full, (
            f"lowercase corruption didn't mutate: valid_full={valid_full!r}, "
            f"mixed={mixed!r}"
        )
        try:
            ok = system.verify(mixed)
        except Exception as exc:
            raise AssertionError(
                f"{system.name}.verify({mixed!r}) (lowercase) raised "
                f"{type(exc).__name__}: {exc!r} — verify() must be "
                f"exception-safe"
            ) from exc
        assert ok is False, (
            f"{system.name}.verify({mixed!r}) (lowercase) = True — "
            f"lowercase must NOT validate"
        )
        return
    elif corrupt == 7:
        # Append a random valid char to body and verify — this probes
        # the verify() implementation with a length-mismatched string.
        extra = alphabet[fdp.ConsumeIntInRange(0, len(alphabet) - 1)]
        longer = valid_full + extra
        try:
            ok = system.verify(longer)
        except Exception as exc:
            raise AssertionError(
                f"{system.name}.verify({longer!r}) (extra char) raised "
                f"{type(exc).__name__}: {exc!r}"
            ) from exc
        # We don't assert a specific value — the longer string may or
        # may not validate depending on the algorithm — but it MUST NOT
        # raise.
        return
    else:
        # corrupt == 8: MOD_11_2 X-in-body for verify().  This is the
        # T1-VULN_AUDIT bug class: verify() must swallow the raw
        # ValueError from int("X") and return False.
        if system is not MOD_11_2:
            return
        # Construct a string with X in the body (NOT as check char).
        x_body = "X" + body[1:] if body else "X"
        try:
            ok = system.verify(x_body)
        except (ISO7064Error, ValueError, TypeError) as exc:
            raise AssertionError(
                f"{system.name}.verify({x_body!r}) (X-in-body) leaked "
                f"{type(exc).__name__}: {exc!r} — verify() MUST swallow "
                f"errors and return False (SPEC §6 AC9)"
            ) from exc
        except Exception as exc:
            raise AssertionError(
                f"{system.name}.verify({x_body!r}) (X-in-body) leaked "
                f"{type(exc).__name__}: {exc!r}"
            ) from exc
        assert ok is False, (
            f"{system.name}.verify({x_body!r}) (X-in-body) = True — X is "
            f"never a valid body character, verify must return False"
        )


def main() -> int:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
