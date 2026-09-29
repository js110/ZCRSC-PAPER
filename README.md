# ZCRSC-PAPER

Reproducibility repository for the manuscript **Zero-Knowledge Certification of Robust Spacetime Compliance under Byzantine Evidence for Vehicular Crowdsensing**.

This repository contains the implementation, experiment scripts, archived result records, and result-figure generation material used by the paper. The manuscript source and JISA submission files remain in [js110/Apaper](https://github.com/js110/Apaper).

## Contents

- `prototype/`: Go/gnark implementation of the signed-box robust-compliance circuits, gateway, tests, and point-ZK lower-bound baseline.
- `experiments/`: synthetic semantics, UrbanNav/receiver diagnostics, cryptographic benchmark records, and analysis scripts.
- `figures/`: scripts, publication plotting configuration, derived data, and generated result figures used by the manuscript.
- `requirements.txt`: direct Python dependencies used by the experiment/plotting pipeline.

## Scope

The code implements the provisioned evidence-certificate layer evaluated in the manuscript. It is not an end-to-end vehicular crowdsensing platform and does not provide participant recruitment, incentives, anonymous networking, dynamic roster management, or field calibration.

## Reproducibility note

Third-party datasets and upstream reference implementations retain their own licenses and distribution terms. Where redistribution permission is not established, this repository keeps derived records, hashes, and scripts but does not claim ownership of the upstream data.
