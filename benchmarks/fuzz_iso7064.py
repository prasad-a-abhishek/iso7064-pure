"""Fuzz harness for iso7064-pure (AC11 / Invariant 14).

Runs a configurable number of iterations of ``compute`` then ``verify``
across all five ISO 7064 systems. Exits non-zero if any crash or oracle
mismatch is detected. By default 100,000 iterations are run (the floor
required by the SPEC); the user can pass a smaller count for quicker
smoke runs.

Usage::

    python3 benchmarks/fuzz_iso7064.py                # 100,000 iters per system
    python3 benchmarks/fuzz_iso7064.py --iters 5000   # 5,000 iters per system
    python3 benchmarks/fuzz_iso7064.py --report PATH  # write markdown summary

The harness runs each system against a randomly generated alphanumeric
corpus (length 1-30), asserts that ``verify(compute(data)) is True``
for every input, and asserts dispatch consistency
``compute(data, mode=M) == System(M).compute(data)``. No network access
and no extra dependencies are required.
"""

from __future__ import annotations

import argparse
import random
import string
import sys
import time
import traceback
from pathlib import Path

# Make the in-tree ``src/`` layout importable when run from the repo root.
_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "src"))

import iso7064_pure  # noqa: E402
from iso7064_pure import (  # noqa: E402
    MOD_11_2,
    MOD_37_2,
    MOD_97_10,
    MOD_661_26,
    MOD_1271_36,
    Mode,
    compute,
)


_NUMERIC_ALPHABET = string.digits
_ALNUM_ALPHABET = string.ascii_uppercase + string.digits


def _gen_corpus(n: int, alphabet: str, *, rng: random.Random,
                min_len: int = 1, max_len: int = 30) -> list[str]:
    """Generate ``n`` random strings over ``alphabet`` of length min_len..max_len."""
    return [
        "".join(rng.choice(alphabet) for _ in range(rng.randint(min_len, max_len)))
        for _ in range(n)
    ]


def _gen_iban_corpus(n: int, *, rng: random.Random) -> list[str]:
    """Generate ``n`` random IBAN-shaped strings (CC + 2 digits + body)."""
    countries = ("GB", "DE", "FR", "GR", "IT", "NL", "ES", "PT", "IE")
    return [
        rng.choice(countries)
        + f"{rng.randint(0, 99):02d}"
        + "".join(rng.choice(_ALNUM_ALPHABET) for _ in range(rng.randint(8, 24)))
        for _ in range(n)
    ]


def fuzz_system(system, alphabet: str, iters: int, *, seed: int) -> dict:
    """Run ``iters`` round-trip iterations on ``system`` and report stats."""
    rng = random.Random(seed)
    corpus = _gen_corpus(iters, alphabet, rng=rng)
    failures: list[tuple[str, str, str]] = []
    crashes = 0
    t0 = time.perf_counter()
    for data in corpus:
        try:
            full = system.compute(data)
            ok = system.verify(full)
            if not ok:
                failures.append((data, full, "round-trip mismatch"))
        except Exception:  # pragma: no cover
            crashes += 1
            traceback.print_exc()
    elapsed = time.perf_counter() - t0
    return {
        "system": system.name,
        "iters": iters,
        "elapsed_s": elapsed,
        "rate_per_s": iters / elapsed if elapsed > 0 else float("inf"),
        "failures": failures,
        "crashes": crashes,
    }


def fuzz_iban(iters: int, *, seed: int) -> dict:
    """Run IBAN-specific round-trip fuzz on MOD_97_10."""
    rng = random.Random(seed)
    corpus = _gen_iban_corpus(iters, rng=rng)
    failures: list[tuple[str, str, str]] = []
    crashes = 0
    t0 = time.perf_counter()
    for data in corpus:
        try:
            full = MOD_97_10.compute(data)
            ok = MOD_97_10.verify(full)
            if not ok:
                failures.append((data, full, "IBAN round-trip mismatch"))
        except Exception:  # pragma: no cover
            crashes += 1
            traceback.print_exc()
    elapsed = time.perf_counter() - t0
    return {
        "system": "MOD_97_10 (IBAN-shaped)",
        "iters": iters,
        "elapsed_s": elapsed,
        "rate_per_s": iters / elapsed if elapsed > 0 else float("inf"),
        "failures": failures,
        "crashes": crashes,
    }


