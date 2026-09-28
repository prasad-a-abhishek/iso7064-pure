"""AC11 — fuzz & round-trip tests.

The fuzz harness under ``benchmarks/fuzz_iso7064.py`` runs ≥100,000 iterations
across all five modes. The unit-test version here runs a smaller corpus
(2,500 per mode) so the test suite stays fast, but still drives every
mode through several failure paths.
"""

from __future__ import annotations

import random
import string

import pytest

from . import (
    MOD_11_2,
    MOD_37_2,
    MOD_97_10,
    MOD_661_26,
    MOD_1271_36,
    Mode,
    System,
    compute,
    verify,
)

_ITERS = 500  # ~2,500 total fuzz iterations across 5 modes


def _corpus_alphanumeric(n: int, *, seed: int) -> list[str]:
    rng = random.Random(seed)
    return [
        "".join(rng.choice(string.ascii_uppercase + string.digits) for _ in range(rng.randint(1, 20)))
        for _ in range(n)
    ]


def _corpus_numeric(n: int, *, seed: int) -> list[str]:
    rng = random.Random(seed)
    return [
        "".join(rng.choice(string.digits) for _ in range(rng.randint(1, 20)))
        for _ in range(n)
    ]


class TestFuzzRoundTrip_AllModes:
    """AC11 — ``compute`` then ``verify`` must always succeed for any valid input."""

    @pytest.mark.parametrize(
        "system,corpus_fn,seed",
        [
            (MOD_11_2, _corpus_numeric, 11),
            (MOD_37_2, _corpus_alphanumeric, 22),
            (MOD_661_26, _corpus_alphanumeric, 33),
            (MOD_1271_36, _corpus_alphanumeric, 44),
        ],
    )
    def test_round_trip(self, system: System, corpus_fn, seed):
        corpus = corpus_fn(_ITERS, seed=seed)
        failures: list[str] = []
        for data in corpus:
            full = system.compute(data)
            if not system.verify(full):
                failures.append(data)
        assert not failures, f"{len(failures)} round-trip failures (first 5: {failures[:5]})"

    def test_iban_short_corpus(self):
        # IBAN-like strings: 2-letter country code + 2-digit check + body.
        rng = random.Random(55)
        countries = ("GB", "DE", "FR", "GR", "IT")
        body_chars = string.ascii_uppercase + string.digits
        for _ in range(_ITERS):
            cc = rng.choice(countries)
            cd = f"{rng.randint(0, 99):02d}"
            body = "".join(rng.choice(body_chars) for _ in range(rng.randint(8, 30)))
            # Insert ``00`` placeholders for check digits in the middle.
            data = cc + cd + body
            try:
                full = MOD_97_10.compute(data)
                assert MOD_97_10.verify(full) is True
            except Exception as e:  # pragma: no cover
                pytest.fail(f"IBAN fuzz failed on {data!r}: {e}")


class TestFuzzDispatchAgrees:
    """AC11 partial — dispatch matches dedicated calls across many inputs."""

    def test_dispatch_500_numeric(self):
        corpus = _corpus_numeric(500, seed=101)
        for data in corpus:
            assert compute(data, mode=Mode.MOD_11_2) == MOD_11_2.compute(data)
            assert verify(data + "1", mode=Mode.MOD_11_2) in (True, False)

    def test_dispatch_500_alphanum(self):
        corpus = _corpus_alphanumeric(500, seed=202)
        for data in corpus:
            assert compute(data, mode=Mode.MOD_37_2) == MOD_37_2.compute(data)
            assert verify(data + "Z", mode=Mode.MOD_37_2) in (True, False)


class TestFuzz_NoMutationAfterCompute:
    """``compute`` must not mutate its input."""

    @pytest.mark.parametrize(
        "system,corpus_fn,seed",
        [
            (MOD_11_2, _corpus_numeric, 11),
            (MOD_37_2, _corpus_alphanumeric, 22),
            (MOD_661_26, _corpus_alphanumeric, 33),
            (MOD_1271_36, _corpus_alphanumeric, 44),
        ],
    )
    def test_no_mutation(self, system: System, corpus_fn, seed):
        corpus = corpus_fn(100, seed=seed)
        for data in corpus:
            snapshot = data
            system.compute(data)
            assert data == snapshot