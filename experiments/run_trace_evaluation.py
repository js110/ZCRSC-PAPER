#!/usr/bin/env python3
"""Real reference trajectory replay with explicitly simulated evidence sources."""
import hashlib
import json
import math
from pathlib import Path
import numpy as np
from run_semantic_evaluation import (
    BoxND, METHODS, _new_counts, _update, _rates, _mean_ci,
    median_point, majority_center, fixed_margin, all_intersection,
    classify_subset_oracle,
)

HERE = Path(__file__).resolve().parent

def main():
    source = HERE / 'UrbanNav_TST_GT_raw.txt'
    raw = np.loadtxt(source, skiprows=2)
    lat = raw[:, 3] + raw[:, 4] / 60 + raw[:, 5] / 3600
    lon = raw[:, 6] + raw[:, 7] / 60 + raw[:, 8] / 3600
    # Local equirectangular approximation for a short urban trajectory.
    east = 6371000 * math.cos(math.radians(lat[0])) * np.radians(lon-lon[0])
    north = 6371000 * np.radians(lat-lat[0])
    x = np.rint(east-east.min()+100).astype(int)
    y = np.rint(north-north.min()+100).astype(int)
    t = np.rint(raw[:, 0]-raw[0, 0]+100).astype(int)
    points = list(zip(x.tolist(), y.tolist(), t.tolist()))
    domain = BoxND((0,0,0), (int(x.max()+100),int(y.max()+100),int(t.max()+100)))
    # Fixed task, chosen from reference-trajectory quantiles, before replay.
    policy = BoxND(tuple(int(np.quantile(v,.2)) for v in (x,y,t)),
                   tuple(int(np.quantile(v,.8)) for v in (x,y,t)))
    records = {}
    functions = dict(median_point=median_point, majority_center=majority_center,
                     fixed_margin=fixed_margin, all_intersection=all_intersection)
    for mode in ('calibrated_correlated', 'undercovered_correlated'):
        seed_rates = {m: [] for m in METHODS}
        for seed in range(30):
            rng = np.random.default_rng(31000+seed)
            counts = {m: _new_counts() for m in METHODS}
            shared = np.zeros(3)
            for point in points:
                # Bounded, temporally correlated innovations; arbitrary units
                # are replaced here by metres, metres, seconds.
                shared = np.clip(.9*shared+.1*rng.uniform(-1,1,3), -1, 1)
                boxes = []
                for i in range(4):
                    radius = np.array([int(rng.integers(8,21)),int(rng.integers(8,21)),int(rng.integers(1,4))])
                    factor = 1 if mode.startswith('calibrated') else 4
                    err = np.rint((factor*shared+rng.uniform(-.3,.3,3))*radius).astype(int)
                    center = np.asarray(point)+err
                    boxes.append(BoxND(tuple(np.maximum(0,center-radius).tolist()),
                                       tuple(np.minimum(domain.hi,center+radius).tolist())))
                truth = policy.contains(point)
                if not truth:
                    attack = policy
                else:
                    _, axis, low = min((point[a]-policy.lo[a],a,True) for a in range(3))
                    lo, hi = list(domain.lo), list(domain.hi)
                    hi[axis] = policy.lo[axis]-1
                    attack = BoxND(tuple(lo),tuple(hi))
                boxes.append(attack)
                for method, function in functions.items():
                    if method == 'fixed_margin':
                        center = np.median(np.array([(np.array(b.lo)+b.hi)/2 for b in boxes]),axis=0)
                        margin = np.array([20,20,3])
                        guard = BoxND(tuple(np.floor(center-margin).astype(int)),tuple(np.ceil(center+margin).astype(int)))
                        decision = 'robust_valid' if policy.contains_box(guard) else ('robust_invalid' if guard.intersection(policy) is None else 'ambiguous')
                    else:
                        decision = function(boxes, policy, 20)
                    _update(counts[method],decision,truth)
                decision = classify_subset_oracle(boxes,domain,policy,1,0)
                _update(counts['robust_depth'],decision,truth)
            for method in METHODS:
                seed_rates[method].append(_rates(counts[method]))
        records[mode] = {'seed_rates': seed_rates, 'aggregate': {
            m: {k:_mean_ci(row[k] for row in rows) for k in rows[0]} for m,rows in seed_rates.items()}}
    result = dict(source='UrbanNav-HK-Medium-Urban-1 reference trajectory',
                  source_url='https://github.com/IPNL-POLYU/UrbanNavDataset',
                  sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                  rows=len(points), duration_seconds=float(raw[-1,0]-raw[0,0]),
                  inside_events=sum(policy.contains(p) for p in points), seeds=30,
                  domain=dict(lo=domain.lo,hi=domain.hi), policy=dict(lo=policy.lo,hi=policy.hi),
                  evidence='simulated bounded temporally correlated errors; no measured GNSS residuals',
                  independent_unit='randomized evidence realization conditional on one fixed trajectory',
                  results=records)
    (HERE/'trace_results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='results'},indent=2))

if __name__ == '__main__':
    main()
