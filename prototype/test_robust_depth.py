#!/usr/bin/env python3

from __future__ import annotations

import random
import unittest

from robust_depth import (
    AMBIGUOUS,
    EVIDENCE_FAILURE,
    ROBUST_INVALID,
    ROBUST_VALID,
    BoxND,
    brute_force_depth,
    classify_robust_compliance,
    classify_subset_oracle,
    maximum_depth,
    outside_slabs,
)


class RobustDepthTests(unittest.TestCase):
    def test_four_decisions(self) -> None:
        domain = BoxND((0, 0), (9, 9))
        policy = BoxND((3, 3), (6, 6))

        valid = [BoxND((3, 3), (5, 5)) for _ in range(4)] + [BoxND((0, 0), (9, 9))]
        self.assertEqual(
            classify_robust_compliance(valid, domain, policy, 1, 0).decision,
            ROBUST_VALID,
        )

        invalid = [BoxND((0, 0), (2, 2)) for _ in range(4)] + [BoxND((0, 0), (9, 9))]
        self.assertEqual(
            classify_robust_compliance(invalid, domain, policy, 1, 0).decision,
            ROBUST_INVALID,
        )

        ambiguous = [BoxND((2, 2), (4, 4)) for _ in range(4)] + [BoxND((0, 0), (9, 9))]
        self.assertEqual(
            classify_robust_compliance(ambiguous, domain, policy, 1, 0).decision,
            AMBIGUOUS,
        )

        failure = [
            BoxND((0, 0), (1, 1)),
            BoxND((2, 2), (3, 3)),
            BoxND((4, 4), (5, 5)),
            BoxND((6, 6), (7, 7)),
            BoxND((8, 8), (9, 9)),
        ]
        self.assertEqual(
            classify_robust_compliance(failure, domain, policy, 1, 0).decision,
            EVIDENCE_FAILURE,
        )

    def test_outside_slabs_cover_exact_integer_complement(self) -> None:
        domain = BoxND((0, 0, 0), (5, 5, 5))
        policy = BoxND((1, 2, 1), (4, 3, 4))
        slabs = outside_slabs(domain, policy)
        for x in range(6):
            for y in range(6):
                for z in range(6):
                    point = (x, y, z)
                    self.assertEqual(
                        any(slab.contains(point) for slab in slabs),
                        not policy.contains(point),
                    )

    def test_candidate_algorithm_matches_exhaustive_oracle(self) -> None:
        rng = random.Random(20260904)
        for dimension in (1, 2, 3):
            domain = BoxND((0,) * dimension, (7,) * dimension)
            for _ in range(400):
                boxes = []
                for _ in range(rng.randint(1, 8)):
                    lo = tuple(rng.randint(0, 7) for _ in range(dimension))
                    hi = tuple(rng.randint(left, 7) for left in lo)
                    boxes.append(BoxND(lo, hi))
                qlo = tuple(rng.randint(0, 7) for _ in range(dimension))
                qhi = tuple(rng.randint(left, 7) for left in qlo)
                query = BoxND(qlo, qhi)
                exact = brute_force_depth(boxes, query)
                candidate = maximum_depth(boxes, query)
                self.assertEqual(candidate.depth, exact.depth)
                if candidate.witness is not None:
                    self.assertEqual(
                        sum(box.contains(candidate.witness) for box in boxes),
                        candidate.depth,
                    )

    def test_subset_and_depth_classifiers_are_equivalent(self) -> None:
        rng = random.Random(19090)
        for dimension in (1, 2, 3):
            domain = BoxND((0,) * dimension, (9,) * dimension)
            policy = BoxND((3,) * dimension, (6,) * dimension)
            for _ in range(400):
                boxes = []
                for _ in range(5):
                    lo = tuple(rng.randint(0, 9) for _ in range(dimension))
                    hi = tuple(rng.randint(left, 9) for left in lo)
                    boxes.append(BoxND(lo, hi))
                depth = classify_robust_compliance(boxes, domain, policy, 1, 0)
                subset = classify_subset_oracle(boxes, domain, policy, 1, 0)
                self.assertEqual(depth.decision, subset)

    def test_threshold_soundness_under_declared_fault_budgets(self) -> None:
        rng = random.Random(2403)
        domain = BoxND((0, 0, 0), (7, 7, 7))
        policy = BoxND((2, 2, 2), (5, 5, 5))
        n, f, r = 7, 1, 1
        for _ in range(1000):
            truth = tuple(rng.randint(0, 7) for _ in range(3))
            honest = []
            for _ in range(n - f - r):
                lo = tuple(rng.randint(0, value) for value in truth)
                hi = tuple(rng.randint(value, 7) for value in truth)
                honest.append(BoxND(lo, hi))
            faulty = []
            for _ in range(f + r):
                lo = tuple(rng.randint(0, 7) for _ in range(3))
                hi = tuple(rng.randint(value, 7) for value in lo)
                faulty.append(BoxND(lo, hi))
            result = classify_robust_compliance(honest + faulty, domain, policy, f, r)
            if result.decision == ROBUST_VALID:
                self.assertTrue(policy.contains(truth))
            if result.decision == ROBUST_INVALID:
                self.assertFalse(policy.contains(truth))

    def test_rejects_invalid_budgets_and_unbounded_inputs(self) -> None:
        domain = BoxND((0, 0), (4, 4))
        policy = BoxND((1, 1), (3, 3))
        with self.assertRaises(ValueError):
            classify_robust_compliance([domain], domain, policy, 1, 0)
        with self.assertRaises(ValueError):
            classify_robust_compliance(
                [BoxND((-1, 0), (2, 2))], domain, policy, 0, 0
            )


if __name__ == "__main__":
    unittest.main()
