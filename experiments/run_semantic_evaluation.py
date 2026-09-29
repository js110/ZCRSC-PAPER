#!/usr/bin/env python3
"""Seed-level evaluation of four-valued robust spacetime compliance.

The experiment uses a quantized 3-D (x, y, t) domain, calibrated and
misspecified evidence boxes, and adaptive Byzantine boxes.  One seed is the
independent experimental unit; events within a seed are repeated observations.
No cryptographic timings are simulated here--those come from the gnark
benchmark in the sibling prototype directory.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "prototype"))

from robust_depth import (  # noqa: E402
    AMBIGUOUS,
    EVIDENCE_FAILURE,
    ROBUST_INVALID,
    ROBUST_VALID,
    BoxND,
    classify_subset_oracle,
)


METHODS = ("median_point", "majority_center", "fixed_margin", "all_intersection", "robust_depth")
DECISIONS = (ROBUST_VALID, ROBUST_INVALID, AMBIGUOUS, EVIDENCE_FAILURE)


@dataclass(frozen=True)
class Condition:
    calibration: str
    radius: int
    actual_byzantine: int

    @property
    def key(self) -> str:
        return f"{self.calibration}__radius_{self.radius}__byz_{self.actual_byzantine}"


def _boundary_weighted_point(
    rng: np.random.Generator, domain_hi: int, policy: BoxND, band: int
) -> tuple[int, ...]:
    if rng.random() >= 0.75:
        return tuple(int(v) for v in rng.integers(0, domain_hi + 1, size=3))
    axis = int(rng.integers(0, 3))
    face = policy.lo[axis] if rng.random() < 0.5 else policy.hi[axis]
    point = [int(v) for v in rng.integers(0, domain_hi + 1, size=3)]
    point[axis] = int(np.clip(face + rng.integers(-band, band + 1), 0, domain_hi))
    return tuple(point)


def _honest_error(
    rng: np.random.Generator,
    radius: int,
    calibration: str,
    shared_direction: np.ndarray,
) -> np.ndarray:
    if calibration == "calibrated_independent":
        return rng.integers(-radius, radius + 1, size=3)
    if calibration == "calibrated_correlated":
        error = np.rint((0.75 * shared_direction + rng.uniform(-0.20, 0.20, 3)) * radius)
        return np.clip(error, -radius, radius).astype(int)
    if calibration == "undercovered_correlated":
        return np.rint((1.35 * shared_direction + rng.uniform(-0.15, 0.15, 3)) * radius).astype(int)
    raise ValueError(calibration)


def _box_around(center: Sequence[int], radius: int, domain_hi: int) -> BoxND:
    return BoxND(
        tuple(max(0, int(v) - radius) for v in center),
        tuple(min(domain_hi, int(v) + radius) for v in center),
    )


def _adversarial_box(truth: tuple[int, ...], policy: BoxND, domain_hi: int) -> BoxND:
    if not policy.contains(truth):
        return policy
    choices: list[tuple[int, int, str]] = []
    for axis in range(3):
        if policy.lo[axis] > 0:
            choices.append((truth[axis] - policy.lo[axis], axis, "low"))
        if policy.hi[axis] < domain_hi:
            choices.append((policy.hi[axis] - truth[axis], axis, "high"))
    _, axis, side = min(choices)
    lo, hi = [0, 0, 0], [domain_hi, domain_hi, domain_hi]
    if side == "low":
        hi[axis] = policy.lo[axis] - 1
    else:
        lo[axis] = policy.hi[axis] + 1
    return BoxND(tuple(lo), tuple(hi))


def generate_event(
    rng: np.random.Generator,
    condition: Condition,
    n: int,
    domain: BoxND,
    policy: BoxND,
) -> tuple[tuple[int, ...], list[BoxND], int]:
    truth = _boundary_weighted_point(rng, domain.hi[0], policy, condition.radius + 1)
    shared = rng.uniform(-1.0, 1.0, size=3)
    boxes: list[BoxND] = []
    honest_misses = 0
    for _ in range(n - condition.actual_byzantine):
        radius = int(rng.integers(max(1, condition.radius // 2), condition.radius + 1))
        error = _honest_error(rng, radius, condition.calibration, shared)
        observed = np.clip(np.asarray(truth) + error, 0, domain.hi[0]).astype(int)
        honest_box = _box_around(observed, radius, domain.hi[0])
        boxes.append(honest_box)
        honest_misses += int(not honest_box.contains(truth))
    boxes.extend(
        _adversarial_box(truth, policy, domain.hi[0])
        for _ in range(condition.actual_byzantine)
    )
    rng.shuffle(boxes)
    return truth, boxes, honest_misses


def _center(box: BoxND) -> tuple[float, ...]:
    return tuple((lo + hi) / 2 for lo, hi in zip(box.lo, box.hi))


def median_point(boxes: Sequence[BoxND], policy: BoxND, _: int) -> str:
    centers = np.asarray([_center(box) for box in boxes])
    return ROBUST_VALID if policy.contains(tuple(np.median(centers, axis=0))) else ROBUST_INVALID


def majority_center(boxes: Sequence[BoxND], policy: BoxND, _: int) -> str:
    votes = sum(policy.contains(_center(box)) for box in boxes)
    return ROBUST_VALID if votes > len(boxes) // 2 else ROBUST_INVALID


def fixed_margin(boxes: Sequence[BoxND], policy: BoxND, radius: int) -> str:
    centers = np.asarray([_center(box) for box in boxes])
    center = np.median(centers, axis=0)
    candidate = BoxND(
        tuple(math.floor(v - radius) for v in center),
        tuple(math.ceil(v + radius) for v in center),
    )
    if policy.contains_box(candidate):
        return ROBUST_VALID
    if candidate.intersection(policy) is None:
        return ROBUST_INVALID
    return AMBIGUOUS


def all_intersection(boxes: Sequence[BoxND], policy: BoxND, _: int) -> str:
    common: BoxND | None = boxes[0]
    for box in boxes[1:]:
        common = common.intersection(box) if common is not None else None
    if common is None:
        return EVIDENCE_FAILURE
    if policy.contains_box(common):
        return ROBUST_VALID
    if common.intersection(policy) is None:
        return ROBUST_INVALID
    return AMBIGUOUS


def _new_counts() -> dict[str, int]:
    return {
        "inside": 0,
        "outside": 0,
        "false_accept": 0,
        "false_reject": 0,
        "correct_decisive": 0,
        **{decision: 0 for decision in DECISIONS},
    }


def _update(counts: dict[str, int], decision: str, truth_inside: bool) -> None:
    counts["inside" if truth_inside else "outside"] += 1
    counts[decision] += 1
    counts["false_accept"] += int(decision == ROBUST_VALID and not truth_inside)
    counts["false_reject"] += int(decision == ROBUST_INVALID and truth_inside)
    counts["correct_decisive"] += int(
        (decision == ROBUST_VALID and truth_inside)
        or (decision == ROBUST_INVALID and not truth_inside)
    )


def _rates(counts: dict[str, int]) -> dict[str, float]:
    total = counts["inside"] + counts["outside"]
    decisive = counts[ROBUST_VALID] + counts[ROBUST_INVALID]
    return {
        "false_accept_rate": counts["false_accept"] / counts["outside"] if counts["outside"] else None,
        "false_reject_rate": counts["false_reject"] / counts["inside"] if counts["inside"] else None,
        "ambiguous_rate": counts[AMBIGUOUS] / total,
        "evidence_failure_rate": counts[EVIDENCE_FAILURE] / total,
        "decisive_coverage": decisive / total,
        "decisive_accuracy": counts["correct_decisive"] / decisive if decisive else None,
    }


def _mean_ci(values: Iterable[float]) -> dict[str, float]:
    array = np.asarray([v for v in values if v is not None], dtype=float)
    if not len(array):
        return {"mean": None, "ci95_low": None, "ci95_high": None, "defined_seeds": 0}
    mean = float(np.mean(array))
    half = float(1.96 * np.std(array, ddof=1) / math.sqrt(len(array))) if len(array)>1 else 0.0
    return {"mean": mean, "ci95_low": mean - half, "ci95_high": mean + half, "defined_seeds": len(array)}


def run(args: argparse.Namespace) -> dict[str, object]:
    domain = BoxND((0, 0, 0), (63, 63, 63))
    policy = BoxND((18, 18, 18), (45, 45, 45))
    conditions = [
        Condition(calibration, radius, byz)
        for calibration in (
            "calibrated_independent",
            "calibrated_correlated",
            "undercovered_correlated",
        )
        for radius in (2, 4, 6)
        for byz in (0, 1, 2)
    ]
    functions: dict[str, Callable[[Sequence[BoxND], BoxND, int], str]] = {
        "median_point": median_point,
        "majority_center": majority_center,
        "fixed_margin": fixed_margin,
        "all_intersection": all_intersection,
    }
    seed_results: dict[str, dict[str, list[dict[str, float]]]] = {
        condition.key: {method: [] for method in METHODS} for condition in conditions
    }
    invariant_violations = 0
    assumption_counts = {
        condition.key: {
            "events": 0,
            "m_le_r": 0,
            "m_gt_r": 0,
            "robust_error_m_le_r": 0,
            "robust_error_m_gt_r": 0,
            "miss_histogram": {},
        }
        for condition in conditions
    }
    seed_counts = {condition.key: {method: [] for method in METHODS} for condition in conditions}
    for seed in range(args.seeds):
        rng = np.random.default_rng(args.seed_base + seed)
        for condition in conditions:
            counts = {method: _new_counts() for method in METHODS}
            for _ in range(args.events_per_seed):
                truth, boxes, honest_misses = generate_event(rng, condition, args.sources, domain, policy)
                truth_inside = policy.contains(truth)
                for method, function in functions.items():
                    _update(counts[method], function(boxes, policy, condition.radius), truth_inside)
                robust = classify_subset_oracle(
                    boxes, domain, policy, args.assumed_byzantine, args.miscoverage_budget
                )
                _update(counts["robust_depth"], robust, truth_inside)
                ac = assumption_counts[condition.key]
                ac["events"] += 1
                hist_key = str(honest_misses)
                ac["miss_histogram"][hist_key] = ac["miss_histogram"].get(hist_key, 0) + 1
                robust_error = (
                    (robust == ROBUST_VALID and not truth_inside)
                    or (robust == ROBUST_INVALID and truth_inside)
                )
                if honest_misses <= args.miscoverage_budget:
                    ac["m_le_r"] += 1
                    ac["robust_error_m_le_r"] += int(robust_error)
                else:
                    ac["m_gt_r"] += 1
                    ac["robust_error_m_gt_r"] += int(robust_error)
                assumptions_hold = (
                    condition.actual_byzantine <= args.assumed_byzantine
                    and condition.calibration.startswith("calibrated_")
                )
                if assumptions_hold and (
                    (robust == ROBUST_VALID and not truth_inside)
                    or (robust == ROBUST_INVALID and truth_inside)
                ):
                    invariant_violations += 1
            for method in METHODS:
                seed_counts[condition.key][method].append(counts[method])
                seed_results[condition.key][method].append(_rates(counts[method]))

    aggregate: dict[str, dict[str, dict[str, dict[str, float]]]] = {}
    for condition in conditions:
        aggregate[condition.key] = {}
        for method in METHODS:
            metrics = seed_results[condition.key][method]
            aggregate[condition.key][method] = {
                metric: _mean_ci(result[metric] for result in metrics)
                for metric in metrics[0]
            }
    return {
        "design": {
            "sources": args.sources,
            "assumed_byzantine": args.assumed_byzantine,
            "miscoverage_budget": args.miscoverage_budget,
            "threshold": args.sources - args.assumed_byzantine - args.miscoverage_budget,
            "seeds": args.seeds,
            "events_per_seed_per_condition": args.events_per_seed,
            "seed_base": args.seed_base,
            "domain": asdict(domain),
            "policy": asdict(policy),
            "independent_unit": "simulation seed",
            "interval": "normal 95% CI over seed-level rates",
            "semantic_oracle": "threshold-subset enumeration; property-tested equivalent to lower-corner maximum depth",
            "conditions": [asdict(condition) | {"key": condition.key} for condition in conditions],
        },
        "invariant_violations_under_stated_assumptions": invariant_violations,
        "assumption_diagnostics": {
            key: {
                **value,
                "p_m_le_r": value["m_le_r"] / value["events"] if value["events"] else None,
                "p_m_gt_r": value["m_gt_r"] / value["events"] if value["events"] else None,
                "robust_error_rate_m_le_r": value["robust_error_m_le_r"] / value["m_le_r"] if value["m_le_r"] else None,
                "robust_error_rate_m_gt_r": value["robust_error_m_gt_r"] / value["m_gt_r"] if value["m_gt_r"] else None,
            }
            for key, value in assumption_counts.items()
        },
        "aggregate": aggregate,
        "seed_results": seed_results,
        "seed_counts": seed_counts,
    }


def plot_results(results: dict[str, object], output_dir: Path) -> None:
    aggregate = results["aggregate"]
    focus = "calibrated_correlated__radius_4__byz_1"
    labels = ["Median\npoint", "Majority\ncenter", "Fixed\nmargin", "All-source\nintersection", "Robust\ndepth"]
    metrics = ("false_accept_rate", "false_reject_rate", "ambiguous_rate", "evidence_failure_rate")
    colors = ("#C44E52", "#DD8452", "#4C72B0", "#8172B2")
    fig, ax = plt.subplots(figsize=(7.16, 3.25))
    x = np.arange(len(METHODS))
    width = 0.19
    for offset, (metric, color) in enumerate(zip(metrics, colors)):
        values = [aggregate[focus][method][metric]["mean"] * 100 for method in METHODS]
        ax.bar(x + (offset - 1.5) * width, values, width, label=metric.replace("_rate", "").replace("_", " "), color=color)
    ax.set_xticks(x, labels)
    ax.set_ylabel("Event rate (%)")
    ax.set_ylim(bottom=0)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(ncol=2, frameon=False, fontsize=8)
    fig.tight_layout()
    for suffix in ("pdf", "png"):
        fig.savefig(output_dir / f"semantic_focus.{suffix}", dpi=300)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.16, 3.0))
    radii = (2, 4, 6)
    for method, color, marker in (("fixed_margin", "#4C72B0", "o"), ("robust_depth", "#55A868", "s")):
        values, lows, highs = [], [], []
        for radius in radii:
            key = f"calibrated_correlated__radius_{radius}__byz_1"
            stat = aggregate[key][method]["decisive_coverage"]
            values.append(stat["mean"] * 100)
            lows.append((stat["mean"] - stat["ci95_low"]) * 100)
            highs.append((stat["ci95_high"] - stat["mean"]) * 100)
        ax.errorbar(radii, values, yerr=[lows, highs], label=method.replace("_", " "), color=color, marker=marker, capsize=3)
    ax.set_xlabel("Maximum declared box radius (quantized units)")
    ax.set_ylabel("Decisive coverage (%)")
    ax.set_xticks(radii)
    ax.set_ylim(0, 100)
    ax.grid(alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    for suffix in ("pdf", "png"):
        fig.savefig(output_dir / f"availability_radius.{suffix}", dpi=300)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=30)
    parser.add_argument("--events-per-seed", type=int, default=80)
    parser.add_argument("--seed-base", type=int, default=20260904)
    parser.add_argument("--sources", type=int, default=5)
    parser.add_argument("--assumed-byzantine", type=int, default=1)
    parser.add_argument("--miscoverage-budget", type=int, default=0)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("semantic_results.json"))
    args = parser.parse_args()
    results = run(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2), encoding="utf-8")
    figure_dir = args.output.parent if args.output.name == "semantic_results.json" else args.output.parent / (args.output.stem + "_figures")
    figure_dir.mkdir(parents=True, exist_ok=True)
    plot_results(results, figure_dir)
    print(json.dumps({
        "output": str(args.output),
        "invariant_violations": results["invariant_violations_under_stated_assumptions"],
        "conditions": len(results["design"]["conditions"]),
    }, indent=2))


if __name__ == "__main__":
    main()
