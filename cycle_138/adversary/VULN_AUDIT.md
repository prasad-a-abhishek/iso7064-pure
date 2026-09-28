# iso7064-pure — Vulnerability Audit (cycle_138)

## Methodology

Manual source review of `src/iso7064_pure/` against ISO/IEC 7064:2021 §7
("Information security and integrity considerations") and the SPEC §6
AC9 error contract ("All systems raise `ISO7064Error` on invalid input").

### Surfaces covered (4)

1. **Public API** — `compute()` / `verify()` / `check_character()` /
   `Mode` enum dispatch (`__init__.py`, `_systems.py:539-554`)
2. **Per-system classes** — `_Mod11_2`, `_Mod37_2`, `_Mod97_10`,
   `_Mod661_26`, `_Mod1271_36` (`_systems.py:183-522`)
3. **Shared alphabet helpers** — `ALPHABET_DIGITS`, `ALPHABET_ALNUM`,
   `_letter_value` (`_alphabet.py`, `_systems.py:67-75`)
4. **CLI entrypoint** — `python -m iso7064_pure` (`__main__.py`)

### Probe vectors exercised

- Type confusion: `None`, `int`, `bytes`, `str`, `Mode` enum, plain `str` mode
- Boundary: empty string, length-1, length-2, length-1,000,000
- Unicode: full-width digits (`U+FF10`), emoji (`U+1F600`),
  combining diacritics (NFC vs NFD), mathematical bold digits
  (`U+1D7D8`), NUL (`U+0000`), ANSI ESC (`U+001B`)
- MOD_11_2 specific: `'X'` as canonical check char AND mid-body `'X'`
  (e.g. `'X794'`, `'1X1'`, `'0X1X'`)
- IBAN-shaped: 4-char pseudo-IBAN (`'AB12'`), lowercase IBAN prefix
- Error-message inspection for information leakage
- Recursion / stack-exhaustion (not applicable — all algorithms are
  iterative)

All probes executed against `python3 -c "..."` against the live
`import iso7064_pure` in `e4a9bc4`.

---

## Findings (severity-ranked)

| ID    | Severity | Surface          | Location                            | Summary                                                                                                                       |
|-------|----------|------------------|-------------------------------------|-------------------------------------------------------------------------------------------------------------------------------|
| V001  | High     | Public API       | `src/iso7064_pure/_systems.py:215-220` (`_Mod11_2._check_character_impl`) | `MOD_11_2.compute('X794')` / `.check_character('X794')` raise raw `ValueError` ("invalid literal for int() with base 10: 'X'") instead of `ISO7064Error`. SPEC §6 AC9 contract violation. |
| V002  | Medium   | Public API       | `src/iso7064_pure/_systems.py:140-175` (`System.compute` / `System.check_character`) | `_check_character_impl` is called unguarded; any future bug in any subclass that raises a non-`ISO7064Error` / non-`ValueError` would propagate raw. Only `verify()` catches `(ISO7064Error, ValueError)`. |
| V003  | Low      | Internal alphabet| `src/iso7064_pure/_systems.py:67-75` (`_letter_value`) | `ord(ch) - ord('A') + 10` overflow is impossible (Z=35 < 37), but helper has no type guard — relies on caller. Not exploitable; just a style note. |
| V004  | Info     | CLI              | `src/iso7064_pure/__main__.py:73-75` | Error messages echo the offending character via `f"... {exc.message}"` (uses `repr()` from error construction). This is by design for SPEC AC9 substring matching; flagged as informational only. |
| V005  | Info     | Public API       | `src/iso7064_pure/_systems.py:541` (`_resolve_system`) | Top-level `compute/verify` dispatch silently accepts a bare string (`mode='MOD_11_2'`) via `mode.value if hasattr(mode, 'value') else str(mode)`. Could mask a typo; not a security boundary, just an API footgun. |

### Detailed narrative

#### V001 (High) — MOD_11_2 raises raw `ValueError` on `'X'` in body

**Reproduction:**

```python
>>> from iso7064_pure import compute, Mode
>>> compute("X794", mode=Mode.MOD_11_2)
Traceback (most recent call last):
  ...
ValueError: invalid literal for int() with base 10: 'X'
```

**Root cause (`_systems.py:201-220`):** `_Mod11_2._validate_input`
deliberately accepts `'X'` as a valid character (line 205:
`if "0" <= ch <= "9" or ch == "X":`), because `'X'` is the canonical
check-character for ISBN-10 check digit value 10. But `_check_character_impl`
(line 217-218) does `int(ch) * (10 - i)` — `int('X')` raises `ValueError`
unconditionally. The author likely assumed `'X'` would only appear at
the *trailing* position (i.e. as check char), but `_validate_input`
permits `'X'` anywhere in the input.

**Contract violation:** SPEC §6 AC9 states "All systems raise
`ISO7064Error` on lowercase input, on non-numeric input to a numeric
system, and on alphabetic characters beyond `Z` in numeric modes".
`'X'` is an alphabetic character; per AC9 it must raise
`ISO7064Error`. The docstring at `_systems.py:49-55` reinforces this:
*"Raised for any invalid input to an ISO 7064 system."*

