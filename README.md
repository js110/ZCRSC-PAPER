# ZCRSC-PAPER

Reproducibility repository for **Zero-Knowledge Certification of Robust Spacetime Compliance under Byzantine Evidence for Vehicular Crowdsensing**.

The JISA manuscript source and submission material live in [js110/Apaper](https://github.com/js110/Apaper). This repository is the canonical public location for the paper's implementation and experiment workflow.

## Repository layout

- `prototype/` — exact robust-depth reference semantics plus the Go/gnark Groth16/BN254 circuits, gateway, tests, and point-ZK lower-bound baseline.
- `experiments/` — semantic simulation, calibration/trace analysis scripts, benchmark records, compilation-sweep records, and compact result summaries.
- `figures/` — result-figure regeneration script and publication plotting configuration.
- `requirements.txt` — direct Python dependencies used by the experiment/plotting pipeline.

## Quick validation

```bash
python3 -m pip install -r requirements.txt
python3 -m unittest -v prototype/test_robust_depth.py

cd prototype/zkdepth
go test ./...
go run ./cmd/pointbench --d 2 --bits 16 --output ../../experiments/point_zk_d2.json
go run ./cmd/pointbench --d 3 --bits 16 --output ../../experiments/point_zk_d3.json
```

To regenerate the main synthetic semantic record:

```bash
python3 experiments/run_semantic_evaluation.py --output experiments/semantic_results.json
```

The full `semantic_results*.json` files are generated outputs and are intentionally not duplicated from the manuscript-development repository because they are several megabytes each. Compact summaries and the manuscript-reported formal benchmark records are versioned here. `receiver_residuals.csv` is also not copied because the receiver diagnostic is derived from third-party data whose redistribution status is not asserted by the authors.

## Scope and data boundary

The code implements the provisioned evidence-certificate layer evaluated in the manuscript. It is not an end-to-end vehicular crowdsensing platform and does not provide participant recruitment, incentives, anonymous networking, dynamic roster management, or field calibration.

Third-party datasets and upstream reference implementations retain their own licenses and distribution terms. Scripts, hashes, and derived compact records are provided where appropriate; upstream data should be obtained from the sources cited by the paper.
