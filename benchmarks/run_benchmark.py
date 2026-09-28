"""Benchmark harness for iso7064-pure (Invariant 14).

Compares iso7064-pure against the canonical python-stdnum ISO 7064
implementations across the same input corpus. Reports mean ops/sec over
5 runs of N iterations per workload, plus peak memory and P95 latency.

Usage::

    python3 benchmarks/run_benchmark.py
    python3 benchmarks/run_benchmark.py --iters 1000 --runs 3

The script appends its results table to ``benchmarks/BENCHMARK.md``
under the heading ``## Latest run``.
"""

from __future__ import annotations

import argparse
import random
import statistics
import string
import sys
import time
import tracemalloc
from pathlib import Path

# Make the in-tree ``src/`` importable.
_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "src"))

import iso7064_pure  # noqa: E402
from iso7064_pure import (  # noqa: E402
    MOD_11_2,
    MOD_37_2,
    MOD_97_10,
    MOD_661_26,
    MOD_1271_36,
)

_ALNUM = string.ascii_uppercase + string.digits
_DIGITS = string.digits


def _make_corpus(n: int, alphabet: str, *, seed: int = 1337) -> list[str]:
    rng = random.Random(seed)
    return [
        "".join(rng.choice(alphabet) for _ in range(rng.randint(1, 30)))
        for _ in range(n)
    ]


def _bench_round_trip(system, corpus: list[str]) -> tuple[float, float, int]:
    """Return (mean ops/s, p95 latency ms, peak memory bytes)."""
    # Warm up.
    for s in corpus[:50]:
        full = system.compute(s)
        system.verify(full)

    tracemalloc.start()
    t0 = time.perf_counter()
    latencies_ms: list[float] = []
    for s in corpus:
        s_t0 = time.perf_counter()
        full = system.compute(s)
        system.verify(full)
        latencies_ms.append((time.perf_counter() - s_t0) * 1000)
    elapsed = time.perf_counter() - t0
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    ops_per_s = (len(corpus) * 2) / elapsed if elapsed > 0 else float("inf")
    p95_ms = (
        statistics.quantiles(latencies_ms, n=20, method="inclusive")[-1]
        if latencies_ms
        else 0.0
    )
    return ops_per_s, p95_ms, peak


def _bench_stdnum_isbn(corpus: list[str]) -> tuple[float, float, int]:
    """Benchmark python-stdnum's ISBN-10 validation as the MOD 11-2 reference."""
    try:
        import stdnum.isbn as stdnum_isbn  # noqa: WPS433 (lazy import)
    except ImportError:
        return 0.0, 0.0, 0
    tracemalloc.start()
    t0 = time.perf_counter()
    latencies_ms: list[float] = []
    for s in corpus:
        s_t0 = time.perf_counter()
        # stdnum expects the FULL ISBN-10 (body + check), so we add a
        # placeholder check digit, then validate. For benchmark
        # purposes this counts as one iteration.
        candidate = s + (s[-1] if s else "0")
        try:
            stdnum_isbn.validate(candidate)
        except Exception:
            pass
        latencies_ms.append((time.perf_counter() - s_t0) * 1000)
    elapsed = time.perf_counter() - t0
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return (
        len(corpus) / elapsed if elapsed > 0 else float("inf"),
        statistics.quantiles(latencies_ms, n=20, method="inclusive")[-1] if latencies_ms else 0.0,
        peak,
    )


def _bench_stdnum_mod37_2(corpus: list[str]) -> tuple[float, float, int]:
    try:
        import stdnum.iso7064.mod_37_2 as m  # noqa: WPS433
    except ImportError:
        return 0.0, 0.0, 0
    tracemalloc.start()
    t0 = time.perf_counter()
    latencies_ms: list[float] = []
    for s in corpus:
        s_t0 = time.perf_counter()
        try:
            m.is_valid(s + m.calc_check_digit(s))
        except Exception:
            pass
        latencies_ms.append((time.perf_counter() - s_t0) * 1000)
    elapsed = time.perf_counter() - t0
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return (
        len(corpus) / elapsed if elapsed > 0 else float("inf"),
        statistics.quantiles(latencies_ms, n=20, method="inclusive")[-1] if latencies_ms else 0.0,
        peak,
    )


def _bench_stdnum_mod97_10(corpus: list[str]) -> tuple[float, float, int]:
    """MOD 97-10 IBAN validation via stdnum."""
    try:
        import stdnum.iban as stdnum_iban  # noqa: WPS433
    except ImportError:
        return 0.0, 0.0, 0
    tracemalloc.start()
    t0 = time.perf_counter()
    latencies_ms: list[float] = []
    for s in corpus:
        s_t0 = time.perf_counter()
        try:
            stdnum_iban.validate(s)
        except Exception:
            pass
        latencies_ms.append((time.perf_counter() - s_t0) * 1000)
    elapsed = time.perf_counter() - t0
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return (
        len(corpus) / elapsed if elapsed > 0 else float("inf"),
        statistics.quantiles(latencies_ms, n=20, method="inclusive")[-1] if latencies_ms else 0.0,
        peak,
    )


