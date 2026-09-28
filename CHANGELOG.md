# Changelog

## v0.1.1 — 2026-09-28

* **MOD_11_2: X-in-body now raises `ISO7064Error` (was: raw `ValueError`).**
  Per ISO/IEC 7064:2021 §6, the letter `X` (value 10) may appear in a MOD 11-2
  string only as the *trailing check character* — never inside the body.
  Previously `MOD_11_2.compute("X794")` and `MOD_11_2.check_character("X794")`
  raised a raw `ValueError: invalid literal for int() with base 10: 'X'`,
  violating SPEC §6 AC9 (which requires `ISO7064Error` on non-numeric input).
  Now both paths raise `ISO7064Error` with a diagnostic message naming the
  offending position. `MOD_11_2.verify("X794")` continues to return `False`
  (canonical contract: invalid → not valid). The CLI surface also benefits:
  `python -m iso7064_pure compute "X794" --mode MOD_11_2` now exits with
  code 2 and a clean stderr message (no Python traceback).
* **Fixes F-001 + F-002** from cycle_138 @repo-adversary FUZZING_REPORT
  (commit 495adc4, see `cycle_138/adversary/fuzz/FUZZING_REPORT.md`).
* Added 4 regression tests in `tests/test_mod11_2.py::TestMod11_2_XInBody`
  covering `compute`, `check_character`, `verify`, and top-level dispatch
  paths. Test count: 210 → 214 (214/214 pass).

## v0.1.0 — 2026-09-28

* Initial release.
* Implements all five ISO/IEC 7064:2021 recurrent check character systems:
  * `MOD_11_2` (numeric, ISBN-10) — includes `X` check character support.
  * `MOD_37_2` (alphanumeric).
  * `MOD_97_10` (numeric, IBAN).
  * `MOD_661_26` (alphanumeric, ISIN, CUSIP).
  * `MOD_1271_36` (alphanumeric, ISO 7064:2021 future-proof system).
* Uniform API: each system exposes `compute`, `verify`, `check_character`.
* Top-level dispatch API: `compute(data, mode=Mode.X)` / `verify(data, mode=Mode.X)`.
* CLI: `python -m iso7064_pure compute|verify|check --mode 11-2|37-2|97-10|661-26|1271-36`.
* Zero runtime dependencies (stdlib only).
* ≥100 pytest tests passing in a fresh venv.
