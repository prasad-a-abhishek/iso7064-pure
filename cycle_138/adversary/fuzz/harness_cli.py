"""Atheris harness for the ``iso7064-pure`` CLI (Surface 3).

Surface 3 of the cycle_138 adversary workstream.

The CLI is the user-facing entrypoint; fuzzing it covers argparse
handling, subcommand dispatch (``compute`` / ``verify``), the
``--mode <MODE>`` choice validation, exit-code matrix (0 / 1 / 2 /
argparse error), and the JSON payload emission.

We invoke the CLI in a fresh subprocess so each fuzz input is fully
isolated.  That means a crash in the CLI doesn't take down the fuzzer.

Exit-code contract (from src/iso7064_pure/__main__.py):

* 0  — success (compute valid input, verify valid input, version, no-args).
* 2  — ``ISO7064Error`` swallowed for ``compute`` / ``verify`` path
        (the CLI converts the error into ``error: <msg>`` on stderr
        and exits 2).
* 2  — argparse parse error (bad flag, unknown option, missing --mode).

Run::

    python3 harness_cli.py -atheris_runs=2000 -max_total_time=5

We cap ``atheris_runs`` low because each run is a subprocess spawn.
"""
from __future__ import annotations

import os
import subprocess
import sys

import atheris  # type: ignore[import-not-found]

# We don't instrument the CLI module — the fuzzer runs OUT of process.
# We DO need atheris to instrument this harness file itself so that
# coverage tracks the argv-construction branches here.
with atheris.instrument_imports():  # type: ignore[attr-defined]
    pass

# After instrumentation we can safely import the package for the version string.
from iso7064_pure import __version__  # noqa: E402
from iso7064_pure import Mode  # noqa: E402


# Use the installed module entry-point, not the in-tree ``__main__``.
# This mirrors what a real user would do (``pip install`` then
# ``python -m iso7064_pure ...``).
_CMD = [sys.executable, "-m", "iso7064_pure"]

# Build a child-env that keeps PATH and PYTHONPATH intact (so
# ``python -m iso7064_pure`` can find the package) but forces
# unbuffered stdio so we capture all output.
_CHILD_ENV = {**os.environ, "PYTHONUNBUFFERED": "1"}


def _run_cli(argv: list[str], timeout: float = 1.0) -> subprocess.CompletedProcess:
    """Run the CLI with the given argv and return the CompletedProcess.

    We pass ``argv`` (a list) instead of relying on ``subprocess`` string
    parsing — this matches the in-process ``argparse.parse_args(argv)``
    contract.
    """
    return subprocess.run(
        _CMD + argv,
        capture_output=True,
        timeout=timeout,
        check=False,
        env=_CHILD_ENV,
    )


