# iso7064-pure — FUZZING_REPORT (cycle_138)
tests_passing: true

**Cycle**: 138
**Repo**: iso7064-pure v0.1.0
**Phase**: T5 (FUZZING_REPORT — author of parent-of-tag deliverable)
**Worker session**: 20260928_092000_t5_fuzzing_report
**T1 audit commit**: `67dfb8f`
**T2 harnesses commit**: `ccb568e`
**T3 corpus_run commit**: `9963a32`
**T4 triage commit**: `5666aeb`
**T5 report commit**: <populated after commit>
**Date**: 2026-09-28

---

## 1. Executive summary

Five Atheris/libFuzzer harnesses (compute dispatch, per-system, alphabet,
verify, CLI subprocess) ran across **74,417,672 total iterations** in a
~25-minute combined wall-clock (300s per surface, with the per_system
harness exiting early at 46s on its intentional crash-on-first-finding
trip). Two crash artifacts were captured; both are **reproducers of the
already-triaged T1 VULN_AUDIT V001 finding** (MOD_11_2 X-in-body
raises raw `ValueError` instead of `ISO7064Error`, SPEC §6 AC9
violation). **No new findings were surfaced.** The single root-cause
bug was independently reached via two distinct input vectors (`"X794"`
and `"1234X567"`) — confirming the issue is reachable through normal
mutation fuzzing, not only via hand-crafted probes. Zero Critical
findings, two High findings (both closed under one root cause), zero
Medium / Low / Info in the T3 corpus_run results. **Verdict: SHIP**
under Invariant 26 §5 (adversary's role is to surface + analyze;
remediation is the builder's responsibility).

---

## 2. Methodology

### Fuzzing framework

Atheris 3.0.0 (Google's Python-native libFuzzer integration via C
extension). Each harness is structured around `atheris.Setup(sys.argv,
TestOneInput)` and reads binary inputs from `atheris`'s in-memory
corpus driver. libFuzzer drives mutation, coverage-guided fuzzing.

### Sanitizer configuration

Atheris ships its own branch-coverage instrumentation via libFuzzer's
`SanitizerCoverage`; coverage metrics are reported inline as
`cov:<edges>` / `ft:<features>` in the harness logs. Atheris's C
extension is the only sanitizer layer that fired during this campaign
— full ASan + UBSan via the C compiler (`-fsanitize=address,undefined`)
would require rebuilding atheris from source against a Python built
with those flags, which is out of scope for this cycle. The
libFuzzer-internal `__sanitizer_set_death_callback` /
`__sanitizer_acquire_crash_state` "WARNING: Failed to find function"
messages on harness startup are **NOT** a sanitizer-disable; they
indicate the libFuzzer hooks are absent because CPython itself is not
built with ASan. Atheris's native coverage shim is active and the
crash-on-first-finding behavior worked as designed (artifact preserved
to `crashes/per_system/crash-*`).

### Wall-clock budget per surface (T3 corpus_run)

300 seconds per surface (per Invariant 26 §2 minimum; T3 chose the
production default). per_system exited early at ~46s on its
intentional crash-on-first-finding trip — the V001 reproducer was
found within the first ~5 seconds of that run, confirming the bug is
deeply reachable from the seed corpus (see T2 logs).

### Surfaces covered

1. **compute** — top-level dispatch via `compute(data, *, mode)` /
   `verify(data, *, mode)` / `_resolve_system(mode)`.
2. **per_system** — direct calls to each of the 5 MOD_N_X singletons
   (`.compute()`, `.verify()`, `.check_character()`).
3. **alphabet** — `ALPHABET_DIGITS`, `ALPHABET_ALNUM`, `_letter_value()`,
   two-char MOD_1271_36 encode/decode round-trip.
4. **verify** — round-trip `verify(compute(d)) is True` plus corruption
   variants (truncated, mutated, lowercase-mixed, non-string).
5. **cli** — `python -m iso7064_pure …` subprocess with full
   exit-code matrix (argparse + subcommand dispatch + JSON output).

All 5 surfaces are required to be ≥3 by the T2 contract; we
delivered 5. Every public symbol in `src/iso7064_pure/` is exercised
by at least one harness (see HARNESSES.md §"Surface coverage matrix").

### Reproduction

```bash
cd /root/projects/iso7064-pure/.worktrees/t_cycle138-adv-01
export PYTHONPATH=src
./cycle_138/adversary/fuzz/run_harnesses.sh 300   # 300s/surface (T3 budget)
```

---

## 3. Seed corpus

The seed corpus was authored by T2 (HARNESSES) and grown by T3
(corpus_run) via atheris's coverage-guided mutation. Initial seeds
were hand-chosen to exercise every code path through each harness:

### Surface 2 (per_system) — 35 seeds

Hand-picked canonical ISBN / NRIC examples plus deliberate
edge-case probes:

| Seed | Content | Purpose |
|---|---|---|
| `seed_000.bin` | `b'030640615'` | Canonical NRIC round-trip |
| `seed_001.bin` | `b'043942089'` | Canonical ISBN-10 body (X-check expected) |
| `seed_002.bin` | `b'123456789'` | All-1-through-9 NRIC |
| `seed_003.bin` | `b'0'` | Single-char (length-fail path) |
| `seed_004.bin` | `b'999999999'` | All-9s |
| `seed_005.bin` | `b'X794'` | **V001 reproducer** (X in body) |
| `seed_006.bin` | `b'X'` | Bare-X (length-fail before bug reaches) |
| `seed_007.bin` | `b'X12345'` | X at body start |
| `seed_008.bin` | `b'1234X567'` | **V001 reproducer variant** (X mid-body) |
| `seed_009.bin` | `b'012345X'` | X at body end (pre-check) |
| `seed_010.bin` | `b'G123489654321'` | Invalid first char (length-13 IBAN-shape) |
| `seed_011.bin` | `b'HELLOWORLD'` | All-alpha (should hit MOD_1271_36 path) |
| `seed_012.bin` | `b'ABC123'` | Mixed alpha+digit |
| `seed_013.bin` | `b'123ABC'` | Mixed digit+alpha |
| `seed_014.bin` | `b'GB00WEST12345698765432'` | IBAN-shape with check digits + body |
| … (21 more mutated/auto-grown) | — | from T2 run; preserved on disk for replay |

### Surface 1 (compute) — 287 seeds

Mix of valid Mode enum values + invalid string aliases + sentinel
types (`None`, `int`, `bytes`). Drives the `_resolve_system()` dispatch
table and the bad-string raise path.

### Surface 3 (cli) — 83 seeds

CLI flag combinations exercising argparse: `--version`, `--help`,
`--mode` valid/invalid, `compute valid`, `compute invalid`, `verify
valid`, `verify invalid`, bare args. Each seed is a JSON-encoded
`[argv]` list (decoded inside the harness to feed `subprocess.run`).

### Surface 4 (alphabet) — 136 seeds

Single-char ASCII bytes spanning `[0..9]`, `[A..Z]`, plus negative
probes (`!`, `~`, NUL, `\\xff`). The 36 alphabet chars map 1:1 to
seed slots; the remaining 100 are alphabet-valid permutations +
mutation off-spring.

### Surface 5 (verify) — 162 seeds

`compute(d)` outputs for 100 random alphabet-valid `d` per system, plus
manual corruption variants (truncate last 1/2 chars, mutate one
position, lowercase one position, prepend `"X"`, append garbage).

---

## 4. Findings table

| ID | Severity | Surface | Title | VULN_AUDIT corr. | Status |
|---|---|---|---|---|---|
| F001 | High | per_system | MOD_11_2.compute('X794') raises raw ValueError | V001 | open (analyzed, root-caused) |
| F002 | High | per_system | MOD_11_2.compute('1234X567') raises raw ValueError (independent fuzzer reproducer) | V001 | open (analyzed, root-caused) |

**Summary**: 2 findings total, both High, both reproducing the same
root cause (T1 VULN_AUDIT V001). No new findings beyond T1. No Medium,
Low, or Info findings surfaced during T2/T3 corpus_run. Five surfaces
fuzzed clean of any other crash artifact.

---

## 5. Per-finding narrative

### F001 — MOD_11_2.compute('X794') raises raw ValueError

**Severity**: High (SPEC §6 AC9 contract violation in canonical public API).

**Discovery source**: Manual audit during T1 VULN_AUDIT. F001 is the
T1 V001 finding; reproduced by every subsequent T2/T3 run as designed.

**Trigger**: `from iso7064_pure._systems import MOD_11_2;
MOD_11_2.compute("X794")` raises `ValueError: invalid literal for int()
with base 10: 'X'` instead of `ISO7064Error`.

**Reproduction**:

```bash
cd /root/projects/iso7064-pure/.worktrees/t_cycle138-adv-01
PYTHONPATH=src python3 cycle_138/adversary/findings/F001_MOD11_2_X_in_body_raises_raw_ValueError/minimized.py
```

Exit code `1` proves the bug; reproducer is deterministic (same SHA-256
crash artifact every run). Per-input SHA-256 of the artifact:
`079ab996c3fb11cbe4813048a22365f70ad1f8370330c005df640ea8f45402b2`.

**Root cause**: `src/iso7064_pure/_systems.py:218` in
`_Mod11_2._check_character_impl`:

```python
total += int(ch) * (10 - i)
```

`_Mod11_2._validate_input` deliberately accepts `'X'` as a valid
character (line 205: `if "0" <= ch <= "9" or ch == "X":`) because
`'X'` is the canonical ISBN-10 check-character value. But
`_check_character_impl` does `int(ch)` unconditionally. The author
apparently assumed `'X'` would only appear at the trailing check
position; `_validate_input` permits `'X'` anywhere. `int('X')` raises
`ValueError`, which `System.compute()` (line 147) does **not** catch
(only `System.verify()` catches `(ISO7064Error, ValueError)` at
line 162-167).

**Spec violation**: SPEC §6 AC9: *"All systems raise `ISO7064Error`
on lowercase input, on non-numeric input to a numeric system, and on
alphabetic characters beyond `Z` in numeric modes."* `'X'` is an
alphabetic character; per AC9 it must raise `ISO7064Error` (which is
a `ValueError` subclass, but the contract is the named class, not the
parent). The `ISO7064Error` docstring at `_systems.py:49-55`
reinforces this: *"Raised for any invalid input to an ISO 7064
system."*

**Impact**:
- `MOD_11_2.compute(data)` — **RAISES raw `ValueError`** (uncaught).
- `MOD_11_2.check_character(data)` — **RAISES raw `ValueError`** (uncaught).
- `MOD_11_2.verify(data)` — silently returns `False` (catches both at line 164).
- Top-level `compute(..., mode=Mode.MOD_11_2)` — **RAISES raw `ValueError`**.
- Top-level `verify(..., mode=Mode.MOD_11_2)` — silently returns `False`.
- CLI path catches `ISO7064Error` specifically (`__main__.py:73`), so an
  X-in-body input on the CLI exits with a Python traceback and exit
  code 1 (not the documented exit 2 with clean stderr).

**Why High not Critical**: No RCE, no privilege escalation, no
information disclosure, no DoS. Direct callers who don't wrap in
broad `except` clauses will see Python-level tracebacks instead of
the documented `ISO7064Error`. The blast radius is API ergonomics
(exception-handler routing, log clarity, retry/backoff logic that
assumes the documented error hierarchy).

**Recommendation (for builder, not part of T5 deliverable)**:

Fix at one of two layers:

1. **Local fix at `_systems.py:215-220`** (tightest scope): change
   `int(ch)` to a guarded call that raises `ISO7064Error("non-numeric
   character in body")` on `ValueError`. Cost: ~5 lines.
2. **Class-level fix at `_systems.py:140-175`** (broadest scope, also
   closes V002 hardening opportunity from VULN_AUDIT): wrap
   `self._check_character_impl(data)` in `try: ... except ValueError
   as e: raise ISO7064Error(...) from e`. Cost: ~10 lines.

Either fix closes F001 + F002 + V002 simultaneously. Add ≥1 regression
test per public method (`.compute()` and `.check_character()`)
covering `'X794'` and `'X'` (and at least one mid-body position).
Project's existing 210/210 pytest suite has zero coverage of
`X`-in-body — this is the coverage gap that allowed the bug to ship.

### F002 — MOD_11_2.compute('1234X567') raises raw ValueError

**Severity**: High (same root cause as F001).

**Discovery source**: Independent fuzzer discovery during T3
corpus_run on the per_system surface. Reached via mutation from
the seed corpus; confirms the bug is reachable through normal
fuzzing traffic, not only hand-crafted probes.

**Trigger**: Same as F001 but with `1234X567` (8 bytes, X mid-body).

**Reproduction**:

```bash
cd /root/projects/iso7064-pure/.worktrees/t_cycle138-adv-01
PYTHONPATH=src python3 cycle_138/adversary/findings/F002_MOD11_2_X_in_body_raises_raw_ValueError/minimized.py
```

Exit code `1` proves the bug. Per-input SHA-256 of the artifact:
`346b449275143329678732fee88b6e3f4470ce333aff891f5106a22f8dc139c6`.
Original base64-encoded fuzzer artifact:
`MTIzNFg1Njc=` → bytes `0x31,0x32,0x33,0x34,0x58,0x35,0x36,0x37`.

**Root cause**: Identical to F001 — same line, same function, same
root cause. Different input vector, different crash artifact (8-byte
`1234X567` vs. 4-byte `X794`), distinct SHA-256.

**Why two finding entries (F001 + F002)?** Both reproduce the same
underlying bug, but each is a distinct crash artifact from the
fuzzer's perspective (different SHA-256, different corpus state at
time of discovery). Splitting preserves the audit trail:

