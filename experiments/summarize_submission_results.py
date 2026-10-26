"""Reproduce JNCA macro/focus coverage and uncertainty from seed-level records."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("semantic_record", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.semantic_record.resolve() == args.output.resolve():
        parser.error("Do not overwrite the raw semantic record.")
    raw = args.semantic_record.read_bytes()
    record = json.loads(raw)
    aggregate = record["aggregate"]
    keys = [key for key in aggregate if key.startswith(("calibrated_independent", "calibrated_correlated")) and key.endswith(("byz_0", "byz_1"))]
    if len(keys) != 12:
        raise ValueError("Expected the twelve within-budget calibrated conditions.")
    robust = np.array([aggregate[k]["robust_depth"]["decisive_coverage"]["mean"] for k in keys])
    fixed = np.array([aggregate[k]["fixed_margin"]["decisive_coverage"]["mean"] for k in keys])
    differences = robust - fixed
    rng = np.random.default_rng(718263)
    boot = rng.choice(differences, size=(20000, len(keys)), replace=True).mean(axis=1)
    focus = "calibrated_correlated__radius_4__byz_1"
    rates = record["seed_results"][focus]
    focus_differences = np.array([a["decisive_coverage"]-b["decisive_coverage"] for a,b in zip(rates["robust_depth"], rates["fixed_margin"])])
    rng = np.random.default_rng(20260905)
    focus_boot = rng.choice(focus_differences, size=(10000,len(focus_differences)), replace=True).mean(axis=1)
    result = {"semantic_record": args.semantic_record.name, "sha256": hashlib.sha256(raw).hexdigest(),
              "macro": {"conditions": keys, "robust_coverage_percent": float(100*robust.mean()),
                        "fixed_margin_coverage_percent": float(100*fixed.mean()),
                        "gain_percentage_points": float(100*differences.mean()),
                        "bootstrap95_percentage_points": (100*np.quantile(boot,[.025,.975],method="linear")).tolist(),
                        "bootstrap_unit": "condition-level paired difference", "resamples": 20000, "seed": 718263, "random_generator": "numpy.random.default_rng / PCG64",
                        "scope": "Variability over this fixed twelve-condition simulation grid, not a field-performance guarantee."},
              "focus": {"condition": focus, "gain_percentage_points": float(100*focus_differences.mean()),
                        "bootstrap95_percentage_points": (100*np.quantile(focus_boot,[.025,.975],method="linear")).tolist(),
                        "bootstrap_unit": "paired simulation seed", "resamples": 10000,"seed": 20260905, "random_generator": "numpy.random.default_rng / PCG64"},
              "undercoverage_diagnostics": record["assumption_diagnostics"]["undercovered_correlated__radius_4__byz_1"],
              "rate_definitions": {"FA": "false accepts / truly outside events", "FR": "false rejects / truly inside events",
                                   "wrong_among_decisive": "all wrong decisive outcomes / all decisive outcomes"}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))


if __name__ == "__main__":
    main()
