#!/usr/bin/env python3
import argparse
import csv
import json
import statistics
from pathlib import Path

def read_json(path):
    return json.loads(Path(path).read_text())

def read_zklp_csv(path):
    rows=[]
    with open(path,newline="") as f:
        reader=csv.DictReader(f, skipinitialspace=True)
        for raw in reader:
            r={k.strip(): v.strip() for k,v in raw.items()}
            rows.append({
                "resolution": int(r["Resolution"]),
                "index": int(r["Index"]),
                "constraints": int(r["NbConstraints"]),
                "compilation_us": int(r["CompilationTime"]),
                "setup_us": int(r["SetupTime"]),
                "prover_us": int(r["ProverTime"]),
                "verifier_us": int(r["VerifierTime"]),
            })
    return rows

def summary_ms(values_us):
    vals=[v/1000.0 for v in values_us]
    return {
        "n": len(vals),
        "mean_ms": statistics.fmean(vals),
        "median_ms": statistics.median(vals),
        "min_ms": min(vals),
        "max_ms": max(vals),
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--zklp-csv", required=True)
    ap.add_argument("--zklp-same-runner", required=True)
    ap.add_argument("--ours-same-runner", required=True)
    ap.add_argument("--output", required=True)
    args=ap.parse_args()

    rows=read_zklp_csv(args.zklp_csv)
    constraints=sorted(set(r["constraints"] for r in rows))
    if len(constraints)!=1:
        raise RuntimeError(f"unexpected ZKLP constraint counts: {constraints}")

    out={
        "comparison_policy": {
            "purpose": "Recent-work context, not a performance ranking.",
            "cross_hardware_rule": "Source-reported runtimes are not compared as speedups across different machines, protocol stacks, or security relations.",
            "same_runner_rule": "The ZKLP smoke benchmark and our subset benchmark run on the same GitHub Actions runner, but use different gnark versions and certify different relations; their timings remain descriptive only."
        },
        "zklp": {
            "paper": "Ernstberger et al., IEEE S&P 2025",
            "repository": "https://github.com/tumberger/zk-Location",
            "pinned_commit": "e8e321524982ddd9dddea37db6fa352529db62c4",
            "source_artifact": "benchmarks/m6i.xlarge/bench_ZKLP32_G16_BN254.txt",
            "source_artifact_summary": {
                "rows": len(rows),
                "constraints": constraints[0],
                "prover": summary_ms([r["prover_us"] for r in rows]),
                "verifier": summary_ms([r["verifier_us"] for r in rows]),
                "setup": summary_ms([r["setup_us"] for r in rows]),
            },
            "same_runner_smoke": read_json(args.zklp_same_runner),
        },
        "ours": {
            "same_runner_subset_n3_d2": read_json(args.ours_same_runner),
        },
        "recent_work_context": [
            {
                "work":"BFT-PoLoc",
                "year":2024,
                "evaluation":"450 RIPE Atlas Waldos; 22/37/450 challengers; 37 deployed cloud challengers (34 US, 2 Canada, 1 Mexico).",
                "reported_result":"<100 km uncertainty for about 20%, 25%, 45% with 22, 37, 450 challengers; <1000 km for about 80%, 85%, 95%.",
                "comparability":"Different problem: Internet-delay localization; no ZK witness-hiding comparison."
            },
            {
                "work":"PG",
                "year":2024,
                "evaluation":"AWS deployment up to 261 sensors and cyber-physical deployment up to 19 resource-constrained sensors.",
                "reported_result":"Privacy-preserving Byzantine sensor fusion with guaranteed output delivery.",
                "comparability":"Different distributed GC architecture and output interface; runtime not normalized against our SNARK."
            },
            {
                "work":"Vehicle ZK-PoL",
                "year":2025,
                "evaluation":"200, 3600, and 43,800 trajectory points; Raspberry Pi/phone/PC provers and remote verifier; interactive ZK backends.",
                "reported_result":"For 43,800 points, about 36 min for EV subsidy and 59 min for highway taxation.",
                "comparability":"Closest policy-compliance application, but trajectory-wide interactive proofs differ from our one-event noninteractive certificate."
            },
            {
                "work":"CRSF",
                "year":2026,
                "evaluation":"Google Cloud; fault-free and faulty executions; up to 261 sensors.",
                "reported_result":"Largest tested total measured phase time reported around one second.",
                "comparability":"Different collusion-resilient garbled-circuit sensor-fusion protocol; no direct proof-size/prover-time comparison."
            }
        ]
    }
    Path(args.output).write_text(json.dumps(out,indent=2)+"\n")

if __name__=="__main__":
    main()
