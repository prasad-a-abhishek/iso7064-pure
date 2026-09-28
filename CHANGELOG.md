# Changelog

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