def _bench_stdnum_cusip(corpus: list[str]) -> tuple[float, float, int]:
    try:
        import stdnum.cusip as stdnum_cusip  # noqa: WPS433
    except ImportError:
        return 0.0, 0.0, 0
    tracemalloc.start()
    t0 = time.perf_counter()
    latencies_ms: list[float] = []
    for s in corpus:
        s_t0 = time.perf_counter()
        try:
            stdnum_cusip.validate(s)
        except Exception:
            pass
        latencies_ms.append((time.perf_counter() - s_t0) * 1000)
    elapsed = time.perf_counter() - t0
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return (
        len(corpus) / elapsed if elapsed > 0 else float("inf"),
        statistics.quantiles(latencies_ms, n=20, method="inclusive")[-1] if latencies_ms else 0.0,
        peak,
    )


def _bench_stdnum_isin(corpus: list[str]) -> tuple[float, float, int]:
    try:
        import stdnum.isin as stdnum_isin  # noqa: WPS433
    except ImportError:
        return 0.0, 0.0, 0
    tracemalloc.start()
    t0 = time.perf_counter()
    latencies_ms: list[float] = []
    for s in corpus:
        s_t0 = time.perf_counter()
        try:
            stdnum_isin.validate(s)
        except Exception:
            pass
        latencies_ms.append((time.perf_counter() - s_t0) * 1000)
    elapsed = time.perf_counter() - t0
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return (
        len(corpus) / elapsed if elapsed > 0 else float("inf"),
        statistics.quantiles(latencies_ms, n=20, method="inclusive")[-1] if latencies_ms else 0.0,
        peak,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iters", type=int, default=10_000,
                        help="Iterations per workload per run (default: 10000)")
    parser.add_argument("--runs", type=int, default=5,
                        help="Number of runs per workload (default: 5)")
    parser.add_argument("--seed", type=int, default=1337,
                        help="Random corpus seed (default: 1337)")
    args = parser.parse_args(argv)

    workloads = [
        ("MOD_11_2 (ISBN-10 numeric)", MOD_11_2, _DIGITS, _bench_stdnum_isbn),
        ("MOD_37_2 (alphanumeric)", MOD_37_2, _ALNUM, _bench_stdnum_mod37_2),
        ("MOD_97_10 (IBAN numeric)", MOD_97_10, _DIGITS, _bench_stdnum_mod97_10),
        ("MOD_661_26 (ISIN alnum)", MOD_661_26, _ALNUM, _bench_stdnum_isin),
        ("MOD_661_26 (CUSIP alnum)", MOD_661_26, _ALNUM, _bench_stdnum_cusip),
        ("MOD_1271_36 (alphanumeric)", MOD_1271_36, _ALNUM, _bench_stdnum_mod37_2),
    ]

    results: list[dict] = []
    print(f"Benchmarking iso7064-pure vs python-stdnum — "
          f"{args.iters:,} iters × {args.runs} runs per workload")
    print()
    for name, system, alphabet, stdnum_bench in workloads:
        corpus = _make_corpus(args.iters, alphabet, seed=args.seed)
        our_runs, stdnum_runs, our_peaks, stdnum_peaks, our_p95s, stdnum_p95s = (
            [], [], [], [], [], []
        )
        for _ in range(args.runs):
            ops, p95, peak = _bench_round_trip(system, corpus)
            our_runs.append(ops)
            our_peaks.append(peak)
            our_p95s.append(p95)
            ops, p95, peak = stdnum_bench(corpus)
            stdnum_runs.append(ops)
            stdnum_peaks.append(peak)
            stdnum_p95s.append(p95)
        ours = statistics.mean(our_runs)
        theirs = statistics.mean(stdnum_runs) if any(stdnum_runs) else 0.0
        results.append({
            "name": name,
            "iso7064_pure": ours,
            "stdnum": theirs,
            "iso7064_pure_peak_mem": max(our_peaks),
            "stdnum_peak_mem": max(stdnum_peaks),
            "iso7064_pure_p95_ms": statistics.mean(our_p95s),
            "stdnum_p95_ms": statistics.mean(stdnum_p95s),
        })
        print(
            f"  {name:<32} iso7064-pure: {ours:>10,.0f} ops/s  "
            f"stdnum: {theirs:>10,.0f} ops/s  "
            f"ratio: {(ours/theirs if theirs else 0):.2f}x"
        )

    # Update BENCHMARK.md under the "## Latest run" heading.
    bench_md = _REPO / "benchmarks" / "BENCHMARK.md"
    if bench_md.exists():
        text = bench_md.read_text()
        table = _format_table(results)
        marker = "## Latest run"
        if marker in text:
            head, tail = text.split(marker, 1)
            new_text = head + marker + "\n\n" + table + tail
        else:
            new_text = text + "\n\n## Latest run\n\n" + table
        bench_md.write_text(new_text)
        print(f"\nUpdated {bench_md}")

    return 0


def _format_table(results: list[dict]) -> str:
    lines = [
        "| Workload | iso7064-pure (ops/s) | stdnum (ops/s) | Ratio | iso7064-pure p95 (ms) | stdnum p95 (ms) | iso7064-pure peak (KB) | stdnum peak (KB) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        ratio = r["iso7064_pure"] / r["stdnum"] if r["stdnum"] else 0.0
        lines.append(
            f"| {r['name']} | {r['iso7064_pure']:,.0f} | {r['stdnum']:,.0f} | "
            f"{ratio:.2f}x | {r['iso7064_pure_p95_ms']:.3f} | {r['stdnum_p95_ms']:.3f} | "
            f"{r['iso7064_pure_peak_mem']/1024:.0f} | {r['stdnum_peak_mem']/1024:.0f} |"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())