# Experiment reproduction and evidence map

Run the commands below from the **ZCRSC-PAPER repository root**, unless the command explicitly changes the working directory. Use an output directory outside this repository for new benchmark measurements when preserving archived records.

## Synthetic semantics and paired ablation

```sh
python3 -m pip install -r requirements.txt
python3 experiments/run_semantic_evaluation.py --output experiments/semantic_results.json
python3 experiments/run_semantic_evaluation.py --miscoverage-budget 1 --output experiments/semantic_results_r1.json
python3 experiments/run_semantic_evaluation.py --miscoverage-budget 2 --output experiments/semantic_results_r2.json
python3 experiments/summarize_results.py
python3 experiments/summarize_ablation.py
python3 experiments/summarize_submission_results.py experiments/semantic_results.json --output experiments/submission_results_summary.json
python3 figures/render_results.py
```

Defaults fix 27 conditions, 30 seeds, 80 events per seed per condition and seed base 20260904: 64,800 events, each with five evidence boxes. r=1 and r=2 use the same random inputs, not independent extra datasets. The JNCA `submission_results_summary.json` uses NumPy default_rng, 20,000 paired condition resamples with seed 718263 for the 12-condition macro interval, and 10,000 paired seed resamples with seed 20260905 for the focus interval. Its within-grid macro interval is not a field-generalization bound.

Existing `results_summary.json`, `paired_comparison.json`, `miscoverage_ablation.json` and `jisa_security_diagnostics.json` retain historical names for stable citations. FA/FR divide errors by true-outside/true-inside counts; wrong-among-decisive risk has a different denominator. The undercovered-model condition contains both M<=r and M>r events.

## Exact external raw inputs

The [manifest](external_data_manifest.json) fixes upstream URLs, commits, target paths and SHA-256 values. Raw data are excluded from Git. These optional commands download the exact raw bytes from their original public hosts; review the upstream dataset terms first.

```sh
python3 experiments/fetch_external_data.py --dataset urbannav
python3 experiments/fetch_external_data.py --dataset graphgnss
python3 experiments/fetch_external_data.py --dataset all --verify-only
python3 experiments/run_trace_evaluation.py
python3 experiments/run_receiver_calibration.py
```

