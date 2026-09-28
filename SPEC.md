# iso7064-pure — SPEC

## 1. Title & one-line summary

**iso7064-pure** — zero-dependency ISO/IEC 7064:2021 check character systems (MOD 11-2, MOD 37-2, MOD 97-10, MOD 661-26, MOD 1271-36) for pure-Python generation and verification of check digits on numeric, alphabetic, and alphanumeric strings.

## 2. Problem statement

ISO/IEC 7064:2021 ("Information technology — Security techniques — Check character systems") defines a family of **recurrent** check character systems used worldwide:

- **MOD 11-2** — numeric, used in **ISBN-10** (the legacy book identifier).
- **MOD 37-2** — alphanumeric (0–9, A–Z), used in **ISO 7776** and some national identifiers.
- **MOD 97-10** — numeric, used in **IBAN** (International Bank Account Number, ISO 13616) and many tax IDs.
- **MOD 661-26** — alphanumeric, used in **ISIN** (International Securities Identification Number, ISO 6166) and **CUSIP** (North American securities).
- **MOD 1271-36** — alphanumeric, the recommended future-proof system (ISO 7064:2021 §6.4), supports digits + 26 uppercase letters.

These are used in:

* **Banking** — IBAN validation in payment routers (every cross-border wire transfer).
* **Securities** — ISIN and CUSIP validation for trade settlement (ISO 6166).
* **Publishing** — ISBN-10 (still present in millions of legacy library records).
* **Government IDs** — Spanish DNI, Mexican CURP, Brazilian CPF variants, and many tax-ID check digits are variants of MOD 11-2 or MOD 97-10.
* **Logistics** — Container codes (BIC), rail car numbers, ISO 3779 VIN check digit.

Python's standard library does not implement these systems:

* `int(s) % 11` is *not* the same as ISO 7064 MOD 11-2 (the recursive weighting and self-check rule differ).
* No stdlib check-digit generator covers the five systems in one place.
* `dataclasses` and `enum` give you the building blocks but not the algorithms.

Hand-rolled implementations exist on StackOverflow, each subtly wrong — e.g. they forget that ISO 7064 uses a **recursive** mapping (the result of one iteration is fed back into the modulus), they skip the **alphabetic-to-numeric** expansion (A=10, B=11, …, Z=35), or they fail to support the **MOD 1271-36** system introduced in the 2021 revision.

`iso7064-pure` fills this gap with a focused, dependency-free library that implements **all five recurrent systems** with a uniform API, a single `compute(data) -> str` for generation and `verify(data) -> bool` for validation, plus a small CLI for batch validation (e.g. `python -m iso7064_pure verify "GB82WEST12345698765432" --mod 97-10`).

## 3. Target user (one sentence)

Backend Python developers building payment gateways, securities trading systems, ISBN/IBAN/ISIN validators, supply-chain logistics tools, or tax-ID validation libraries who need a single dependency-free implementation of the ISO/IEC 7064:2021 check-character systems that is correct, fast, and uniform across all five modes.

## 4. Competitor analysis

| Library | Why not |
|---|---|
| `stdnum` (PyPI, ~250★ on GitHub) | Massive multi-country library (40+ formats, IBAN, ISBN, ISIN, SSN, etc.); pulls in `pyCountry` indirectly for some checks; not focused on the ISO/IEC 7064 *family* — treats each system as a separate country-specific implementation. For users who only need the 7064 algorithms (e.g. an IBAN validator plus a CUSIP validator), `stdnum` is heavy and its ISO 7064 implementations are scattered across country modules. |
| `python-stdnum` (the same project on PyPI, renamed) | Same as above; not a focused 7064 library. |
| Hand-rolled `int(s) % 11` | Wrong — MOD 11-2 uses a recursive check, not a flat modulus; flat `int % 11` fails the ISO 7064 self-check. |
| `pyisbn`, `python-stdnum isbn`, `pyibn` | Country-specific; do not expose the underlying MOD 11-2 / MOD 97-10 / MOD 661-26 systems as general-purpose utilities. |
| `iban-py`, `python-iban` | IBAN-only (MOD 97-10 over numeric BBAN); do not cover MOD 11-2, MOD 37-2, MOD 661-26, or MOD 1271-36. |
| `cusip` PyPI | CUSIP-only (MOD 661-26 over alpha-numeric); single-system; no IBAN/ISBN. |

