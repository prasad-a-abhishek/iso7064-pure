# fuzz_report.md

Fuzz harness for `iso7064-pure` — 100,000 iterations per system.

## Summary

- Total iters: 1,000,000
- Total crashes: 0
- Total oracle mismatches: 0
- Total elapsed: 6.14s

## Per-system results

| System | Iters | Elapsed (s) | Rate (ops/s) | Crashes | Oracle mismatches |
|---|---|---|---|---|---|
| MOD_11_2 | 100,000 | 0.296 | 337,367 | 0 | 0 |
| MOD_37_2 | 100,000 | 0.386 | 259,374 | 0 | 0 |
| MOD_661_26 | 100,000 | 0.898 | 111,400 | 0 | 0 |
| MOD_1271_36 | 100,000 | 0.427 | 234,381 | 0 | 0 |
| MOD_97_10 (IBAN-shaped) | 100,000 | 0.496 | 201,774 | 0 | 0 |
| dispatch | 500,000 | 3.642 | 137,270 | 0 | 0 |

## Verdict

VERDICT: PASS — 0 crashes, 0 oracle mismatches.
