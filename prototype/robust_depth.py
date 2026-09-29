#!/usr/bin/env python3
"""Exact robust compliance over quantized axis-aligned evidence boxes.

This module is a geometry reference implementation, not a zero-knowledge
backend.  Coordinates are integers and every interval is closed.  The core
routine computes exact maximum overlap depth from lower-corner candidates,
which is polynomial for fixed dimension and avoids enumerating all surviving
source subsets.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations, product
from typing import Iterable, Sequence


ROBUST_VALID = "robust_valid"
ROBUST_INVALID = "robust_invalid"
AMBIGUOUS = "ambiguous"
EVIDENCE_FAILURE = "evidence_failure"


@dataclass(frozen=True)
class BoxND:
    """Inclusive integer box [lo_1, hi_1] x ... x [lo_d, hi_d]."""

    lo: tuple[int, ...]
    hi: tuple[int, ...]

    def __post_init__(self) -> None:
        if len(self.lo) == 0 or len(self.lo) != len(self.hi):
            raise ValueError("lo and hi must have the same positive dimension")
        if any(left > right for left, right in zip(self.lo, self.hi)):
            raise ValueError("box is empty")

    @property
    def dimension(self) -> int:
        return len(self.lo)

    def contains(self, point: Sequence[int]) -> bool:
        return len(point) == self.dimension and all(
            left <= value <= right
            for value, left, right in zip(point, self.lo, self.hi)
        )

    def contains_box(self, other: "BoxND") -> bool:
        _same_dimension(self, other)
        return all(
            left <= other_left and other_right <= right
            for left, right, other_left, other_right in zip(
                self.lo, self.hi, other.lo, other.hi
            )
        )

    def intersection(self, other: "BoxND") -> "BoxND | None":
        _same_dimension(self, other)
        lo = tuple(max(a, b) for a, b in zip(self.lo, other.lo))
        hi = tuple(min(a, b) for a, b in zip(self.hi, other.hi))
        if any(left > right for left, right in zip(lo, hi)):
            return None
        return BoxND(lo, hi)


@dataclass(frozen=True)
class DepthResult:
    depth: int
    witness: tuple[int, ...] | None
    candidate_count: int


@dataclass(frozen=True)
class ComplianceResult:
    decision: str
    threshold: int
    inside_depth: int
    outside_depth: int
    inside_witness: tuple[int, ...] | None
    outside_witness: tuple[int, ...] | None
    evaluated_candidates: int


def _same_dimension(first: BoxND, second: BoxND) -> None:
    if first.dimension != second.dimension:
        raise ValueError("dimension mismatch")


def _validate_boxes(boxes: Sequence[BoxND], domain: BoxND) -> None:
    for box in boxes:
        _same_dimension(box, domain)
        if not domain.contains_box(box):
            raise ValueError("every evidence box must lie within the public domain")


def maximum_depth(boxes: Sequence[BoxND], query: BoxND) -> DepthResult:
    """Return the exact maximum number of boxes covering a point in ``query``.

    For any nonempty common intersection, its lower corner is covered by the
    same boxes.  Hence a maximum is attained at a Cartesian product of lower
    endpoints of the boxes after clipping them to ``query``.
    """

    if not boxes:
        return DepthResult(0, None, 0)
    for box in boxes:
        _same_dimension(box, query)

    clipped = [candidate for box in boxes if (candidate := box.intersection(query))]
    if not clipped:
        return DepthResult(0, None, 0)

    axes = [sorted({box.lo[axis] for box in clipped}) for axis in range(query.dimension)]
    best_depth = 0
    best_point: tuple[int, ...] | None = None
    candidate_count = 0
    for point in product(*axes):
        candidate_count += 1
        depth = sum(box.contains(point) for box in clipped)
        if depth > best_depth:
            best_depth = depth
            best_point = tuple(point)
    return DepthResult(best_depth, best_point, candidate_count)


def outside_slabs(domain: BoxND, policy: BoxND) -> tuple[BoxND, ...]:
    """Cover the complement of ``policy`` in ``domain`` by at most 2d slabs.

    Slabs may overlap at corners, which does not affect their maximum depth.
    Quantized coordinates make the complement exact via ``lo-1`` and ``hi+1``.
    """

    _same_dimension(domain, policy)
    if not domain.contains_box(policy):
        raise ValueError("policy must be contained in the public domain")
    slabs: list[BoxND] = []
    for axis in range(domain.dimension):
        if policy.lo[axis] > domain.lo[axis]:
            lo = list(domain.lo)
            hi = list(domain.hi)
            hi[axis] = policy.lo[axis] - 1
            slabs.append(BoxND(tuple(lo), tuple(hi)))
        if policy.hi[axis] < domain.hi[axis]:
            lo = list(domain.lo)
            hi = list(domain.hi)
            lo[axis] = policy.hi[axis] + 1
            slabs.append(BoxND(tuple(lo), tuple(hi)))
    return tuple(slabs)


def classify_robust_compliance(
    boxes: Sequence[BoxND],
    domain: BoxND,
    policy: BoxND,
    byzantine_budget: int,
    miscoverage_budget: int,
) -> ComplianceResult:
    """Classify the threshold feasible set relative to a task policy.

    The feasible set contains points covered by at least
    ``n - byzantine_budget - miscoverage_budget`` evidence boxes.
    """

    _validate_boxes(boxes, domain)
    _same_dimension(domain, policy)
    if not domain.contains_box(policy):
        raise ValueError("policy must be contained in the public domain")
    n = len(boxes)
    f = byzantine_budget
    r = miscoverage_budget
    if f < 0 or r < 0 or f + r >= n:
        raise ValueError("budgets must be nonnegative and satisfy f + r < n")
    threshold = n - f - r

    inside = maximum_depth(boxes, policy)
    best_outside = DepthResult(0, None, 0)
    outside_candidate_count = 0
    for slab in outside_slabs(domain, policy):
        result = maximum_depth(boxes, slab)
        outside_candidate_count += result.candidate_count
        if result.depth > best_outside.depth:
            best_outside = result

    inside_reachable = inside.depth >= threshold
    outside_reachable = best_outside.depth >= threshold
    if inside_reachable and not outside_reachable:
        decision = ROBUST_VALID
    elif outside_reachable and not inside_reachable:
        decision = ROBUST_INVALID
    elif inside_reachable and outside_reachable:
        decision = AMBIGUOUS
    else:
        decision = EVIDENCE_FAILURE

    return ComplianceResult(
        decision=decision,
        threshold=threshold,
        inside_depth=inside.depth,
        outside_depth=best_outside.depth,
        inside_witness=inside.witness,
        outside_witness=best_outside.witness,
        evaluated_candidates=inside.candidate_count + outside_candidate_count,
    )


def classify_subset_oracle(
    boxes: Sequence[BoxND],
    domain: BoxND,
    policy: BoxND,
    byzantine_budget: int,
    miscoverage_budget: int,
) -> str:
    """Equivalent classifier by enumerating all threshold-sized subsets.

    This is useful as a fast native oracle when ``n-k`` is very small.  Its
    worst-case subset count is combinatorial; the lower-corner algorithm above
    instead has a fault-budget-independent polynomial bound for fixed d.
    """

    _validate_boxes(boxes, domain)
    _same_dimension(domain, policy)
    if not domain.contains_box(policy):
        raise ValueError("policy must be contained in the public domain")
    n = len(boxes)
    f, r = byzantine_budget, miscoverage_budget
    if f < 0 or r < 0 or f + r >= n:
        raise ValueError("budgets must be nonnegative and satisfy f + r < n")
    threshold = n - f - r
    inside_reachable = False
    outside_reachable = False
    for selected in combinations(boxes, threshold):
        common: BoxND | None = selected[0]
        for box in selected[1:]:
            common = common.intersection(box) if common is not None else None
        if common is None:
            continue
        inside_reachable |= common.intersection(policy) is not None
        outside_reachable |= not policy.contains_box(common)
        if inside_reachable and outside_reachable:
            break
    if inside_reachable and not outside_reachable:
        return ROBUST_VALID
    if outside_reachable and not inside_reachable:
        return ROBUST_INVALID
    if inside_reachable and outside_reachable:
        return AMBIGUOUS
    return EVIDENCE_FAILURE


def brute_force_depth(boxes: Sequence[BoxND], query: BoxND) -> DepthResult:
    """Exhaustive oracle for tests on small integer domains."""

    axes: Iterable[range] = (
        range(left, right + 1) for left, right in zip(query.lo, query.hi)
    )
    best_depth = 0
    best_point: tuple[int, ...] | None = None
    count = 0
    for point in product(*axes):
        count += 1
        depth = sum(box.contains(point) for box in boxes)
        if depth > best_depth:
            best_depth = depth
            best_point = tuple(point)
    return DepthResult(best_depth, best_point, count)
