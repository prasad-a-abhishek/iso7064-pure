"""Minimized reproducer for F002.

This script demonstrates the same MOD_11_2.compute() bug as F001 but with
a longer, fuzzer-discovered input '1234X567' (8 bytes). The fuzzer
discovered this input independently of the manual V001 reproducer
('X794'), proving the bug is reachable across a wider surface of inputs.

F002 vs F001 — both reproducer the same underlying bug. They are split
into two finding entries because each represents a distinct fuzzer-
discovered crash artifact (different SHA-256, different corpus state)
and the fuzzer independently converged on each. Splitting them preserves
the crash history; if MOD_11_2 is fixed, both inputs should stop
triggering crashes and both finding folders can be closed simultaneously.

Run from the worktree root:
    PYTHONPATH=src python3 cycle_138/adversary/findings/F002_*/minimized.py

Expected: exits 0 with a printed ValueError that is NOT an ISO7064Error.
"""
import sys
import traceback

sys.path.insert(0, "src")

import iso7064_pure as iso  # noqa: E402
from iso7064_pure import ISO7064Error  # noqa: E402
from iso7064_pure._systems import MOD_11_2  # noqa: E402

# Fuzzer-discovered input: '1234X567' — 8 bytes with alphabetic 'X' at
# position 4.  The fuzzer found this independently during T3 corpus run
# (see crash-f8f1862b450dd4ee99f2b4f73ecc93e41850d443).  Note: this
# input would be rejected on length grounds alone (MOD_11_2 only takes
# 9-digit bodies for ISBN-10), but the fuzzer's per_system harness
# dispatches mode-based on raw_data[0], so any byte sequence is accepted.
DATA = "1234X567"

print(f"F002: calling MOD_11_2.compute({DATA!r}) ...")
try:
    out = MOD_11_2.compute(DATA)
    print(f"  UNEXPECTED SUCCESS: returned {out!r}")
    sys.exit(2)
except ISO7064Error as exc:
    print(f"  EXPECTED ERROR (ISO7064Error subclass): {exc!r}")
    print("  Spec §6 AC9 contract satisfied.")
    sys.exit(0)
except ValueError as exc:
    print("=" * 60)
    print("RAW ValueError escaped (NOT wrapped in ISO7064Error):")
    print("=" * 60)
    traceback.print_exc()
    print("=" * 60)
    print("BUG CONFIRMED: SPEC §6 AC9 contract violation (fuzzer-discovered).")
    sys.exit(1)