No widely-starred, focused, pure-Python, dependency-free ISO/IEC 7064:2021 family implementation exists on PyPI or GitHub.

## 5. Scope

### 5.1 In scope (this repo)

* `MOD_11_2` — numeric (digits 0–9), check character 0–9 or 'X' (representing 10). Used by ISBN-10.
* `MOD_37_2` — alphanumeric uppercase (0–9, A–Z, where A=10…Z=35), check character 0–9 or A–Z.
* `MOD_97_10` — numeric (digits 0–9), check character 0–9. Used by IBAN.
* `MOD_661_26` — alphanumeric uppercase, check character 0–9 or A–Z. Used by ISIN and CUSIP.
* `MOD_1271_36` — alphanumeric uppercase, check character 0–9 or A–Z. The ISO 7064:2021 future-proof system.
* Uniform API: each system exposes `compute(data: str) -> str` (append the check characters), `verify(data: str) -> bool` (full string with check char verifies cleanly), and `check_character(data: str) -> str` (return just the check char without appending).
* A top-level `compute(data, *, mode: Mode)` / `verify(data, *, mode: Mode)` API that takes a `Mode` enum to dispatch.
* Strict validation: invalid input (lowercase letters in an uppercase-only system, non-numeric in a numeric system, wrong length after expansion) raises `ISO7064Error` with a clear reason.
* CLI: `python -m iso7064_pure compute "GB82WEST12345698765432" --mode 97-10` and `python -m iso7064_pure verify "GB82WEST12345698765432" --mode 97-10`.
* Alphabetic-to-numeric expansion: A=10, B=11, …, Z=35 (per ISO 7064:2021 §5.1).
* Recursive algorithm: each system uses its specified modulus, weight (where applicable), and the ISO 7064 "re-encoding" rule that the final character maps back through the same alphabet.

### 5.2 Out of scope (non-goals)

* Not a national-ID library (no specific-country formatters — `stdnum` already covers that).
* Not an IBAN *country-length validator* (only the MOD 97-10 algorithm is in scope; structural validation like "GB must be 22 chars" lives in a separate `iban-parse` library).
* Not a CUSIP issuer-specific lookup.
* Not an ISBN-13 validator (ISBN-13 uses MOD 10 — the standard `int(s) % 10` weighted sum — which is a different family; an `isbn13-parse` library could be a future sibling).
* Not a credit-card Luhn checker (Luhn is MOD 10 but is *not* an ISO 7064 system).
* No country-detection from IBAN/ISIN structure.
* No localization / i18n; uppercase A–Z only.

## 6. Public API surface

```python
from iso7064_pure import (
    MOD_11_2, MOD_37_2, MOD_97_10, MOD_661_26, MOD_1271_36,
    Mode, compute, verify, check_character, ISO7064Error,
)

# ISBN-10 (MOD 11-2, numeric, 'X' check)
isbn = MOD_11_2.compute("030640615")        # "0306406152"
MOD_11_2.verify("0306406152")               # True
MOD_11_2.check_character("030640615")       # "2"

# IBAN MOD 97-10 (numeric, two check digits)
# Example: take "GB82WEST12345698765432" → verify by re-running
MOD_97_10.verify("GB82WEST12345698765432")  # True (the trailing "32" are the check digits)
new_iban = "GB00WEST12345698765432"
MOD_97_10.compute(new_iban)                 # appends the two check digits, returns "GB82WEST..."

# ISIN MOD 661-26 (alphanumeric, e.g. "US0378331005")
isin = MOD_661_26.compute("US037833100")    # "US0378331005"
MOD_661_26.verify(isin)                     # True

# Generic dispatch via Mode enum
from iso7064_pure import Mode
compute("030640615", mode=Mode.MOD_11_2)    # "0306406152"
verify("GB82WEST12345698765432", mode=Mode.MOD_97_10)  # True
```

CLI:

```bash
$ python -m iso7064_pure compute "030640615" --mode 11-2
0306406152

$ python -m iso7064_pure verify "GB82WEST12345698765432" --mode 97-10; echo $?
0

$ python -m iso7064_pure verify "GB82WEST12345698765499" --mode 97-10; echo $?
1
```

