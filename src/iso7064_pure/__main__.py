"""Command-line entry point for iso7064-pure.

Two subcommands: ``compute`` and ``verify``. Each accepts ``--mode``
(``MOD_11_2``, ``MOD_37_2``, ``MOD_97_10``, ``MOD_661_26``, ``MOD_1271_36``)
plus the data string. ``--version`` and ``--help`` are wired up explicitly
so they don't get swallowed by argparse's required-positional handling.
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from iso7064_pure import (
    ISO7064Error,
    Mode,
    __version__,
    compute,
    verify,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="iso7064-pure",
        description=(
            "ISO/IEC 7064:2021 check character systems — "
            "compute and verify check digits."
        ),
    )
    parser.add_argument(
        "--version", action="version", version=f"iso7064-pure {__version__}"
    )

    sub = parser.add_subparsers(dest="command")

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("data", help="input string")
    common.add_argument(
        "--mode",
        required=True,
        choices=[m.value for m in Mode],
        help="ISO 7064 system",
    )

    sub.add_parser(
        "compute",
        parents=[common],
        help="append the check character(s) and print the full string",
    )
    sub.add_parser(
        "verify",
        parents=[common],
        help="validate and exit 0 if the check character(s) are correct",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    mode = Mode(args.mode)
    try:
        if args.command == "compute":
            print(compute(args.data, mode=mode))
            return 0
        if args.command == "verify":
            return 0 if verify(args.data, mode=mode) else 1
    except ISO7064Error as exc:
        print(f"error: {exc.message}", file=sys.stderr)
        return 2
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())