# Resource-bounded compilation sweep

Completed 15 September 2026. `plan.json` was written before data collection and contains all 32 jobs (30 unique grid configurations plus two n=5,d=2 compatibility controls), seeded order, machine summary, bounds and code hashes. `results.json` includes every outcome; `case_*.log` are unedited child-process logs. The binary is a regenerable build product and is excluded from Git.

Reproduce from the Paper A directory:

```sh
python3 experiments/run_compile_sweep.py
python3 figures/render_compile_sweep.py experiments/compile_sweep_20260915T010554Z
```

The first command creates a new timestamped run, never overwriting this dataset. Point the second command at the desired completed run. Complete R1CS counts include signatures and geometry; neither setup nor proving is executed. The depth circuit uses public k and is compiled once per n,d; k in its row identifies the paired reference, not a fixed depth constraint. n=4 subset b=2 and k=n/2 are the same configuration.

27/32 runs completed; 5 were stopped after sampled RSS exceeded 3 GiB. RSS is sampled every 50 ms, so it is an observed peak rather than exact OS high-water usage; limits can be overshot between samples. Go's 2500 MiB soft target is not an OS memory cap. No timeout occurred. Timings have one process invocation per configuration and no statistical uncertainty claim.

Six overlapping compiled counts match earlier benchmark artifacts. Separate solver regression `go test -run TestCompileSweepThresholdBinding -count=1 ./...` passed on this date, checking valid signed fixtures for k=2,3 at n=4,d=2 and rejecting threshold substitution. This is not proof-generation validation for all large cases. The experiment changes no production circuit logic.

Plot: `figures/compile_scalability.pdf`, with source CSV and manifest. Failed points are gaps, not extrapolated counts. Raw logs remain the source of truth for completed counts. Current audit checks every displayed table cell and all successful log results.