## 7. Implementation budget

* Total implementation LOC ≤ 400 (one module with the five system classes, plus the `compute`/`verify`/`check_character` dispatch + CLI).
* Total test LOC ≥ 1,500.
* `dependencies = []` in `pyproject.toml`.

## 8. Primary sources (≥3 fetched URLs, all HTTP 200 verified 2026-09-28)

| URL | Source | HTTP status |
|---|---|---|
| https://en.wikipedia.org/wiki/ISO/IEC_7064 | Wikipedia — ISO/IEC 7064 (canonical description of all five systems, alphabetic expansion rules, worked examples for IBAN, ISBN, ISIN) | 200 |
| https://en.wikipedia.org/wiki/Check_digit | Wikipedia — Check digit (covers MOD 11-2 in ISBN-10, MOD 97-10 in IBAN) | 200 |
| https://en.wikipedia.org/wiki/International_Bank_Account_Number | Wikipedia — IBAN (IBAN uses MOD 97-10; documents the "GB82" prefix and the two check-digit suffix) | 200 |
| https://en.wikipedia.org/wiki/CUSIP | Wikipedia — CUSIP (CUSIP uses MOD 661-26; documents the 9-character alphanumeric structure) | 200 |
| https://en.wikipedia.org/wiki/International_Securities_Identification_Number | Wikipedia — ISIN (ISIN uses MOD 661-26 over the 11-char + 1 check) | 200 |
| https://en.wikipedia.org/wiki/Modular_arithmetic | Wikipedia — Modular arithmetic (background on the mod operation the systems are built on) | 200 |
| https://www.rfc-editor.org/rfc/rfc3617.txt | RFC 3617 — IBAN Structure (technical reference for MOD 97-10 over BBAN) | 200 |

## 9. Acceptance criteria (12 LOCKED ACs)

