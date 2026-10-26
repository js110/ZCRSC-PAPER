"""Summarize archived trials using one explicitly defined quantile convention."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.record.resolve() == args.output.resolve():
        parser.error("Output must differ from the raw record.")
    raw = args.record.read_bytes()
    record = json.loads(raw)
    result = {key: record[key] for key in ("n", "d", "constraints", "setup_ms", "proof_bytes", "public_witness_bytes", "go_version", "goos", "goarch")}
    result.update(record_file=args.record.name, record_sha256=hashlib.sha256(raw).hexdigest(),
                  quantile_method="numpy.quantile(method='linear')", numpy_version=np.__version__)
    for name in ("prove_ms", "verify_ms"):
        values = np.asarray(record[name], dtype=float)
        if len(values) != record["repetitions"] or not np.all(np.isfinite(values)) or np.any(values < 0):
            raise ValueError(f"Invalid {name} trials")
        result[name] = {"trials": len(values), "p50": float(np.quantile(values, .5, method="linear")),
                        "p95": float(np.quantile(values, .95, method="linear"))}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