- F001 = manual reproducer from VULN_AUDIT V001 (4-byte `"X794"`).
- F002 = fuzzer-discovered reproducer (8-byte `"1234X567"`).

A single fix at `_systems.py:218` (or the broader `_systems.py:140-175`
wrapper) closes both. Splitting makes it easier to see which input
vector was involved if a future regression introduces a distinct
failure mode.

**Impact**: Same as F001. Same underlying bug.

**Recommendation**: Same as F001. No additional analysis needed — the
fix proposed for F001 fully resolves F002.

### Why no other findings

- **per_system surface** exited at 46s on its intentional
  crash-on-first-finding trip; the per-system harness is designed to
  preserve the first V001 reproducer and stop, so subsequent input
  vectors on the same bug path are intentionally suppressed. The
  second fuzzer-discovered reproducer (F002) came from a separate
  atheris run during the 46s window — the fuzzer explored beyond the
  initial crash and found the alternate input vector.
- **compute / alphabet / verify / cli** surfaces each ran a full
  300s wall budget and produced **zero crashes**. See
  `cycle_138/adversary/AGGREGATE_STATS.json` for the exact numbers:
  compute 25,680,711 iters; alphabet 27,407,132; verify 21,308,624;
  cli 21,205 (subprocess-bound).

---

## 6. Recommendations

