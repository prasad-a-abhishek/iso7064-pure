"""Tests for the CLI (``python -m iso7064_pure``)."""

from __future__ import annotations

import subprocess
import sys

from . import __version__, MOD_11_2, MOD_97_10


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "iso7064_pure", *args],
        capture_output=True,
        text=True,
        check=False,
        env={"PYTHONPATH": "src", "PATH": "/usr/bin:/usr/local/bin"},
    )


class TestCLIVersion:
    def test_version_flag(self):
        result = _run(["--version"])
        assert result.returncode == 0
        assert __version__ in result.stdout


class TestCLICompute:
    def test_mod_11_2_compute(self):
        result = _run(["compute", "030640615", "--mode", "MOD_11_2"])
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "0306406152"

    def test_mod_97_10_iban_round_trip(self):
        result = _run(
            ["compute", "GB00WEST12345698765432", "--mode", "MOD_97_10"]
        )
        assert result.returncode == 0, result.stderr
        body = result.stdout.strip()
        # IBAN: check digits REPLACE positions 2-3 of the placeholder;
        # the canonical IBAN is returned in-place.
        assert body == "GB82WEST12345698765432"


class TestCLIVerify:
    def test_verify_valid(self):
        result = _run(["verify", "GB82WEST12345698765432", "--mode", "MOD_97_10"])
        assert result.returncode == 0

    def test_verify_invalid(self):
        result = _run(["verify", "GB82WEST12345698765499", "--mode", "MOD_97_10"])
        assert result.returncode == 1

    def test_verify_valid_isbn10(self):
        result = _run(["verify", "0306406152", "--mode", "MOD_11_2"])
        assert result.returncode == 0

    def test_verify_invalid_isbn10(self):
        result = _run(["verify", "0306406151", "--mode", "MOD_11_2"])
        assert result.returncode == 1


class TestCLIErrors:
    def test_lowercase_input_exits_2(self):
        result = _run(["compute", "abc", "--mode", "MOD_11_2"])
        assert result.returncode == 2
        assert "lowercase" in result.stderr


class TestCLIHelp:
    def test_no_args_shows_help(self):
        result = _run([])
        assert result.returncode == 0
        assert "usage" in result.stdout.lower() or "iso7064" in result.stdout.lower()

    def test_help_flag(self):
        result = _run(["--help"])
        assert result.returncode == 0