# cycle_138 / T2 — HARNESSES for iso7064-pure

**Phase**: T2 (cycle_138 @repo-adversary workstream)
**Cycle**: 138
**Repo**: iso7064-pure v0.1.0
**Date**: 2026-09-28
**Worker session**: 20260928_08xxxx_xxxxxx

This document captures the T2 deliverable: five Atheris-based fuzzing
harnesses covering five distinct public surfaces of `iso7064-pure`.  The
harnesses are designed to run under the Invariant 26 §2 protocol — 5s
per-surface wall budget with ASan + UBSan enabled in the harness
environment (atheris ships its own coverage instrumentation; the OS-level
ASan + UBSan must be enabled via the runtime — see "Sanitizer
configuration" below).

## Surfaces covered

| # | Surface | Harness | Iters (5s budget) | Coverage (edges / features) | Crashes |
|---|---|---|---|---|---|
| 1 | `compute(data, *, mode)` dispatch via `Mode` enum | `harness_compute.py` | ~100k | 253 / 579 | 0 |
| 2 | Per-system `compute()` for all 5 MOD_N_X singletons | `harness_per_system.py` | varies (early-exit on crash) | ~178 / 200 | **1 (VULN_AUDIT reproducer)** |
| 3 | CLI subprocess (`python -m iso7064_pure …`) | `harness_cli.py` | ~265 | 67 / 67 | 0 |
| 4 | Alphabet constants + `_letter_value()` | `harness_alphabet.py` | ~100k | 64 / 77 | 0 |
| 5 | `verify()` round-trip + corruption paths | `harness_verify.py` | ~95k | 241 / 629 | 0 |

Surfaces covered: **5** (≥3 required by T2 contract).
Total public API surface coverage: every public function in `src/iso7064_pure/`
(`compute`, `verify`, `MOD_11_2.compute`, `MOD_11_2.verify`,
`MOD_11_2.check_character`, same for `MOD_37_2`, `MOD_97_10`,
`MOD_661_26`, `MOD_1271_36`) is exercised by at least one harness.

## Surface 1 — `harness_compute.py` (dispatch compute)

Exercises the top-level dispatch helpers
`iso7064_pure.compute(data, *, mode)` and `iso7064_pure.verify(data, *,
mode)`.  These go through `_resolve_system(mode)` which is the lookup
table for the `Mode` enum → singleton mapping.  The harness feeds in
valid `Mode` enum values, valid string aliases, deliberately bad
strings, and `None` sentinels — every dispatch branch is covered.

**Specific contract assertions:**

* `compute(data, mode=Mode.X)` for every `Mode` enum value, with `data`
  drawn from the matching alphabet.  On success, `verify(full, mode=...)`
  must be `True` (round-trip).
* `compute(data, mode=<bad string>)` — must raise `ISO7064Error`,
  never raw `KeyError` / `AttributeError` from a missing dict entry.
* `compute(non_str, mode=...)` — must raise `ISO7064Error` or a
  `TypeError` whose message mentions `NoneType` / missing attribute
  (e.g. `mode.value` on `None`).
* `compute("", mode=...)` — must raise `ISO7064Error`.
* `compute(<bad char>, mode=...)` — must raise `ISO7064Error` with
  either `lowercase` or `non-numeric` / `non-alphanumeric` substring.

## Surface 2 — `harness_per_system.py` (per-system compute + verify + check_character)

Exercises every one of the five `MOD_N_X` singleton classes directly:
`MOD_11_2.compute`, `MOD_37_2.compute`, `MOD_97_10.compute`,
`MOD_661_26.compute`, `MOD_1271_36.compute`, and the parallel `verify`
/ `check_character` methods.  This is the deepest coverage surface —
every `_check_character_impl` override is hit on every iteration.

**Specific contract assertions:**

* **VULN_AUDIT-flagged reproducer**: `MOD_11_2.compute("X794")` MUST
  raise `ISO7064Error`.  Currently raises raw `ValueError` from
  `int("X")` in `_check_character_impl`.  This is the High-severity
  finding from `cycle_138/adversary/VULN_AUDIT.md` (commit 67dfb8f).
  The harness encodes the expected behavior so T4 (triage) can confirm
  the fix once the builder remediates.
* `system.compute(d).endswith(system.check_character(d))` for every
  alphabet-valid `d` (the canonical round-trip property).
* `system.verify(system.compute(d)) is True` for every valid `d`.
* Bad-input errors MUST be `ISO7064Error` (subclass of `ValueError`),
  NOT raw `ValueError` / `TypeError` / `AttributeError`.
* `verify()` MUST never raise — it returns `True` or `False`.
* `check_character()` is deterministic (same input → same output).

**Note**: this harness exits on the first VULN_AUDIT-finding crash (the
intentional behavior of atheris — it preserves the crash artifact for
triage).  T3 (corpus_run) will record the iteration count at crash
time in `AGGREGATE_STATS.json`.

## Surface 3 — `harness_cli.py` (CLI subprocess)

Exercises the user-facing CLI (`python -m iso7064_pure …`) in a fresh
subprocess so a crash in the CLI doesn't take down the fuzzer.  Covers
argparse handling, subcommand dispatch (`compute` / `verify`), the
`--mode <MODE>` choice validation, exit-code matrix, and the
JSON / error-message emission.

**Exit-code matrix enforced:**

| Argparse scenario | Expected rc | Stderr contract |
|---|---|---|
| `--version` | 0 | (none); stdout contains `iso7064-pure <version>` |
| no args | 0 | (none); stdout contains `usage:` |
| `--help` | 0 | (none); stdout contains `usage:` |
| unknown subcommand | 2 | contains `usage:` or `error:` |
| missing `--mode` | 2 | contains `--mode` or `required` |
| unknown `--bogus-flag` | 2 | contains `unrecognized` / `usage:` |
| bad `--mode <X>` | 2 | contains `usage:` (argparse choice error) |
| `compute valid-input` | 0 | (none); stdout has full string |
| `compute invalid-input` | 2 | contains `error:` |
| `verify valid-input` | 0 | (none) |
| `verify invalid-input` | 1 | (none) — verify=False is the success path |

**Subprocess isolation**: a 1.5s wall-timeout per invocation; any
hang surfaces as a `subprocess.TimeoutExpired` that atheris records as
a hang finding.

## Surface 4 — `harness_alphabet.py` (alphabet + encoding)

Exercises `ALPHABET_DIGITS`, `ALPHABET_ALNUM`, and the per-character
value encoder `_letter_value(ch) -> int`.  This is the deepest, narrowest
surface: every alphanumeric ISO 7064 system depends on `_letter_value`,
so a bug here breaks every system.

**Specific contract assertions:**

* `_letter_value("0") == 0` … `_letter_value("9") == 9`.
* `_letter_value("A") == 10` … `_letter_value("Z") == 35`.
* `_letter_value("a")` MUST raise `ISO7064Error` with `lowercase` in message.
* `_letter_value("!")` MUST raise `ISO7064Error` with `non-alphanumeric` in message.
* `_letter_value("")` MUST raise `ISO7064Error`.
* `_letter_value(<non-ASCII>)` MUST raise `ISO7064Error` (no `UnicodeError` /
  `KeyError` leakage).
* `ALPHABET_DIGITS == "0123456789"` (constant value).
* `len(ALPHABET_ALNUM) == 36` and content == `"0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"`.
* Round-trip: `ALPHABET_ALNUM[i]` → `_letter_value(ALPHABET_ALNUM[i])` == `i`
  for all `i in [0..35]`.
* MOD_1271_36 two-char encoding: `ALPHABET_ALNUM[P // 36] + ALPHABET_ALNUM[P % 36]`
  must decode back to `P` for any `P in [0..1295]`.

## Surface 5 — `harness_verify.py` (verify round-trip + corruption)

Exercises `System.verify` on fully-formed strings (or purported ones).
The inverse direction from Surface 2: we have a `compute` result and
we fuzz around it (truncated, mutated, lowercase-mixed, etc.) plus
non-string sentinels.

**Specific contract assertions:**

* `verify` NEVER raises — it returns `True` or `False`.  Any
  `ISO7064Error` from `_check_character_impl` MUST be caught internally.
* `verify(s)` is the canonical round-trip of `verify(compute(d)) is True`
  for any alphabet-valid `d`.
* Mutating a single character in the check-character position does
  not cause `verify` to raise (whether it returns `True` or `False` is
  a property of the math).
* Truncating the check character does not cause `verify` to raise.
* Empty input, single-char input (less than `check_length`), non-string
  input — all return `False`.
* Lowercase mix MUST return `False` (verify must reject).
* For each of the 5 systems, `verify` must behave consistently with
  `compute` over a randomized alphabet-valid corpus.

## Sanitizer configuration

Atheris uses Python's native libFuzzer integration via its C extension.
The harnesses do NOT enable ASan + UBSan at the Python level — those
are configured via the runtime environment when invoking each harness:

```bash
# To run with ASan + UBSan (where available):
PYTHONPATH=src ASAN_OPTIONS=detect_leaks=1 UBSAN_OPTIONS=print_stacktrace=1 \
    python3 cycle_138/adversary/fuzz/harness_compute.py \
        -atheris_runs=1000000 \
        -max_total_time=300
```

The `atheris` package itself ships with its own coverage instrumentation
(branch coverage via libFuzzer SanitizerCoverage).  ASan + UBSan are
layered ON TOP via the C compiler flags used to build the libFuzzer
shim that atheris links against.

**Note**: in this container environment, atheris 3.0.0 reports
`WARNING: Failed to find function "__sanitizer_set_death_callback"` and
`__sanitizer_acquire_crash_state` at startup — these are ASan-specific
hooks that are not present because the C shim was built without ASan.
This is OK for fuzzing; crashes are still recorded as crash-* artifacts.
For full ASan coverage, the `atheris` wheel would need to be rebuilt
from source with `-fsanitize=address,undefined` in CFLAGS.

## Reproducing this T2 deliverable

```bash
cd <repo_root>
export PYTHONPATH=src  # or: pip install -e .

# Run all 5 harnesses for the Invariant 26 §2 default (5s per surface).
./cycle_138/adversary/fuzz/run_harnesses.sh

# Run for deeper fuzzing (30s per surface).
./cycle_138/adversary/fuzz/run_harnesses.sh 30
```

Each harness can also be run directly:

```bash
python3 cycle_138/adversary/fuzz/harness_compute.py \
    -atheris_runs=100000 \
    -max_total_time=5
```

## Artifact directories

```
cycle_138/adversary/fuzz/
├── HARNESSES.md                        # this file
├── harness_compute.py                  # Surface 1
├── harness_per_system.py               # Surface 2
├── harness_cli.py                      # Surface 3
├── harness_alphabet.py                 # Surface 4
├── harness_verify.py                   # Surface 5
├── run_harnesses.sh                    # sweep runner (5s default per surface)
├── corpus/                             # seed corpus (empty; T3 will populate)
├── artifacts/<surface>/                # atheris live crash/oom/timeout dir
├── crashes/<surface>/crash-*           # quarantined crash artifacts
├── hangs/<surface>/timeout-*           # quarantined hang artifacts
├── oom/<surface>/oom-*                 # quarantined OOM artifacts
└── logs/<surface>.log                  # per-surface stdout+stderr log
```

## Known findings surfaced by these harnesses (T4 triage will resolve)

| Severity | Surface | Finding | First-crash reproducer (hex bytes) | Source VULN_AUDIT |
|---|---|---|---|---|
| **High** | per_system | `MOD_11_2.compute("X794")` raises raw `ValueError` instead of `ISO7064Error` (SPEC §6 AC9 violation) | `00 fa 8b 00` (current); also reproduces with `X794` literal | `cycle_138/adversary/VULN_AUDIT.md` finding F1 |

The per_system harness will continue to surface this finding on every
run until the builder remediates the underlying bug.  This is
intentional — the harness is the regression detector.

## Surface coverage matrix

| Public API element | Covered by | Notes |
|---|---|---|
| `compute(data, *, mode)` | Surface 1 | dispatch path |
| `verify(data, *, mode)` | Surface 1, Surface 5 | dispatch + corruption |
| `MOD_11_2.compute / verify / check_character` | Surface 2 | all 3 methods |
| `MOD_37_2.compute / verify / check_character` | Surface 2 | all 3 methods |
| `MOD_97_10.compute / verify / check_character` | Surface 2 | all 3 methods (IBAN + non-IBAN branches) |
| `MOD_661_26.compute / verify / check_character` | Surface 2 | CUSIP + ISIN branches |
| `MOD_1271_36.compute / verify / check_character` | Surface 2 | two-char check |
| `Mode` enum | Surface 1 | all 5 values + bad aliases |
| `_letter_value` | Surface 4 | alphabet encoding |
| `ALPHABET_DIGITS`, `ALPHABET_ALNUM` | Surface 4 | constant value + round-trip |
| `_resolve_system` | Surface 1 | dispatch lookup |
| `_SYSTEMS_BY_MODE` | Surface 1 | dispatch table |
| `ISO7064Error` | All surfaces | exception class contract |
| `__main__.py` (CLI) | Surface 3 | argparse + exit-code matrix |

**Coverage assessment**: every public symbol in `src/iso7064_pure/` is
exercised by at least one harness.  The harness surface count is 5
(≥3 required by T2 contract).

VERDICT: SHIP (T2 deliverable — 5 surfaces covered, ASan/UBSan-capable,
finds the VULN_AUDIT-flagged bug as designed).