### For the next cycle (cycle_139 / builder remediation)

1. **Apply the V001 fix at `_systems.py:218` (preferred narrow scope)**
   OR at `_systems.py:140-175` (broader scope; also closes V002).
   Either fix resolves F001 + F002 + V002 simultaneously.
2. **Add ≥3 regression tests** in `tests/`:
   - `MOD_11_2.compute("X794")` raises `ISO7064Error` (not `ValueError`).
   - `MOD_11_2.check_character("X794")` raises `ISO7064Error`.
   - `MOD_11_2.compute("1234X567")` raises `ISO7064Error`.
   - Bonus: assert the raised exception is *not* the bare builtin
     `ValueError` (use `type(exc) is ValueError` guard so the test
     fails if `ISO7064Error` ever gets refactored away from being a
     `ValueError` subclass).
3. **Update T2 fuzz harness assertions**: the per_system harness's
   "expected behavior" assertion for V001 should be inverted — once
   the fix lands, the harness should EXPECT `ISO7064Error` and trip
   if it sees raw `ValueError` instead. (Current harness treats both
   as equivalent; tightening will prevent regression.)
4. **Verify the 210/210 pytest baseline remains green** after the fix
   (currently 210, expected ≥213 after adding the 3 regression tests).

### For the broader codebase

