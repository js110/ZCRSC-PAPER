#!/usr/bin/env python3
"""Create manuscript tables and the cryptographic scaling figure."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


HERE = Path(__file__).resolve().parent


def ci_text(stat: dict[str, float]) -> str:
    return f"{100 * stat['mean']:.2f} [{100 * stat['ci95_low']:.2f}, {100 * stat['ci95_high']:.2f}]"


def main() -> None:
    semantic = json.loads((HERE / "semantic_results.json").read_text())
    aggregate = semantic["aggregate"]
    benchmark_paths = sorted(HERE.glob("zkdepth_n*_d*_formal.json")) + sorted(HERE.glob("subset_n*_d*_formal.json"))
    benchmarks = [json.loads(path.read_text()) for path in benchmark_paths]

    benchmark_rows = []
    for result in benchmarks:
        prove = np.asarray(result["prove_ms"])
        verify = np.asarray(result["verify_ms"])
        benchmark_rows.append({
            "geometry": result.get("geometry_backend", "depth"),
            "n": result["n"],
            "d": result["d"],
            "constraints": result["constraints"],
            "setup_ms": result["setup_ms"],
            "prove_p50_ms": float(np.quantile(prove, 0.50)),
            "prove_p95_ms": float(np.quantile(prove, 0.95)),
            "prove_p99_ms": float(np.quantile(prove, 0.99)),
            "verify_p50_ms": float(np.quantile(verify, 0.50)),
            "verify_p95_ms": float(np.quantile(verify, 0.95)),
            "verify_p99_ms": float(np.quantile(verify, 0.99)),
            "proof_bytes": result["proof_bytes"],
            "public_witness_bytes": result["public_witness_bytes"],
        })
    with (HERE / "zk_benchmark_table.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=benchmark_rows[0].keys())
        writer.writeheader()
        writer.writerows(benchmark_rows)

    focus_key = "calibrated_correlated__radius_4__byz_1"
    focus_rows = []
    for method, metrics in aggregate[focus_key].items():
        focus_rows.append({
            "method": method,
            "false_accept_percent_ci95": ci_text(metrics["false_accept_rate"]),
            "false_reject_percent_ci95": ci_text(metrics["false_reject_rate"]),
            "ambiguous_percent_ci95": ci_text(metrics["ambiguous_rate"]),
            "evidence_failure_percent_ci95": ci_text(metrics["evidence_failure_rate"]),
            "decisive_coverage_percent_ci95": ci_text(metrics["decisive_coverage"]),
            "decisive_accuracy_percent_ci95": ci_text(metrics["decisive_accuracy"]),
        })
    with (HERE / "semantic_focus_table.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=focus_rows[0].keys())
        writer.writeheader()
        writer.writerows(focus_rows)

    stated_keys = [
        key for key in aggregate
        if key.startswith(("calibrated_independent", "calibrated_correlated"))
        and key.endswith(("byz_0", "byz_1"))
    ]
    focus_seed_counts = semantic["seed_counts"][focus_key]["robust_depth"]
    wrong_seed_count = sum(
        (row["false_accept"] + row["false_reject"]) > 0
        for row in focus_seed_counts
    )
    zero_error_cluster_upper95 = (
        1.0 - 0.05 ** (1.0 / len(focus_seed_counts))
        if wrong_seed_count == 0 else None
    )
    summary = {
        "stated_assumption_conditions": len(stated_keys),
        "robust_false_accept_mean_across_conditions": float(np.mean([
            aggregate[key]["robust_depth"]["false_accept_rate"]["mean"] for key in stated_keys
        ])),
        "robust_false_reject_mean_across_conditions": float(np.mean([
            aggregate[key]["robust_depth"]["false_reject_rate"]["mean"] for key in stated_keys
        ])),
        "robust_decisive_coverage_mean_across_conditions": float(np.mean([
            aggregate[key]["robust_depth"]["decisive_coverage"]["mean"] for key in stated_keys
        ])),
        "fixed_margin_decisive_coverage_mean_across_conditions": float(np.mean([
            aggregate[key]["fixed_margin"]["decisive_coverage"]["mean"] for key in stated_keys
        ])),
        "focus_condition": focus_key,
        "focus_seed_cluster_wrong_decisive": {
            "clusters": len(focus_seed_counts),
            "clusters_with_any_wrong_decisive": wrong_seed_count,
            "one_sided_exact_upper95_if_zero": zero_error_cluster_upper95,
            "estimand": "probability that an identically generated seed cluster contains at least one wrong decisive event",
            "note": "Synthetic-generator bound; not a field error-rate bound.",
        },
        "focus": aggregate[focus_key],
        "negative_controls": {
            "undercoverage": aggregate["undercovered_correlated__radius_4__byz_1"]["robust_depth"],
            "budget_exceeded": aggregate["calibrated_correlated__radius_4__byz_2"]["robust_depth"],
        },
        "hardware": {
            "model": "Mac mini (Macmini9,1)",
            "soc": "Apple M1, 8 cores (4 performance, 4 efficiency)",
            "memory_gb": 16,
            "os": "macOS 26.6.2",
            "go": "1.25.6",
            "gnark": "0.14.0",
        },
        "benchmark_rows": benchmark_rows,
    }
    (HERE / "results_summary.json").write_text(json.dumps(summary, indent=2) + "\n")

    rows = sorted(benchmark_rows, key=lambda row: (row["d"], row["n"]))
    fig, axes = plt.subplots(1, 2, figsize=(7.16, 2.7))
    for d, color, marker in ((2, "#4C72B0", "o"), (3, "#C44E52", "s")):
        selected = [row for row in rows if row["d"] == d and row["geometry"] == "depth"]
        axes[0].plot([row["n"] for row in selected], [row["constraints"] / 1000 for row in selected], marker=marker, color=color, label=f"d={d}")
        axes[1].plot([row["n"] for row in selected], [row["prove_p50_ms"] for row in selected], marker=marker, color=color, label=f"d={d}")
    axes[0].set_ylabel("R1CS constraints (thousands)")
    axes[1].set_ylabel("Proving time p50 (ms)")
    for ax in axes:
        ax.set_xlabel("Evidence sources n")
        ax.grid(alpha=0.25)
        ax.legend(frameon=False)
        ax.set_xticks(sorted({row["n"] for row in rows}))
    fig.tight_layout()
    for suffix in ("pdf", "png"):
        fig.savefig(HERE / f"zk_scaling.{suffix}", dpi=300)
    plt.close(fig)

    # Paired bootstrap resamples seeds, keeping the same events and both rules
    # together. It conditions on the chosen simulation design.
    focus = semantic['seed_results'][focus_key]
    differences = np.array([a['decisive_coverage']-b['decisive_coverage'] for a,b in
                            zip(focus['robust_depth'],focus['fixed_margin'])])
    rng = np.random.default_rng(20260905)
    boot = rng.choice(differences, size=(10000,len(differences)), replace=True).mean(axis=1)
    paired = dict(mean_percentage_points=float(100*differences.mean()),
                  bootstrap95_percentage_points=(100*np.quantile(boot,[.025,.975])).tolist(),
                  unit='paired simulation seed', resamples=10000, seed=20260905,
                  undefined_class_seed_count=sum(c['inside']==0 or c['outside']==0
                      for cond in semantic['seed_counts'].values() for c in cond['robust_depth']))
    (HERE/'paired_comparison.json').write_text(json.dumps(paired,indent=2)+'\n')


if __name__ == "__main__":
    main()