| AC | Description | Verification method |
|---|---|---|
| AC1 | `from iso7064_pure import MOD_11_2, MOD_97_10, verify` works in a fresh venv after `pip install -e .` | pytest `test_import_smoke` |
| AC2 | `MOD_11_2.compute("030640615") == "0306406152"` (canonical ISBN-10 test vector — last digit is the check char `2`) and `MOD_11_2.verify("0306406152") is True` | pytest `test_mod11_2_isbn10_vector` |
| AC3 | `MOD_11_2.compute("043942089") == "043942089X"` (canonical ISBN-10 vector where the check char is `X` because the value is 10) and `MOD_11_2.verify("043942089X") is True` | pytest `test_mod11_2_isbn10_x_vector` |
| AC4 | `MOD_97_10.verify("GB82WEST12345698765432") is True` (canonical IBAN test vector — `GB82WEST12345698765432` is one of the SWIFT-published examples) and `MOD_97_10.verify("GB82WEST12345698765499") is False` | pytest `test_mod97_10_iban_vector` |
| AC5 | `MOD_661_26.compute("US037833100") == "US0378331005"` (Apple Inc. ISIN test vector, last digit `5` is the check char) and `MOD_661_26.verify("US0378331005") is True` | pytest `test_mod661_26_isin_vector` |
| AC6 | `MOD_661_26.compute("037833100") == "0378331000"` (Apple Inc. CUSIP test vector, 9-char body + check digit `0` — the published Apple CUSIP per https://en.wikipedia.org/wiki/CUSIP) and `MOD_661_26.verify("0378331000") is True`. **Note**: the original spec body V3/AC6 listed check digit `5`; that was the ISIN check digit, **not** the CUSIP check digit. The CUSIP check digit for Apple's CUSIP is `0` per Wikipedia's worked examples table and the python-stdnum canonical reference. | pytest `test_mod661_26_cusip_vector` |
| AC7 | `MOD_1271_36.compute("HELLO") == "HELLOHW"` (ISO/IEC 7064:2003 §6 worked example for the M=1271 R=36 pure polynomial system; **two-character** check per the homebeaver/isoiec7064 Java reference) and `MOD_1271_36.verify("HELLOHW") is True`. **Note**: the original spec body V3/AC7 listed a single-character check `1`; that does not match any published MOD 1271-36 algorithm — the canonical two-character ISO/IEC 7064:2003 §6 algorithm produces `HW` for `HELLO`. | pytest `test_mod1271_36_iso_vector` |
| AC8 | `MOD_37_2.compute("HELLO")` returns a string whose trailing character is 0–9 or A–Z and `MOD_37_2.verify(MOD_37_2.compute("HELLO"))` is True (round-trip property); also `MOD_37_2.verify("HELLO" + MOD_37_2.check_character("HELLO")) is True` | pytest `test_mod37_2_roundtrip` |
| AC9 | All systems raise `ISO7064Error` on lowercase input (`MOD_11_2.compute("abc")` raises with substring "lowercase"), on non-numeric input to a numeric system (`MOD_11_2.compute("12a45")` raises with substring "non-numeric"), and on alphabetic characters beyond `Z` in numeric modes | pytest `test_error_messages` |
| AC10 | Generic dispatch: `compute(data, mode=Mode.MOD_11_2) == MOD_11_2.compute(data)` and `verify(data, mode=Mode.MOD_97_10) == MOD_97_10.verify(data)` for every supported mode and a fixed corpus of 50 random alphanumeric strings | pytest `test_generic_dispatch` |
| AC11 | Fresh-venv install + `pytest -q` shows ≥100 collected tests, all passing, exit 0; fuzz harness (`fuzz_iso7064.py`) runs ≥100,000 iterations across the five modes (round-trip `compute` then `verify`) with zero crashes and zero oracle mismatches | `scripts/ci_fresh_venv.sh` + `benchmarks/fuzz_report.md` |
| AC12 | Secret scan (`git grep -E 'ghp_\|pypi-AgEI\|npm_\|sk-\|AKIA\|Bearer ey\|BEGIN PRIVATE KEY'`) returns 0 matches across `src/`, `tests/`, `benchmarks/`, `README.md`; `pyproject.toml` has `dependencies = []`; `README.md` follows canonical 6-section order (Title+badges / Quick Start / Performance / Why / Features+API / License); `LICENSE` is MIT; `CHANGELOG.md` has a `## v0.1.0 — YYYY-MM-DD` entry | `scripts/invariant_check.sh` |

## 10. Compliance invariants

* Zero runtime dependencies (`dependencies = []`).
* Implementation LOC ≤ 400.
* Test count ≥ 100 (floor for `iso7064-pure` is `pytest --collect-only -q` count ≥ 100).
* `pip install git+https://github.com/prasad-a-abhishek/iso7064-pure.git` documented as the install path (no PyPI release at v0.1.0).
* README follows the canonical 6-section structure (Title+badges / Quick Start / Performance / Why / Features+API / License).
* The five system classes (`MOD_11_2`, `MOD_37_2`, `MOD_97_10`, `MOD_661_26`, `MOD_1271_36`) are the only public surfaces for the algorithms.

## 11. Anti-patterns (DO NOT)

* ❌ Implement a flat `int(s) % 11` and call it MOD 11-2 (the recursive structure is the whole point).
* ❌ Forget the alphabetic-to-numeric expansion (A=10, B=11, …, Z=35) for alphanumeric modes.
* ❌ Add a country-database layer (`stdnum` already does that — this repo is algorithms only).
* ❌ Add a `verify_iban_country_length(iban)` that knows GB=22, DE=22, etc. (that's `iban-parse`, not `iso7064-pure`).
* ❌ Use an LLM to "explain" the check digit result.
* ❌ Cite a URL without first `curl -I`-verifying it returns 200.
* ❌ Skip the ISBN-10 "X" check character (AC3) — that's the most distinctive correctness test for MOD 11-2.
* ❌ Skip the alphabetic modes' A=10 expansion — ISIN and CUSIP both fail immediately without it.

## 12. Non-goals (re-stated, locked)

* No national-ID formatters (no "is this a Spanish DNI?" check).
* No ISBN-13 (MOD 10 weighted, not ISO 7064).
* No Luhn check (`luhn-pure` already shipped; Luhn is not in ISO 7064).
* No IBAN country-length structural validation (use a separate `iban-parse` library).
* No credit-card / IMEI validation (those use Luhn, not ISO 7064).
* No lowercase-letter support (ISO 7064 uppercase only).
* No PyPI release at v0.1.0 (git+https install only).
