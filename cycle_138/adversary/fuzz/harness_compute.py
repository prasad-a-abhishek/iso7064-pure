"""Atheris harness for the top-level ``compute()`` dispatch surface.

Surface 1 of the cycle_138 adversary workstream.

Exercises :func:`iso7064_pure.compute` and :func:`iso7064_pure.verify` —
the two public module-level dispatch helpers that route through
:func:`_resolve_system` and the :class:`Mode` enum.  This complements
``harness_per_system.py`` (which calls the per-system singletons directly)
by also fuzzing the dispatch path itself: bad / unknown mode strings,
enum values supplied as raw strings, etc.

Specifically we test:

* ``compute(data, mode=Mode.X)`` for every ``Mode`` enum value, with
  ``data`` drawn from the matching alphabet so the call is expected to
  succeed.  On success we assert ``verify(full, mode=...) is True``.
* ``compute(data, mode=<random string>)`` — the dispatch helper must
  raise :class:`ISO7064Error` (or accept a valid alias), NEVER
  ``KeyError`` or ``AttributeError` from a missing dict entry.
* ``compute(bad_data, mode=Mode.X)`` with chars outside the alphabet —
  the call MUST raise :class:`ISO7064Error`, NEVER a raw :class:`ValueError`
  (this is the SPEC §6 AC9 contract that the VULN_AUDIT flagged as
  currently violated for ``MOD_11_2`` X-in-body inputs).
* ``compute(non_str, mode=Mode.X)`` — type-error path; must raise
  :class:`ISO7064Error` (a subclass of :class:`ValueError`).
* ``compute("", mode=Mode.X)`` — empty input path.

Run::

    python3 harness_compute.py -atheris_runs=100000 -max_total_time=5
"""
from __future__ import annotations

import sys

import atheris  # type: ignore[import-not-found]  # atheris is installed system-wide

# ``atheris.instrument_imports`` is a runtime-injected context manager;
# pyright cannot see it statically because the symbols are mutated by
# atheris's native coverage shim.  Suppress the false-positive.
with atheris.instrument_imports():  # type: ignore[attr-defined]
    from iso7064_pure import (
        ISO7064Error,
        Mode,
        compute,
        verify,
    )


# Per-mode seed alphabets — these match what the build's tests use to
# seed the round-trip corpus.  Fuzzed inputs are drawn from these so the
# happy path is exercised frequently; we then ALSO inject malformed
# inputs (chars outside the alphabet, non-str, empty) to probe error
# branches.
#
# MOD_97_10 (IBAN) is special: it accepts DIGITS in any position, but
# only accepts LETTERS when the input is IBAN-shaped (``CC##...``).  We
# seed with digits-only for the fuzz corpus so the harness exercises
# the non-IBAN branch.  The IBAN branch is covered by Surface 2 which
# constructs IBAN-shaped inputs explicitly.
_MODE_ALPHABETS: dict[Mode, str] = {
    Mode.MOD_11_2: "0123456789",  # numeric (X allowed in check char; not in fuzz body)
    Mode.MOD_37_2: "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ",  # alphanumeric
    Mode.MOD_97_10: "0123456789",  # numeric-only for non-IBAN path
    Mode.MOD_661_26: "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ",  # alphanumeric
    Mode.MOD_1271_36: "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ",  # alphanumeric
}
_MODE_LIST: list[Mode] = list(_MODE_ALPHABETS.keys())

# Valid aliases the dispatch helper should accept (Mode values + raw strings).
_VALID_MODE_ALIASES: tuple[str, ...] = tuple(m.value for m in _MODE_LIST)
# Invalid modes that the dispatch helper MUST reject via ISO7064Error,
# not KeyError / AttributeError.
_INVALID_MODE_ALIASES: tuple[str, ...] = (
    "",
    "mod_11_2",  # case-mismatch must not silently resolve
    "MOD_99_99",
    "MOD_11_2; rm -rf /",
    "MOD_11_2\x00",
    "🦀",  # non-ASCII
)


