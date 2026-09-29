#!/usr/bin/env python3
"""Summarize matched r-budget runs and restore the manuscript's r=0 figures."""
import json
from pathlib import Path
from run_semantic_evaluation import plot_results
HERE=Path(__file__).resolve().parent

def main():
    runs=[json.loads((HERE/name).read_text()) for name in ('semantic_results.json','semantic_results_r1.json','semantic_results_r2.json')]
    rows=[]
    for key in ('calibrated_correlated__radius_4__byz_1','undercovered_correlated__radius_4__byz_1'):
        for r,run in enumerate(runs):
            # Verify shared reference class denominators for paired input seeds.
            for c,b in zip(run['seed_counts'][key]['robust_depth'],runs[0]['seed_counts'][key]['robust_depth']):
                assert (c['inside'],c['outside'])==(b['inside'],b['outside'])
            metrics=run['aggregate'][key]['robust_depth']
            rows.append(dict(condition=key,r=r,k=5-1-r,**{m:metrics[m]['mean'] for m in
                ('false_accept_rate','false_reject_rate','ambiguous_rate','evidence_failure_rate','decisive_coverage')}))
    result=dict(rows=rows,design='same seeds, event generator and policy; only r changes',
                events_per_r=64800,total_observations_including_r0=194400,
                note='r1/r2 are matched reanalyses with shared random seeds, not independent additional datasets')
    (HERE/'miscoverage_ablation.json').write_text(json.dumps(result,indent=2)+'\n')
    plot_results(runs[0],HERE)
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
