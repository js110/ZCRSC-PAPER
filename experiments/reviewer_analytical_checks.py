"""Deterministic analytical checks, NOT device or circuit benchmarks."""
import json
import math
from pathlib import Path

def poisson_binomial_tail(ps, r):
    dist = [1.0]
    for p in ps:
        out = [0.0] * (len(dist) + 1)
        for i, v in enumerate(dist):
            out[i] += v * (1-p)
            out[i+1] += v * p
        dist = out
    return sum(dist[r+1:])

def work(n, d, k):
    # Leading-order proxies with coefficients chosen as displayed in manuscript.
    # Different primitives/constants: inequality is not a constraint crossover.
    return {'n': n, 'd': d, 'k': k,
            'depth_proxy': (2*d+1)*d*n**(d+1),
            'subset_proxy': math.comb(n,k)*k*d,
            'depth_candidates_per_query': n**d}

def main():
    intervals = [(-4,4), (-2,6), (2,4)]
    feasible = [x for x in range(-4,9) if sum(a<=x<=b for a,b in intervals)>=2]
    assert feasible == list(range(-2,5))
    assert all(a<=-1<=b for a,b in intervals[:2])
    tails = [{'r':r, 'markov_bound':min(1,5*.05/(r+1)),
              'independent_exact_tail':poisson_binomial_tail([.05]*5,r)} for r in range(3)]
    assert abs(tails[0]['independent_exact_tail']-(1-.95**5))<1e-12
    rows = [work(n,d,k) for n,k in [(5,4),(20,19),(20,10),(30,15)] for d in (2,3)]
    payload = {'scope':'Analytical illustration only; no hardware or compiled-circuit measurements',
               'calibration_assumption':'Five independent Bernoulli misses with p=0.05 ONLY for exact tails',
               'calibration':tails, 'work_proxies':rows,
               'counterexample_checked':True}
    destination = Path(__file__).with_name('reviewer_analytical_checks.json')
    destination.write_text(json.dumps(payload,indent=2)+'\n')
    print(json.dumps(payload,indent=2))

if __name__ == '__main__':
    main()
