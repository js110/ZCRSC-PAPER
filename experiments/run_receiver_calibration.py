#!/usr/bin/env python3
"""Retrospective, single-receiver diagnostic; see calibration_protocol.md."""
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
COMMIT = 'e9e4c6a4ded5dc7f2813265a76a56b280f714a3f'
BASE = f'https://raw.githubusercontent.com/weisongwen/GraphGNSSLib/{COMMIT}/global_fusion/dataset/gps_solution_TST2/'


def ecef(lat, lon, height):
    lat, lon = math.radians(lat), math.radians(lon)
    a, inv_f = 6378137.0, 298.257223563
    f = 1 / inv_f
    e2 = f * (2 - f)
    n = a / math.sqrt(1 - e2 * math.sin(lat)**2)
    return ((n + height)*math.cos(lat)*math.cos(lon),
            (n + height)*math.cos(lat)*math.sin(lon),
            (n*(1-e2) + height)*math.sin(lat))


def horizontal_residual(estimate, reference):
    delta = [x-y for x, y in zip(ecef(*estimate), ecef(*reference))]
    lat, lon = map(math.radians, reference[:2])
    east = -math.sin(lon)*delta[0] + math.cos(lon)*delta[1]
    north = (-math.sin(lat)*math.cos(lon)*delta[0]
             - math.sin(lat)*math.sin(lon)*delta[1] + math.cos(lat)*delta[2])
    return east, north


def unique_insert(data, key, value):
    if key in data:
        raise ValueError(f'duplicate epoch: {key}')
    if not all(math.isfinite(x) for x in value):
        raise ValueError('nonfinite input')
    data[key] = value


def load_data(folder):
    truth, solution, headers = {}, {}, []
    for row in csv.reader((folder/'groundTruth_TST.csv').read_text().splitlines()):
        values = list(map(float, row))
        if len(values) != 5 or values[0] != values[1]:
            raise ValueError('unexpected reference format')
        # First reference field repeats seconds, not GPS week.
        unique_insert(truth, values[1], values[2:])
    for line in (folder/'rtklibResult.pos').read_text().splitlines():
        if line.startswith('%'):
            headers.append(line)
            continue
        if not line.strip():
            continue
        values = list(map(float, next(csv.reader([line]))))
        if len(values) != 15 or values[0] != 2108:
            raise ValueError('unexpected POS format or GPS week')
        if values[7] <= 0 or values[8] <= 0:
            raise ValueError('nonpositive horizontal standard deviation')
        unique_insert(solution, values[1], values[2:])
    if not any('solution  : combined' in h for h in headers):
        raise ValueError('processing mode differs from analysis protocol')
    matched = []
    for second in sorted(truth.keys() & solution.keys()):
        sol = solution[second]
        east, north = horizontal_residual(sol[:3], truth[second])
        matched.append(dict(gps_second=second, east_m=east, north_m=north,
                            horizontal_m=math.hypot(east, north),
                            score_m=max(abs(east), abs(north)),
                            q=int(sol[3]), sdn_m=sol[5], sde_m=sol[6]))
    return truth, solution, headers, matched


def radius_order_statistic(scores, alpha=.05):
    rank = math.ceil((len(scores)+1)*(1-alpha))
    if not 1 <= rank <= len(scores):
        raise ValueError('insufficient calibration sample for selected rank')
    return sorted(scores)[rank-1], rank


def chronological_split(rows, gap=10):
    middle = len(rows)//2
    if middle < 1 or middle+gap >= len(rows):
        raise ValueError('insufficient rows for split')
    return rows[:middle], rows[middle:middle+gap], rows[middle+gap:]


def describe(rows, radius):
    errors = sorted(row['horizontal_m'] for row in rows)
    receiver = sum(abs(r['east_m']) <= 3*r['sde_m'] and
                   abs(r['north_m']) <= 3*r['sdn_m'] for r in rows)
    empirical = sum(r['score_m'] <= radius for r in rows)
    return dict(n=len(rows), start_gps_second=rows[0]['gps_second'],
                end_gps_second=rows[-1]['gps_second'],
                q_counts=dict(sorted(Counter(r['q'] for r in rows).items())),
                receiver_3sigma_contained=receiver,
                receiver_3sigma_coverage=receiver/len(rows),
                calibrated_square_contained=empirical,
                calibrated_square_coverage=empirical/len(rows),
                horizontal_median_m=(errors[(len(errors)-1)//2]+errors[len(errors)//2])/2,
                horizontal_p95_nearest_rank_m=errors[math.ceil(.95*len(errors))-1],
                horizontal_max_m=errors[-1])


def main():
    folder = ROOT/'graphgnss_tst2'
    truth, solution, headers, rows = load_data(folder)
    calibration, gap, evaluation = chronological_split(rows)
    radius, rank = radius_order_statistic([r['score_m'] for r in calibration])
    sources = [dict(filename=name, url=BASE+name,
                    sha256=hashlib.sha256((folder/name).read_bytes()).hexdigest())
               for name in ('groundTruth_TST.csv', 'rtklibResult.pos')]
    result = dict(scope='exploratory retrospective static single-receiver diagnostic',
                  commit=COMMIT, sources=sources, pos_headers=headers,
                  protocol_sha256=hashlib.sha256((ROOT/'calibration_protocol.md').read_bytes()).hexdigest(),
                  source_reference_rows=len(truth), source_solution_rows=len(solution),
                  unique_reference_positions=len(set(tuple(x) for x in truth.values())),
                  matched_rows=len(rows), unmatched_reference_rows=len(truth)-len(rows),
                  unmatched_solution_rows=len(solution)-len(rows), gap_rows=len(gap),
                  alpha_recipe=.05, calibration_rank=rank, radius_m=radius,
                  calibration=describe(calibration, radius), evaluation=describe(evaluation, radius),
                  independent_trials=False, online_causal_evaluation=False,
                  multisource_calibration=False, redistribution_permission='unverified')
    (ROOT/'receiver_calibration.json').write_text(json.dumps(result, indent=2)+'\n')
    with (ROOT/'receiver_residuals.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['split']+list(rows[0]))
        writer.writeheader()
        for label, subset in (('calibration', calibration), ('gap', gap), ('evaluation', evaluation)):
            writer.writerows(dict(split=label, **row) for row in subset)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
