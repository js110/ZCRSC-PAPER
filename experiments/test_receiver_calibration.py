import unittest
from run_receiver_calibration import (ecef, horizontal_residual, unique_insert,
                                     radius_order_statistic, chronological_split)


class CalibrationTests(unittest.TestCase):
    def test_reference_axes(self):
        self.assertEqual(ecef(0, 0, 0), (6378137., 0., 0.))
        self.assertEqual(horizontal_residual((22, 114, 5), (22, 114, 5)), (0., 0.))
        e, n = horizontal_residual((0, .00001, 0), (0, 0, 0))
        self.assertAlmostEqual(e, 1.1131949079, places=8)
        self.assertEqual(n, 0)
        e, n = horizontal_residual((.00001, 0, 0), (0, 0, 0))
        self.assertEqual(e, 0)
        self.assertAlmostEqual(n, 1.1057427582, places=8)

    def test_duplicate_and_nonfinite_rejected(self):
        data = {}
        unique_insert(data, 1, [2])
        with self.assertRaises(ValueError):
            unique_insert(data, 1, [3])
        with self.assertRaises(ValueError):
            unique_insert(data, 2, [float('nan')])

    def test_rank_and_split(self):
        self.assertEqual(radius_order_statistic(list(range(78))), (75, 76))
        with self.assertRaises(ValueError):
            radius_order_statistic([1, 2])
        a, gap, b = chronological_split(list(range(157)))
        self.assertEqual((len(a), len(gap), len(b)), (78, 10, 69))
        self.assertLess(a[-1], gap[0])
        self.assertLess(gap[-1], b[0])
        changed = list(range(157))[:78]+[999]*79
        a2, _, _ = chronological_split(changed)
        self.assertEqual(radius_order_statistic(a), radius_order_statistic(a2))


if __name__ == '__main__':
    unittest.main()
