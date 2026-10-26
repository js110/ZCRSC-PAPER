"""Run pinned ZKLP and our subset benchmark sequentially on the same host.

Requires git, Go, and a C compiler (the upstream h3-go dependency uses cgo).
Upstream sources stay in the requested work directory, outside this repository.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
COMMIT = "e8e321524982ddd9dddea37db6fa352529db62c4"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=10)
    args = parser.parse_args()
    if args.repetitions < 1:
        parser.error("repetitions must be positive")
    work = args.work_dir.resolve()
    if work == ROOT or ROOT in work.parents:
        parser.error("Use a work directory outside this repository.")
    work.mkdir(parents=True, exist_ok=True)
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    upstream = work / "zk-Location"
    if not upstream.exists():
        subprocess.run(["git", "clone", "--filter=blob:none", "--no-checkout", "https://github.com/tumberger/zk-Location.git", str(upstream)], check=True)
        subprocess.run(["git", "checkout", COMMIT], cwd=upstream, check=True)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=upstream, text=True).strip()
    if head != COMMIT:
        raise SystemExit("Existing upstream checkout has a different commit; choose an empty work directory.")
    if subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=all"], cwd=upstream, text=True).strip():
        raise SystemExit("Existing upstream checkout is not clean (tracked or untracked files).")
    overlay = HERE / "zklp_smoke_test.go"
    target = upstream / "loc2index32" / "paper_reproduction_test.go"
    if target.exists():
        raise SystemExit("Instrumentation target already exists; choose a clean work directory.")
    shutil.copyfile(overlay, target)
    try:
        env = {**os.environ, "ZCRSC_BENCH_OUTPUT": str(output / "zklp_same_runner.json"),
               "ZCRSC_BENCH_REPETITIONS": str(args.repetitions), "CGO_ENABLED": "1"}
        subprocess.run(["go", "test", "-count=1", "-run", "^TestPaperSameRunnerZKLP$", "-v", "./loc2index32"], cwd=upstream, env=env, check=True)
    finally:
        target.unlink()
    subprocess.run(["go", "run", "./cmd/bench", "--n", "3", "--d", "2", "--bits", "16", "--geometry", "subset",
                    "--repetitions", str(args.repetitions), "--output", str(output / "ours_same_runner_subset_n3_d2.json")], cwd=ROOT / "prototype/zkdepth", check=True)
    for filename, expected in [("zklp_same_runner.json", 19467), ("ours_same_runner_subset_n3_d2.json", 32474)]:
        path = output / filename
        record = json.loads(path.read_text())
        if record["constraints"] != expected:
            raise ValueError(f"Unexpected compiled relation in {filename}: {record['constraints']}")
        record["prove_median_ms"] = statistics.median(record["prove_ms"])
        record["verify_median_ms"] = statistics.median(record["verify_ms"])
        path.write_text(json.dumps(record, indent=2) + "\n")
    manifest = {"upstream_commit": COMMIT, "upstream_url": "https://github.com/tumberger/zk-Location",
                "upstream_go_mod": (upstream / "go.mod").read_text(),
                "test_vector": "first line of data/f32/loc2index32.txt",
                "test_vector_first_line": (upstream / "data/f32/loc2index32.txt").read_text().splitlines()[0],
                "test_vector_file_sha256": hashlib.sha256((upstream / "data/f32/loc2index32.txt").read_bytes()).hexdigest(),
                "instrumentation_sha256": hashlib.sha256(overlay.read_bytes()).hexdigest(),
                "repetitions": args.repetitions, "execution": "sequentially in one host process environment; separate Go modules",
                "note": "New measurements, not an assertion of identical historical wall-clock timings. Relations and gnark versions differ."}
    (output / "same_runner_provenance.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Saved records and provenance in {output}")


if __name__ == "__main__":
    main()
