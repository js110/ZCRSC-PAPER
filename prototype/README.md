# Robust-depth reference kernel

This directory contains the exact, non-cryptographic reference semantics for
Paper A. Coordinates are quantized integers and evidence regions are inclusive
axis-aligned boxes.

Run the tests locally:

```bash
cd /Users/jiangsheng/Desktop/IEEE/revision_vehcom/paper_a/prototype
python3 -m unittest -v test_robust_depth.py
```

The implementation evaluates Cartesian products of clipped lower endpoints.
For fixed dimension `d`, this uses at most `O(n^(d+1))` primitive comparisons
per depth query, instead of enumerating `C(n, f+r)` surviving-source subsets.
The native subset oracle computes the same decision and is cheaper for small
omission budgets. Native tests compare both classifiers and exhaustive grids.

`zkdepth/` contains real Groth16/BN254 implementations of both geometries, with
in-circuit twisted-Edwards EdDSA/MiMC verification (not Ed25519). Run:

```bash
cd zkdepth
GOCACHE=/tmp/pcvcs-paper-a-go-cache go test -v ./...
GOCACHE=/tmp/pcvcs-paper-a-go-cache go run ./cmd/bench --geometry subset --n 4 --d 3 --repetitions 30
```

The depth backend allows a public k; the subset backend fixes k=n-1 in the
benchmark (the circuit exposes a compile-time SubsetThreshold). The verifier
must authorize the matching circuit key, roster, threshold and task statement.
This is a research prototype, not audited deployment software. Context digest
validation, physical source enrollment, data calibration, delivery and replay
storage are deployment responsibilities absent from the microbenchmark.

The separate `gateway.go` harness implements configured task snapshots, report
and challenge binding, and atomic in-process challenge consumption. Run its
integration test with `go test -count=1 -race -run TestGatewayBoundReportAndReplay
-v ./...`. The four genuine decision proofs all consume their challenges; only
the valid class makes a report eligible. All twelve mismatched proof/code pairs,
missing proofs, substituted reports and replayed challenges are rejected. Failed
proof attempts do not consume the pending challenge. This does not supply durable
or distributed storage, physical calibration or vehicle-level deduplication.
