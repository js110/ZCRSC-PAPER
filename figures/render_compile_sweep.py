"""Render archived measured R1CS counts; resource-limited points stay gaps."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_directory", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    source = args.run_directory / "results.json"
    raw = source.read_bytes()
    rows = json.loads(raw)
    plan = json.loads((args.run_directory / "plan.json").read_text())
    if len(rows) != len(plan["jobs"]):
        raise ValueError("Results do not cover the planned jobs.")
    for row, job in zip(rows, plan["jobs"]):
        if any(row[k] != job[k] for k in ("n", "d", "k", "backend")):
            raise ValueError("Results and planned execution order differ.")
        if row["status"] == "ok" and (row["returncode"] != 0 or row.get("constraints", 0) <= 0):
            raise ValueError("Successful rows must have measured constraints.")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.4), layout="constrained")
    styles = [("Lower corner", "depth", None, "o"), ("Subset b=1", "subset", 1, "s"),
              ("Subset b=2", "subset", 2, "^"), ("Subset k=n/2", "subset", "half", "D")]
    table = []
    for ax, d in zip(axes, (2, 3)):
        for label, backend, budget, marker in styles:
            values = []
            for n in (4, 8, 12, 16):
                k = n // 2 if budget == "half" else n - (budget or 1)
                matches = [r for r in rows if (r["n"], r["d"], r["backend"], r["k"]) == (n, d, backend, k)]
                if len(matches) != 1:
                    raise ValueError(f"Expected exactly one measured or limited row: {n,d,backend,k}")
                row = matches[0]
                value = row.get("constraints") if row["status"] == "ok" else None
                values.append(value if value is not None else np.nan)
                table.append({"d": d, "n": n, "series": label, "k": k, "status": row["status"], "constraints": value})
            ax.plot((4, 8, 12, 16), values, marker=marker, label=label)
        ax.set(title=f"d={d}", xlabel="Issuers n", ylabel="R1CS constraints", yscale="log", xticks=(4, 8, 12, 16))
        ax.grid(alpha=.2)
        ax.legend(fontsize=8)
    for suffix in ("png", "pdf", "svg"):
        fig.savefig(args.output_dir / f"compile_scalability.{suffix}", dpi=300)
    plt.close(fig)
    with (args.output_dir / "compile_scalability_data.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=table[0].keys())
        writer.writeheader()
        writer.writerows(table)
    manifest = {"source_run_directory": args.run_directory.name,
                "results_sha256": hashlib.sha256(raw).hexdigest(), "total_runs": len(rows),
                "grid_runs": sum(r["n"] in (4,8,12,16) for r in rows),
                "compatibility_controls": sum(r["n"] == 5 for r in rows),
                "successful_runs": sum(r["status"] == "ok" for r in rows),
                "limited_runs": sum(r["status"] != "ok" for r in rows),
                "note": "Grid has 30 unique jobs; n=4 subset b=2 and k=n/2 share one measured row. Two n=5,d=2 controls are excluded from plotted grid. Limited runs are gaps, never estimates."}
    (args.output_dir / "compile_scalability_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    if hashlib.sha256(source.read_bytes()).hexdigest() != manifest["results_sha256"]:
        raise ValueError("Source changed during plotting.")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
