"""The CPython workload matches the shared reference values and validates its inputs."""

from __future__ import annotations

import random

import pytest

from runtime_internals_lab.spec import Spec
from runtime_internals_lab.workload import MAX_OPS, MAX_WINDOW, Vec, VectorChurn
from runtime_internals_lab.xorshift import XorShift32


def test_xorshift32_matches_the_shared_reference_sequences(spec: Spec) -> None:
    for seed, first in spec.xorshift32:
        rng = XorShift32(seed)
        assert tuple(rng.next() for _ in first) == first


@pytest.mark.parametrize("seed", [0, -1, 2**32])
def test_xorshift32_rejects_seeds_outside_the_32_bit_range(seed: int) -> None:
    with pytest.raises(ValueError, match="seed"):
        XorShift32(seed)


def test_every_shared_checksum_matches(spec: Spec) -> None:
    for c in spec.checks:
        assert VectorChurn(c.window).run(c.ops, c.seed) == c.checksum, c


def test_the_ring_is_emptied_at_the_start_of_every_round() -> None:
    churn = VectorChurn(64)
    first = churn.run(1_000, 7)
    churn.run(500, 99)
    assert churn.run(1_000, 7) == first


def test_retained_objects_change_the_checksum_only_once_the_ring_wraps() -> None:
    assert VectorChurn(100).run(100, 5) == VectorChurn(0).run(100, 5)
    assert VectorChurn(100).run(101, 5) != VectorChurn(0).run(101, 5)


def test_checksums_stay_unsigned_32_bit_for_random_inputs() -> None:
    rnd = random.Random(1)
    for _ in range(50):
        value = VectorChurn(rnd.randrange(50)).run(1 + rnd.randrange(5_000), 1 + rnd.randrange(2**32 - 1))
        assert 0 <= value < 2**32


def test_out_of_range_arguments_are_rejected() -> None:
    for window in (-1, MAX_WINDOW + 1):
        with pytest.raises(ValueError, match="window"):
            VectorChurn(window)
    churn = VectorChurn(0)
    for ops in (0, MAX_OPS + 1):
        with pytest.raises(ValueError, match="ops"):
            churn.run(ops, 1)
    with pytest.raises(ValueError, match="seed"):
        churn.run(10, 0)


def test_vec_operations_return_new_objects() -> None:
    a = Vec(1, 2)
    b = a.add(Vec(3, 4))
    c = b.scale(3)
    assert (b.x, b.y, c.x, c.y, a.x, a.y) == (4, 6, 12, 18, 1, 2)
    assert c is not b
    with pytest.raises(AttributeError):
        a.z = 1  # type: ignore[attr-defined]