**Scope of impact:**

- `MOD_11_2.compute(data)` — **RAISES** raw `ValueError` (uncaught).
- `MOD_11_2.check_character(data)` — **RAISES** raw `ValueError` (uncaught).
- `MOD_11_2.verify(data)` — silently returns `False` (wraps in
  `(ISO7064Error, ValueError)` catch at line 164).
- Top-level `compute(..., mode=Mode.MOD_11_2)` — **RAISES** raw `ValueError`.
- Top-level `verify(..., mode=Mode.MOD_11_2)` — silently returns `False`.

**Why High not Critical:** The uncaught `ValueError` does NOT cause
data corruption, code execution, privilege escalation, or information
disclosure. It is a contract violation that makes the public API
non-total over arbitrary input — direct callers who don't wrap in
broad except clauses will see Python-level tracebacks instead of
the documented `ISO7064Error` (a `ValueError` subclass) with the
"lowercase" / "non-numeric" / "non-alphanumeric" substring promised
by AC9. The blast radius is API ergonomics, not security per se.
The CLI path catches `ISO7064Error` specifically (line 73), so an
`X`-in-body input on the CLI exits with a Python traceback and exit
code 1 (not the documented exit 2 with a clean stderr message).

**Why not covered by tests:** The 125-test suite (verified by
`grep -r "def test_" tests/`) has zero cases with `'X'` in the
non-trailing position. Test `test_mod11_2.py:55-58` only exercises the
canonical `('043942089', '043942089X')` round-trip where `'X'` is
the check char. The fuzz harness (`test_fuzz.py`) uses
`string.digits` corpus, never `'X'`. So this regression survived
build + QA.

**Suggested fix (for builder, not part of T1 deliverable):**
Validate the body separately from the trailing check position, OR
have `_Mod11_2._check_character_impl` walk positions 0..len(data)-1
with weights and reject `'X'` in body, OR add an early `ValueError`
catch in `System.compute()` that re-raises as `ISO7064Error`.

#### V002 (Medium) — `_check_character_impl` unguarded

`System.compute` (line 140-147) and `System.check_character` (line
168-175) call `self._check_character_impl(data)` after `_validate_input`
returns, but do NOT wrap that call in a `try/except (ISO7064Error, ValueError)`
like `verify()` does at line 164. V001 is the concrete instance of this
gap; any future algorithmic bug in any of the five subclasses would
similarly leak raw exceptions. Recommend defensive catch on `System.compute`
and `System.check_character` to convert any `ValueError` /
`ArithmeticError` into `ISO7064Error`. Low cost, eliminates the whole
class of bug.

#### V003-V005

Style / informational notes. No remediation required.

### Surfaces audited and clean

- **CLI** (`__main__.py`) — clean. argparse rejects unknown args;
  `ISO7064Error` is caught and prints `error: ...` to stderr, exit 2.
  No shell injection (no `os.system`, no `subprocess`).
- **`_alphabet.py`** — clean. Pure constant strings.
- **Module init (`__init__.py`)** — clean. Re-exports only.
- **`_resolve_system` dispatch** — clean except for V005 (accepts
  bare string; not a security issue).
- **IBAN path (`_Mod97_10`)** — clean. Rotation only triggers when
  `_looks_like_iban` is true (2 uppercase letters + 2 digits prefix);
  lowercase is rejected before rotation. The `'AB12'` 4-char edge
  case was probed and works correctly (`'AB12' -> 'AB72'`).
- **MOD_661_26 ISIN / CUSIP split** — clean. `_is_isin_shape` is
  length-11 + 2 letters + 2 digits + 7 alphanumeric. Other 11-char
  shapes fall through to CUSIP path (which uses the wider alphabet
  including `*@#`).

---

## Verdict

VERDICT: DIRTY

**Rationale:** V001 is a High-severity contract violation directly
against SPEC §6 AC9 and the `ISO7064Error` docstring at
`_systems.py:49-55`. The `MOD_11_2.compute()` and `.check_character()`
public methods raise a raw Python `ValueError` instead of the documented
exception type when input contains `'X'` in the non-trailing position.
Per Invariant 26 adversary-stop-conditions, 1+ High finding → DIRTY.

**Handoff to builder (via orchestrator):**
- V001 is the blocker; remediation is small (3-5 lines in
  `_systems.py:215-220` or wrapper at `_systems.py:140-175`).
- V002 is the related hardening opportunity (catches the whole
  class of bug). Recommend doing both in the same fix commit.
- V003-V005 are advisory; no action required.
- The 125-test suite has a coverage gap on `X`-in-body; the fix
  commit should add ≥1 test per public method (`.compute()` and
  `.check_character()`) covering at least `'X794'` and `'X'`.

Test count after fix should remain ≥ 100 (currently 125, so add
≥ 1-3 tests for V001; net ≥ 126).

---

## Metadata

- `vuln_audit_commit_sha`: <populated after commit>
- `findings_total`: 5
- `findings_by_severity`: {critical: 0, high: 1, medium: 1, low: 1, info: 2}
- `verdict_line`: VERDICT: DIRTY
- `surfaces_covered`: 4
- `worker_session_id`: t_f17f4b78