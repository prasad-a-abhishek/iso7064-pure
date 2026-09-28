"""AC10 — generic dispatch via the ``Mode`` enum.

Each system must dispatch correctly to its dedicated singleton, both for
``compute`` and ``verify``, across a fixed corpus of random alphanumeric
strings.
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

_SYSTEMS: list[tuple[Mode, System]] = [
    (Mode.MOD_11_2, MOD_11_2),
    (Mode.MOD_37_2, MOD_37_2),
    (Mode.MOD_97_10, MOD_97_10),
    (Mode.MOD_661_26, MOD_661_26),
    (Mode.MOD_1271_36, MOD_1271_36),
]


def _make_corpus(n: int, *, alphabet: str = string.ascii_uppercase + string.digits, seed: int = 1337) -> list[str]:
    rng = random.Random(seed)
    return ["".join(rng.choice(alphabet) for _ in range(rng.randint(3, 30))) for _ in range(n)]


class TestDispatchConsistency:
    """AC10 — compute(data, mode=M) == System(M).compute(data)."""

    @pytest.mark.parametrize("mode,system", _SYSTEMS)
    def test_compute_dispatch(self, mode, system):
        corpus = _make_corpus(20, alphabet=string.digits if mode in (Mode.MOD_11_2, Mode.MOD_97_10) else string.ascii_uppercase + string.digits)
        for data in corpus:
            assert compute(data, mode=mode) == system.compute(data)

    @pytest.mark.parametrize("mode,system", _SYSTEMS)
    def test_verify_dispatch(self, mode, system):
        corpus = _make_corpus(20, alphabet=string.digits if mode in (Mode.MOD_11_2, Mode.MOD_97_10) else string.ascii_uppercase + string.digits)
        for data in corpus:
            # Verify across both the dispatch path and the dedicated method.
            full = system.compute(data)
            assert verify(full, mode=mode) == system.verify(full)

    @pytest.mark.parametrize("mode,system", _SYSTEMS)
    def test_50_string_dispatch_contract(self, mode, system):
        # Larger corpus mandated by AC10.
        corpus = _make_corpus(50, alphabet=string.digits if mode in (Mode.MOD_11_2, Mode.MOD_97_10) else string.ascii_uppercase + string.digits, seed=99)
        for data in corpus:
            assert compute(data, mode=mode) == system.compute(data)
            assert verify(system.compute(data), mode=mode) is True


class TestModeEnumStringHandling:
    """AC10 partial — ``Mode`` enum members stringify."""

    @pytest.mark.parametrize(
        "name,expected",
        [
            ("MOD_11_2", "MOD_11_2"),
            ("MOD_37_2", "MOD_37_2"),
            ("MOD_97_10", "MOD_97_10"),
            ("MOD_661_26", "MOD_661_26"),
            ("MOD_1271_36", "MOD_1271_36"),
        ],
    )
    def test_mode_value(self, name, expected):
        m = Mode[name]
        assert m.value == expected

    def test_mode_iteration(self):
        # Iteration gives all five systems exactly once.
        seen = set()
        for m in Mode:
            seen.add(m.value)
        assert seen == {
            "MOD_11_2",
            "MOD_37_2",
            "MOD_97_10",
            "MOD_661_26",
            "MOD_1271_36",
        }


class TestDispatch_InvalidInput:
    """AC10 partial — invalid input through dispatch surfaces errors."""

    def test_compute_lowercase_via_dispatch(self):
        with pytest.raises(Exception) as exc:
            compute("hello", mode=Mode.MOD_37_2)
        assert "lowercase" in str(exc.value)

    def test_verify_returns_bool_for_invalid(self):
        # Dispatch should mirror the underlying system.
        assert verify("garbage!@#", mode=Mode.MOD_37_2) is False
        assert verify("garbage!@#", mode=Mode.MOD_661_26) is False