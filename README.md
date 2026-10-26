# ZCRSC-PAPER

Public reproducibility repository for **Zero-Knowledge Certification of Robust Spacetime Compliance under Byzantine Evidence for Vehicular Crowdsensing**.

The Journal of Network and Computer Applications (JNCA) manuscript, LaTeX figures and submission material live in [js110/Apaper](https://github.com/js110/Apaper). This separate repository contains the implementation, source scripts and experiment records cited by that manuscript.

## Quick validation from this repository root

Requires Python 3.13 (CI), Go 1.25.0 or compatible, and Git. Python dependency versions are in `requirements.txt`; Go dependencies and checksums are in `prototype/zkdepth/go.mod` and `go.sum`.

```sh
python3 -m pip install -r requirements.txt
python3 -m unittest discover -s prototype -p test_robust_depth.py -v
python3 -m unittest discover -s experiments -p test_receiver_calibration.py -v
go -C prototype/zkdepth test -count=1 ./...
python3 figures/render_compile_sweep.py experiments/compile_sweep_20260915T010554Z
```

Every command above starts at the repository root. The compilation renderer uses archived measurements and does not execute the expensive sweep.

## Reproduce the paper

[experiments/README.md](experiments/README.md) maps each reported experiment to its inputs, exact commands and output records, including:

- the 27-condition, 30-seed synthetic evaluation and paired r=0,1,2 analyses;
- explicit, hash-verified acquisition of pinned UrbanNav and GraphGNSSLib raw inputs;
- the archived compilation grid (30 unique grid cases plus two compatibility controls);
- the permanent [n=8 raw trials](experiments/subset_n8_d2_formal_30.json), [provenance](experiments/subset_n8_d2_provenance.json) and [linear-quantile summary](experiments/subset_n8_d2_summary.json);
- a first-vector ZKLP instrumentation overlay, a same-host execution script and manual CI workflow that preserve the pinned upstream circuit and its gnark replacement.

Cryptographic timings depend on hardware and system load. Rerunning a workflow generates new measurements, not an expectation of identical historical wall-clock values. The Mac M1, same-runner comparison and n=8 Linux results are separate records.

## Data and scope

`prototype/` contains inclusive-integer reference semantics and Go/gnark Groth16/BN254 circuits, gateway and tests. `experiments/` contains scripts, benchmark arrays and compact summaries. `figures/` contains plotting code.

Full `semantic_results*.json` files are reproducible generated outputs and are not versioned. The derived `experiments/receiver_residuals.csv` **is** versioned. Original third-party UrbanNav and GraphGNSSLib inputs are not redistributed; their pinned URLs and SHA-256 hashes are in `experiments/external_data_manifest.json`. Review the upstream dataset terms before explicitly requesting a download. Authors must confirm the appropriate publication terms for derived data.

The prototype implements a provisioned evidence-certificate layer. It does not implement participant recruitment, incentives, anonymous networking, dynamic rosters, field calibration or durable distributed replay storage. All four successfully verified decision classes consume their challenges; only Valid accepts the report. Failed proof attempts leave an unexpired challenge pending.

## License status

No project license has yet been selected by the authors. Public availability is not a license grant. A code/data license is an outstanding author decision; this maintenance revision does not assign one on their behalf. Third-party sources and datasets retain their own terms.