@atheris.instrument_func  # type: ignore[attr-defined]
def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)  # type: ignore[attr-defined]

    # Build a plausible argv.  We bound the size so subprocess spawn
    # time stays predictable and per-input timeout (5s) is realistic.
    mode_kind = fdp.ConsumeIntInRange(0, 7)

    # All five valid Mode values + a few deliberately bad ones to probe
    # argparse's ``choices=[...]`` rejection.
    valid_modes: tuple[str, ...] = tuple(m.value for m in Mode)
    bad_modes: tuple[str, ...] = (
        "mod_11_2",  # case mismatch — should NOT be accepted
        "MOD_99_99",  # unknown
        "",  # empty
        "🦀",  # non-ASCII
        "MOD_11_2; rm -rf /",  # shell-meta attempt
    )
    mode_value: str
    if mode_kind < len(valid_modes):
        mode_value = valid_modes[mode_kind]
    elif mode_kind < len(valid_modes) + len(bad_modes):
        mode_value = bad_modes[mode_kind - len(valid_modes)]
    else:
        mode_value = valid_modes[0]  # default to a known-good mode

    # Subcommand: 0=compute, 1=verify, 2=--version, 3=no-args, 4=unknown,
    # 5=--help, 6=missing --mode, 7=invalid positional after valid flags.
    cmd_kind = fdp.ConsumeIntInRange(0, 7)
    argv: list[str] = []
    try:
        if cmd_kind == 0:
            raw = fdp.ConsumeUnicodeNoSurrogates(20)
            argv = ["compute", raw, "--mode", mode_value]
        elif cmd_kind == 1:
            raw = fdp.ConsumeUnicodeNoSurrogates(20)
            argv = ["verify", raw, "--mode", mode_value]
        elif cmd_kind == 2:
            argv = ["--version"]
        elif cmd_kind == 3:
            argv = []
        elif cmd_kind == 4:
            fake = "definitely-not-a-subcommand-" + fdp.ConsumeUnicodeNoSurrogates(8)
            argv = [fake]
        elif cmd_kind == 5:
            argv = ["--help"]
        elif cmd_kind == 6:
            raw = fdp.ConsumeUnicodeNoSurrogates(20)
            argv = ["compute", raw]  # missing --mode
        else:
            # cmd_kind == 7: bogus flag to exercise argparse error branch.
            raw = fdp.ConsumeUnicodeNoSurrogates(20)
            argv = ["compute", raw, "--mode", mode_value, "--bogus-flag", "x"]
    except UnicodeEncodeError:
        return

    # Cap argv length so a single malformed token can't OOM the fuzzer.
    if len(argv) > 6:
        argv = argv[:6]

    try:
        proc = _run_cli(argv, timeout=1.5)
    except subprocess.TimeoutExpired:
        # 1.5s is generous for any well-formed input; a hang means the
        # CLI entered a real loop, which would be a bug.  Surface it by
        # propagating so atheris records the hang corpus entry.
        raise
    except (FileNotFoundError, PermissionError, OSError):
        # CLI not installed (developer machine without `pip install -e .`).
        # Skip this input rather than poisoning the corpus.
        return
    except ValueError as exc:
        # ``subprocess.run`` rejects argv containing embedded NUL bytes
        # with ``ValueError: embedded null byte`` BEFORE spawning the
        # child.  This is a CPython contract on POSIX, not a library
        # bug — skip the input.
        if "embedded null" in str(exc).lower():
            return
        raise

    rc = proc.returncode

    # Exit-code contract enforcement.
    if cmd_kind == 2:
        # --version always exits 0 and prints the version string.
        assert rc == 0, f"--version exited {rc}: stderr={proc.stderr!r}"
        assert b"iso7064-pure" in proc.stdout, (
            f"--version missing version string: {proc.stdout!r}"
        )
        assert f"iso7064-pure {__version__}".encode() in proc.stdout, (
            f"--version output {proc.stdout!r} doesn't contain expected "
            f"'iso7064-pure {__version__}'"
        )
    elif cmd_kind == 3:
        # No args → usage on stdout, exit 0.
        assert rc == 0, f"no-args exited {rc}: stderr={proc.stderr!r}"
        assert b"usage:" in proc.stdout.lower(), (
            f"no-args missing usage line: stdout={proc.stdout!r}"
        )
    elif cmd_kind == 5:
        # --help exits 0 and prints usage.
        assert rc == 0, f"--help exited {rc}: stderr={proc.stderr!r}"
        assert b"usage:" in proc.stdout.lower(), (
            f"--help missing usage line: stdout={proc.stdout!r}"
        )
    elif cmd_kind == 4:
        # Unknown subcommand → argparse error, exit 2.
        assert rc == 2, f"unknown-cmd exited {rc} (want 2): stderr={proc.stderr!r}"
        assert (
            b"usage:" in proc.stderr.lower() or b"error:" in proc.stderr.lower()
        ), f"argparse error didn't mention usage/error: {proc.stderr!r}"
    elif cmd_kind == 6:
        # Missing --mode → argparse error, exit 2.
        assert rc == 2, f"missing-mode exited {rc} (want 2): stderr={proc.stderr!r}"
        assert (
            b"--mode" in proc.stderr.lower() or b"required" in proc.stderr.lower()
        ), f"missing-mode error didn't mention --mode: {proc.stderr!r}"
    elif cmd_kind == 7:
        # Bogus extra flag → argparse error, exit 2.
        assert rc == 2, f"bogus-flag exited {rc} (want 2): stderr={proc.stderr!r}"
        assert (
            b"unrecognized" in proc.stderr.lower()
            or b"unknown" in proc.stderr.lower()
            or b"usage:" in proc.stderr.lower()
        ), f"bogus-flag error: {proc.stderr!r}"
    else:
        # cmd_kind 0 or 1: compute / verify path.
        # If mode_value is bad → argparse exit 2.
        if mode_value not in valid_modes:
            assert rc == 2, (
                f"bad-mode {mode_value!r} exited {rc} (want 2): "
                f"stderr={proc.stderr!r}"
            )
            return
        # Otherwise: rc in (0, 1, 2) per the CLI contract.
        # 0 — success (compute produced check string, or verify returned True).
        # 1 — verify returned False (check character mismatch).  This is
        #      a documented success-path of verify, NOT a CLI error.
        # 2 — ISO7064Error caught by __main__, exits 2 with "error:" on stderr.
        assert rc in (0, 1, 2), (
            f"compute/verify path exited {rc} (want 0/1/2): "
            f"stderr={proc.stderr!r}"
        )
        if rc == 2:
            # ISO7064Error swallowed → stderr must contain "error:".
            assert b"error:" in proc.stderr.lower(), (
                f"ISO7064Error exit-2 path missing 'error:' on stderr: "
                f"{proc.stderr!r}"
            )
        elif rc == 0 and cmd_kind == 0:
            # compute succeeded → stdout must contain a non-empty check string.
            assert proc.stdout, (
                f"compute succeeded but stdout empty: stderr={proc.stderr!r}"
            )
        elif rc == 0 and cmd_kind == 1:
            # verify=True → stdout may be empty (verify doesn't print on
            # success), but exit code 0 means verify returned True.
            pass
        elif rc == 1 and cmd_kind == 1:
            # verify=False → documented "invalid check character" path.
            assert proc.stderr == b"", (
                f"verify=False exit-1 path shouldn't write to stderr: "
                f"{proc.stderr!r}"
            )


def main() -> int:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
