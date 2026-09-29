# Exploratory single-receiver residual diagnostic

Analysis choices recorded on 2026-09-05 before computing residual summaries.
Discovery already inspected the reference file and the first solution rows; this
is an exploratory protocol, not prospective registration or a blinded study.

Source: Weisong Wen's GraphGNSSLib, commit
`e9e4c6a4ded5dc7f2813265a76a56b280f714a3f`, directory
`global_fusion/dataset/gps_solution_TST2`.
Use `groundTruth_TST.csv` and `rtklibResult.pos` without editing source bytes.
Record URLs, hashes, headers and row counts in the result JSON. Do not assume
that the software license establishes redistribution rights for the data.

The reference has a constant position and GPS seconds of week in column two.
Column one repeats these seconds and is NOT a GPS week. The POS header states
week 2108, WGS84 ellipsoidal coordinates, RTKLIB 2.4.2, kinematic/combined mode.
Match exact seconds within week 2108, reject duplicate epochs, do not interpolate
or extrapolate the short reference interval. Retain all available solution flags.

Convert both positions to WGS84 ECEF, then project their difference onto east
and north at the reference location. Analyze horizontal error only: vertical
reference provenance and antenna-height conventions have not been established.
No fitted translation, rotation, scale, bias subtraction or quality filtering.

Sort matched epochs. Use the first floor(N/2) as calibration, skip the next ten
matched epochs, and retain the remainder as evaluation. These are retrospective
chronological subsets of an already combined solution; its backwards processing
may use later raw observations, so this is NOT a causal deployment evaluation.

Compare (a) the receiver's axis-wise three-standard-deviation rectangle using
sdn/sde, with no asserted nominal simultaneous coverage, and (b) a fixed square
whose radius is calibration order statistic ceil((m+1)*0.95) of max(|east|,|north|).
This familiar order-statistic rule is a descriptive calibration recipe here,
not a claimed distribution-free guarantee: serial dependence, a single short
sequence and combined processing invalidate an unqualified exchangeability claim.
If the rank exceeds calibration size, fail rather than silently change the rule.

Report exact contained/total counts, radius, horizontal error quantiles, solution
flag counts and unmatched rows. Do not calculate iid binomial confidence intervals
or treat epochs as independent trials. Do not duplicate this receiver into several
issuers or run an apparent multisource security experiment from those duplicates.
No signatures, timestamps with measured uncertainty, or vehicle-motion validation
are supplied by this diagnostic. No classifier or proof timing is inferred.