def fuzz_dispatch(iters: int, *, seed: int) -> dict:
    """Confirm that ``compute(data, mode=M)`` agrees with ``System(M).compute(data)``."""
    rng = random.Random(seed)
    pairs = [
        (Mode.MOD_11_2, MOD_11_2, _NUMERIC_ALPHABET),
        (Mode.MOD_37_2, MOD_37_2, _ALNUM_ALPHABET),
        (Mode.MOD_97_10, MOD_97_10, _NUMERIC_ALPHABET),
        (Mode.MOD_661_26, MOD_661_26, _ALNUM_ALPHABET),
        (Mode.MOD_1271_36, MOD_1271_36, _ALNUM_ALPHABET),
    ]
    failures: list[str] = []
    crashes = 0
    t0 = time.perf_counter()
    for mode, system, alphabet in pairs:
        corpus = _gen_corpus(iters, alphabet, rng=rng)
        for data in corpus:
            try:
                if compute(data, mode=mode) != system.compute(data):
                    failures.append(f"{system.name}: dispatch mismatch for {data!r}")
            except Exception:  # pragma: no cover
                crashes += 1
                traceback.print_exc()
    elapsed = time.perf_counter() - t0
    return {
        "system": "dispatch",
        "iters": iters * len(pairs),
        "elapsed_s": elapsed,
        "rate_per_s": (iters * len(pairs)) / elapsed if elapsed > 0 else float("inf"),
        "failures": failures,
        "crashes": crashes,
    }


def write_report(results: list[dict], iters: int, path: Path) -> None:
    """Write a markdown summary of the fuzz run to ``path``."""
    lines = [
        "# fuzz_report.md",
        "",
        f"Fuzz harness for `iso7064-pure` — {iters:,} iterations per system.",
        "",
        "## Summary",
        "",
        f"- Total iters: {sum(r['iters'] for r in results):,}",
        f"- Total crashes: {sum(r['crashes'] for r in results)}",
        f"- Total oracle mismatches: {sum(len(r['failures']) for r in results)}",
        f"- Total elapsed: {sum(r['elapsed_s'] for r in results):.2f}s",
        "",
        "## Per-system results",
        "",
        "| System | Iters | Elapsed (s) | Rate (ops/s) | Crashes | Oracle mismatches |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r['system']} | {r['iters']:,} | {r['elapsed_s']:.3f} "
            f"| {r['rate_per_s']:,.0f} | {r['crashes']} | {len(r['failures'])} |"
        )
    lines.append("")
    lines.append("## Verdict")
    lines.append("")
    total_crashes = sum(r["crashes"] for r in results)
    total_failures = sum(len(r["failures"]) for r in results)
    if total_crashes == 0 and total_failures == 0:
        lines.append("VERDICT: PASS — 0 crashes, 0 oracle mismatches.")
    else:
        lines.append(
            f"VERDICT: FAIL — {total_crashes} crash(es), "
            f"{total_failures} oracle mismatch(es)."
        )
    path.write_text("\n".join(lines) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--iters", type=int, default=100_000,
        help="Iterations per system (default: 100000; SPEC floor)",
    )
    parser.add_argument(
        "--report", type=Path, default=None,
        help="Optional path for a markdown summary (default: benchmarks/fuzz_report.md)",
    )
    args = parser.parse_args(argv)

    iters = args.iters
    report_path = args.report or (_REPO / "benchmarks" / "fuzz_report.md")

    print(f"iso7064-pure fuzz harness — {iters:,} iters per surface")
    results = [
        fuzz_system(MOD_11_2, _NUMERIC_ALPHABET, iters, seed=11),
        fuzz_system(MOD_37_2, _ALNUM_ALPHABET, iters, seed=22),
        fuzz_system(MOD_661_26, _ALNUM_ALPHABET, iters, seed=33),
        fuzz_system(MOD_1271_36, _ALNUM_ALPHABET, iters, seed=44),
        fuzz_iban(iters, seed=55),
        fuzz_dispatch(iters, seed=66),
    ]
    total_crashes = sum(r["crashes"] for r in results)
    total_failures = sum(len(r["failures"]) for r in results)
    for r in results:
        print(
            f"  {r['system']:<22} {r['iters']:>8,} iters  "
            f"{r['elapsed_s']:>7.2f}s  "
            f"{r['rate_per_s']:>10,.0f} ops/s  "
            f"crashes={r['crashes']}  mismatches={len(r['failures'])}"
        )
    print(
        f"\nTotal: {total_crashes} crashes, {total_failures} oracle mismatches "
        f"across {sum(r['iters'] for r in results):,} iterations."
    )

    write_report(results, iters, report_path)
    print(f"Markdown report written to {report_path}")

    if total_crashes or total_failures:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())