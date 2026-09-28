"""Minimized reproducer for F001.

This script demonstrates the MOD_11_2.compute() bug where an alphabetic
character ('X') appearing in the BODY of input data causes a raw ValueError
to escape instead of being wrapped in ISO7064Error.

SPEC §6 AC9 requires: "All systems raise ISO7064Error on invalid input".

Run from the worktree root:
    PYTHONPATH=src python3 cycle_138/adversary/findings/F001_*/minimized.py

Expected: exits 0 with a printed ValueError that is NOT an ISO7064Error.
This proves the SPEC §6 AC9 contract violation.
"""
import sys
import traceback

sys.path.insert(0, "src")

import iso7064_pure as iso  # noqa: E402
from iso7064_pure import ISO7064Error  # noqa: E402
from iso7064_pure._systems import MOD_11_2  # noqa: E402

# Minimized input: 'X794' — only 4 chars, contains the alphabetic 'X' in
# the body.  This is the smallest input that still triggers the bug; further
# reduction to 1-3 chars (e.g. 'X', 'X7', 'X79') is blocked because MOD_11_2
# requires exactly N input digits and a single check char.
DATA = "X794"

print(f"F001: calling MOD_11_2.compute({DATA!r}) ...")
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
    print("BUG CONFIRMED: SPEC §6 AC9 contract violation.")
    print("MOD_11_2._check_character_impl called int('X') on body digit,")
    print("raising raw ValueError from CPython's int() builtin instead")
    print("of catching and re-raising as ISO7064Error.")
    sys.exit(1)