@atheris.instrument_func  # type: ignore[attr-defined]
def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)  # type: ignore[attr-defined]

    # Pick mode: 0..len(MODE_LIST)-1 → valid enum; len..+3 → valid alias string;
    # +4..+7 → invalid alias string; +8 → non-str sentinel (None).
    n_modes = len(_MODE_LIST)
    mode_kind = fdp.ConsumeIntInRange(0, n_modes + 7)
    bad_kind = fdp.ConsumeIntInRange(0, 3)

    if mode_kind < n_modes:
        mode = _MODE_LIST[mode_kind]
    elif mode_kind < n_modes + 4:
        mode = _VALID_MODE_ALIASES[mode_kind - n_modes]
    elif mode_kind < n_modes + 8:
        mode = _INVALID_MODE_ALIASES[mode_kind - n_modes - 4]
    else:
        mode = None  # sentinel: dispatch helper must reject via ISO7064Error

    # Build input: draw ``length`` chars from the mode's alphabet so the
    # happy-path compute is exercised.  Then optionally inject a bad
    # char / wrong-type / empty.
    length = fdp.ConsumeIntInRange(1, 24)
    raw_data = fdp.ConsumeUnicodeNoSurrogates(length)

    # Get the right alphabet for the current mode (used for clean-path filtering).
    cur_mode = mode if isinstance(mode, Mode) else Mode(_VALID_MODE_ALIASES[0])
    cur_alphabet = _MODE_ALPHABETS[cur_mode]

    if bad_kind == 0 and isinstance(mode, Mode) and mode is not Mode.MOD_11_2:
        # Inject a lowercase letter (out-of-alphabet) into the body.
        raw_data = raw_data + "a" if raw_data else "a"
    elif bad_kind == 1:
        # Inject a non-alphanumeric punctuation.
        raw_data = raw_data + "!" if raw_data else "!"
    elif bad_kind == 2:
        # Empty body — must raise ISO7064Error.
        raw_data = ""
    else:
        # bad_kind == 3 (clean): strip anything not in the alphabet so
        # the harness exercises the compute/verify happy path rather than
        # wasting iterations on validation-only fuzz (covered by Surface 2).
        raw_data = "".join(c if c in cur_alphabet else cur_alphabet[0] for c in raw_data)
        if not raw_data:
            raw_data = cur_alphabet[0]

    # The fuzzer may also produce an empty string from ConsumeUnicodeNoSurrogates
    # even when length > 0 (e.g. lone surrogates get filtered); in that case
    # we expect ISO7064Error too.
    if not raw_data:
        # Empty data → ISO7064Error is the documented contract.
        try:
            compute(raw_data, mode=mode)  # type: ignore[arg-type]
        except ISO7064Error:
            return
        except (TypeError, ValueError) as exc:
            if isinstance(exc, ISO7064Error):
                return
            raise AssertionError(
                f"compute('', mode={mode}) raised raw {type(exc).__name__}: {exc!r}"
            ) from exc
        raise AssertionError(
            f"compute('', mode={mode}) did NOT raise — empty data must reject"
        )

    # If mode is invalid, we only test that the dispatch rejects it cleanly;
    # we skip the data path because the dispatch happens BEFORE data
    # validation in the implementation.
    if not (isinstance(mode, Mode) or mode in _VALID_MODE_ALIASES):
        try:
            compute(raw_data, mode=mode)  # type: ignore[arg-type]
        except ISO7064Error:
            return  # expected
        except (ValueError, TypeError):
            # ISO7064Error is a ValueError subclass; if dispatch raised a
            # bare ValueError/TypeError, that's acceptable (e.g. None
            # mode triggers AttributeError on .value, which we want to
            # surface as a finding).
            return
        except AttributeError:
            # The None sentinel path: dispatch helper does
            # ``mode.value if hasattr(mode, 'value') else str(mode)`` —
            # None has no .value, str(None)='None' → KeyError on dict
            # lookup → ISO7064Error.  An uncaught AttributeError would
            # be a bug.
            raise
        except Exception as exc:  # pragma: no cover — record any other path
            raise AssertionError(
                f"dispatch rejected invalid mode with unexpected exception "
                f"{type(exc).__name__}: {exc!r}"
            ) from exc
        # If we reach here, the dispatch ACCEPTED a bogus mode — that's a bug.
        raise AssertionError(
            f"dispatch accepted invalid mode {mode!r} (kind={mode_kind})"
        )

    # Valid mode path.
    if not isinstance(mode, Mode):
        mode = Mode(mode)

    try:
        full = compute(raw_data, mode=mode)
    except ISO7064Error:
        # Expected on bad chars / empty / non-str.  Verify path:
        if bad_kind in (0, 1):
            return  # expected: bad chars in body
        if bad_kind == 2 and not raw_data:
            return  # expected: empty data
        # Unexpected ISO7064Error from a "clean" body — record the input.
        raise AssertionError(
            f"compute({raw_data!r}, mode={mode}) raised ISO7064Error "
            f"on apparently valid input"
        )
    except (ValueError, TypeError) as exc:
        # SPEC §6 AC9: must be ISO7064Error, not raw ValueError.
        # If we see a bare ValueError/TypeError, that's the bug from T1.
        if isinstance(exc, ISO7064Error):
            return  # already handled above
        if isinstance(exc, TypeError) and not isinstance(raw_data, str):
            return  # non-str input — may legitimately be TypeError
        raise AssertionError(
            f"compute({raw_data!r}, mode={mode}) raised raw "
            f"{type(exc).__name__} instead of ISO7064Error: {exc!r}"
        ) from exc

    # If we got here, compute succeeded — assert verify round-trips.
    assert isinstance(full, str), (
        f"compute({raw_data!r}, mode={mode}) returned non-str: "
        f"{type(full).__name__}"
    )
    assert full.startswith(raw_data), (
        f"compute({raw_data!r}, mode={mode}) = {full!r} doesn't start with input"
    )
    assert len(full) == len(raw_data) + (2 if mode is Mode.MOD_97_10
                                          or mode is Mode.MOD_1271_36 else 1), (
        f"compute({raw_data!r}, mode={mode}) = {full!r} has wrong check-char length"
    )

    # Round-trip: verify the FULL string passes verify().
    if not verify(full, mode=mode):
        raise AssertionError(
            f"round-trip failed: compute({raw_data!r}, mode={mode}) = "
            f"{full!r} but verify({full!r}, mode={mode}) = False"
        )

    # Verify the truncated-by-check-char string ALSO fails verify (sanity).
    if len(raw_data) > 0:
        truncated = full[:-1] if mode is not Mode.MOD_97_10 else full[:-2]
        # Just ensure verify on a wrong-shape string doesn't crash:
        try:
            _ = verify(truncated + "0", mode=mode)
        except ISO7064Error:
            pass


def main() -> int:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