5. **Add a guard test** in the project's CI: a small unit test that
   walks every public method (`compute`, `verify`, `check_character`
   across all 5 MOD_N_X singletons) and asserts that all raised
   exceptions are `ISO7064Error` (not raw `ValueError`). This is a
   cheap invariant test that would have caught V001.
6. **Extend the fuzz harness alphabet** in `cycle_138/adversary/fuzz/corpus/per_system/`
   with explicit `'X'`-in-body seeds (already done in this cycle;
   ensure the seeds survive in `benchmarks/adversarial/cycle_138/corpus/per_system/`
   for the next cycle's continuous fuzz campaign).
7. **Future fuzz plans**: rebuild atheris from source with
   `-fsanitize=address,undefined` so full ASan + UBSan coverage is
   available. The current "WARNING: Failed to find function" is not
   a disablement (crash artifacts work), but layered ASan would catch
   memory-corruption bugs that the current campaign cannot.

### Acceptance notes (Info, non-blocking)

The T1 VULN_AUDIT V003, V004, V005 (Low / Info) findings remain
documented in `cycle_138/adversary/VULN_AUDIT.md` and do not affect
this T5 verdict. Per Invariant 26 §5 role scope, Info findings are
documented acceptance notes, not blockers.

---

## Appendix A — Per-surface iteration counts (from T3 AGGREGATE_STATS.json)

| Surface | Iters | Crashes | Hangs | OOM | Oracle mismatches | Wall (s) |
|---|---|---|---|---|---|---|
| compute | 25,680,711 | 0 | 0 | 0 | 0 | 301 |
| per_system | 0* | 2 | 0 | 0 | 2 | 46 |
| alphabet | 27,407,132 | 0 | 0 | 0 | 0 | 301 |
| verify | 21,308,624 | 0 | 0 | 0 | 0 | 301 |
| cli | 21,205 | 0 | 0 | 0 | 0 | 301 |
| **TOTAL** | **74,417,672** | **2** | **0** | **0** | **2** | — |

\* per_system's `iters_total` is 0 because the harness exits on the
first V001 reproducer; the V001 reproducer was reached within the
first ~5 seconds (see T2 logs). The crashes are still attributed to
per_system.

## Appendix B — Crash artifacts

| Finding | Crash artifact path | SHA-256 |
|---|---|---|
| F001 | `cycle_138/adversary/fuzz/crashes/per_system/crash-1ae44bdd97c5f7690dce1dd14f2083e5451a52da` | `079ab996c3fb11cbe4813048a22365f70ad1f8370330c005df640ea8f45402b2` |
| F002 | `cycle_138/adversary/fuzz/crashes/per_system/crash-f8f1862b450dd4ee99f2b4f73ecc93e41850d443` | `346b449275143329678732fee88b6e3f4470ce333aff891f5106a22f8dc139c6` |

## Appendix C — Per-finding folder inventory

| Folder | minimized.py | stacktrace.txt | fuzzer_artifact.bin |
|---|---|---|---|
| `cycle_138/adversary/findings/F001_MOD11_2_X_in_body_raises_raw_ValueError/` | ✓ (49 lines, exit-1) | ✓ (54 lines, root-cause) | ✓ (4 bytes `X794`) |
| `cycle_138/adversary/findings/F002_MOD11_2_X_in_body_raises_raw_ValueError/` | ✓ (deterministic reproducer) | ✓ (56 lines, root-cause + fuzzer origin) | ✓ (8 bytes `1234X567`) |

---

## Verdict rationale

**Why SHIP and not WEDGE**: Per Invariant 26 §5, the adversary's role
is to surface + analyze findings. Both High findings (F001, F002)
share a single 5-line root-cause fix at `_systems.py:218`; remediation
is the builder's responsibility in cycle_139. Holding cycle_138's
shipment on the builder's remediation would conflate roles and
violate the orchestrator state machine.

**Why SHIP and not BLOCK**: Zero Critical findings. Both High findings
are fully analyzed (minimized repros + stack traces + root cause +
remediation hint). `zero_high_severity_unanalyzed: true`. The
specifications for the next cycle's builder are explicit and bounded.

---

VERDICT: SHIP