UrbanNav: [UrbanNavDataset](https://github.com/IPNL-POLYU/UrbanNavDataset), pinned commit `e53717a40c94803cd479a140433f6d803b1a0876`, `tools/gt_vis/data/UrbanNav_TST_GT_raw.txt`; the bytes hash to `9d48bb497878aafbd17290789560394c72ecafec20c9e0eaff448418695d92bf`, matching the historical `trace_results.json`. Pinning this retrieval commit establishes the exact public source bytes; it is not a claim that this commit was recorded in the original experiment log. The replay uses measured reference kinematics with simulated evidence errors, not measured multisource GNSS evidence.

GraphGNSSLib: [source directory](https://github.com/weisongwen/GraphGNSSLib/tree/e9e4c6a4ded5dc7f2813265a76a56b280f714a3f/global_fusion/dataset/gps_solution_TST2), pinned commit `e9e4c6a4ded5dc7f2813265a76a56b280f714a3f`; `groundTruth_TST.csv` and `rtklibResult.pos` are saved under `experiments/graphgnss_tst2/`. The diagnostic follows [calibration_protocol.md](calibration_protocol.md). It is retrospective, stationary and single-receiver. `score_m` and square containment use Chebyshev residuals; `horizontal_median_m` uses Euclidean horizontal distance. Recomputing these outputs may change text-file line endings but must preserve the numerical results and source-byte hashes.

## Full circuit costs and archived compilation

```sh
go -C prototype/zkdepth run ./cmd/pointbench --d 2 --bits 16 --output ../../experiments/point_zk_d2_new.json
go -C prototype/zkdepth run ./cmd/pointbench --d 3 --bits 16 --output ../../experiments/point_zk_d3_new.json
go -C prototype/zkdepth run ./cmd/bench --geometry subset --n 4 --d 3 --bits 16 --repetitions 30 --output ../../experiments/subset_n4_d3_new.json
go -C prototype/zkdepth run ./cmd/bench --geometry depth --n 4 --d 3 --bits 16 --repetitions 30 --output ../../experiments/depth_n4_d3_new.json
python3 experiments/run_compile_sweep.py
```

The compilation sweep creates a new timestamped directory. It does **not** run setup or proofs. The archived [plan](compile_sweep_20260915T010554Z/plan.json), [32 results](compile_sweep_20260915T010554Z/results.json) and child logs are retained. There are 30 unique grid cases because n=4,b=2 and k=n/2 coincide, plus two n=5,d=2 controls; 27 total runs succeeded and five hit the RSS limit.

Render the archived counts without rerunning compilation:

```sh
python3 figures/render_compile_sweep.py experiments/compile_sweep_20260915T010554Z
```

This emits PDF/SVG/PNG, an exact plotted-data CSV, and a manifest separating grid cases from controls. Limited points remain gaps, never estimates. Existing original plan/source hashes describe the original implementation commit; maintaining the reproduction scripts does not rewrite that historical provenance.

## Permanent eight-issuer record and quantiles

`subset_n8_d2_formal_30.json` is the unmodified artifact downloaded from [run39109997226](https://github.com/js110/ZCRSC-PAPER/actions/runs/39109997226), source commit `ac02137d230e1382b95982b794ad872f108c487e`, on 2026-10-26. Its SHA-256 and original expiring-artifact metadata are in `subset_n8_d2_provenance.json`. Keeping the raw JSON in Git removes reliance on Actions artifact retention.

```sh
python3 experiments/summarize_benchmark_record.py experiments/subset_n8_d2_formal_30.json --output experiments/subset_n8_d2_summary.json
```

All current summary p95 values use `numpy.quantile(method='linear')`. For the archived n=8 array: proving p50/p95=902.0885/923.1667ms; verification p50/p95=1.237/1.38715ms. The historical workflow printed nearest-rank p95=926.998/1.438ms; that original log is preserved, while the manuscript and maintained summary use the common linear convention. Raw timings are unchanged.

Reproduce n=8 independently with `.github/workflows/n8_benchmark.yml` (`workflow_dispatch`) or the exact command recorded in its provenance JSON. Newly produced measurements should be saved under a different name; do not overwrite the historical raw artifact.

## ZKLP same-host execution chain

Historical records are `zklp_same_runner.json` and `ours_same_runner_subset_n3_d2.json`. Upstream is [tumberger/zk-Location](https://github.com/tumberger/zk-Location/tree/e8e321524982ddd9dddea37db6fa352529db62c4), commit `e8e321524982ddd9dddea37db6fa352529db62c4`. Its go.mod requires gnark 0.9.1 and replaces it with `github.com/winderica/gnark` commit `e30c94cd2e7e`; the replacement is deliberately retained.

The new `zklp_smoke_test.go` is instrumentation only. It is temporarily installed alongside the pinned upstream tests, uses the upstream `loc2Index32Circuit` and first exact hexadecimal vector (`3F311FBF 3F35A99C 0 1 0 1`), runs one setup and repeated real proofs/verifications, and serializes the proof/public witness using each library's own `WriteTo`. It does not vendor or modify the upstream circuit. A C compiler is required by upstream h3-go/cgo; no H3 command-line binary is invoked by this vector.

```sh
python3 experiments/run_same_runner.py --work-dir ../zklp-reproduction-work --output-dir ../same-runner-new --repetitions 10
```

The script checks the exact upstream checkout, refuses tracked modifications, adds/removes its test overlay, runs both implementations sequentially in one host environment and saves raw arrays plus source/vector provenance. `.github/workflows/same_runner_benchmark.yml` provides the same sequence on an Ubuntu runner with Go 1.25.0. These are new measurements, not the original historical wall-clock run. Their relations, compiler stacks and proof serializers differ; use the results descriptively, not as a normalized speedup claim. The historical same-runner records do not contain the instrumentation source hash, so exact recovery of that historical harness is not asserted.

For the source-reported upstream CSV context (a separate dataset), use `build_recent_work_comparison.py --zklp-csv <downloaded pinned benchmarks/m6i.xlarge/bench_ZKLP32_G16_BN254.txt> --zklp-same-runner <zklp JSON> --ours-same-runner <our JSON> --output <new comparison JSON>`.
