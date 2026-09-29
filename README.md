# ZCRSC-PAPER

Reproducibility repository for the manuscript **Zero-Knowledge Certification of Robust Spacetime Compliance under Byzantine Evidence for Vehicular Crowdsensing**.

This repository is the **canonical public code and experiment repository** cited by the paper. The manuscript source and JISA submission files remain in [js110/Apaper](https://github.com/js110/Apaper).

The initial reproducibility snapshot was migrated from `js110/Apaper` commit `2718922fbb2337ee28793cb8ea1d9cb52f21c309`.

## Contents

- `prototype/`: Python reference semantics plus the Go/gnark signed-box circuits, gateway, tests, cryptographic benchmarks, and point-ZK lower-bound baseline.
- `experiments/`: synthetic semantics, calibration diagnostics, compilation sweep records, cryptographic benchmark records, statistical summaries, and analysis scripts.
- `figures/`: publication plotting configuration and the result-rendering script used by the manuscript.
- `requirements.txt`: direct Python dependencies used by the experiment/plotting pipeline.

Generated manuscript PNG/PDF figure files are intentionally not duplicated here; the manuscript repository retains the submission-ready figures.

## Quick reproduction

Install the direct Python dependencies:

```bash
python3 -m pip install -r requirements.txt
```

Run the finite-domain reference tests:

```bash
cd prototype
python3 -m unittest -v test_robust_depth.py
```

Run the Go/gnark tests:

```bash
cd prototype/zkdepth
go test ./...
```

Regenerate the synthetic semantic experiments from the repository root:

```bash
python3 experiments/run_semantic_evaluation.py
python3 experiments/run_semantic_evaluation.py --miscoverage-budget 1 --output experiments/semantic_results_r1.json
python3 experiments/run_semantic_evaluation.py --miscoverage-budget 2 --output experiments/semantic_results_r2.json
python3 experiments/summarize_ablation.py
python3 experiments/summarize_results.py
```

The three full per-event semantic result files (`semantic_results.json`, `semantic_results_r1.json`, and `semantic_results_r2.json`) are deterministic generated artifacts of roughly 2.3 MB each. They are not duplicated in this migrated repository snapshot because the connector used for the migration cannot reliably transfer those large text blobs; the commands above regenerate them from the tracked scripts and fixed seeds. The compact tables, summaries, benchmark records, and other archived results used to audit the manuscript are tracked.

## Scope

The code implements the provisioned evidence-certificate layer evaluated in the manuscript. It is not an end-to-end vehicular crowdsensing platform and does not provide participant recruitment, incentives, anonymous networking, dynamic roster management, issuer-independence guarantees, or field calibration.

## Data and external software

Third-party datasets and upstream reference implementations retain their own licenses and distribution terms. Where redistribution permission is not established, this repository keeps derived records, hashes, scripts, or pinned source identifiers but does not claim ownership of the upstream data. UrbanNav and GraphGNSSLib source data should be obtained from their cited original sources when reproducing the corresponding diagnostics.
