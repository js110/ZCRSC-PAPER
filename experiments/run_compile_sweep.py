"""Bounded, seeded circuit compilation sweep; never estimates missing counts."""
import hashlib, json, os, platform, random, subprocess, time
from datetime import datetime, timezone
from pathlib import Path
import psutil

ROOT=Path(__file__).resolve().parents[1]
MODULE=ROOT/'prototype/zkdepth'
def main():
    out=ROOT/'experiments'/('compile_sweep_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    out.mkdir()
    binary=out/'compilebench'
    subprocess.run(['go','build','-o',str(binary),'./cmd/compilebench'],cwd=MODULE,check=True)
    jobs=[]
    for d in (2,3):
        for n in (4,8,12,16):
            jobs.append(dict(n=n,d=d,k=n-1,backend='depth'))
            for k in sorted({n-1,n-2,n//2}):
                jobs.append(dict(n=n,d=d,k=k,backend='subset'))
    # Replay a published small-case count as a compatibility control.
    jobs += [dict(n=5,d=2,k=4,backend=b) for b in ('depth','subset')]
    random.Random(20260915).shuffle(jobs)
    plan=dict(created_utc=datetime.now(timezone.utc).isoformat(),seed=20260915,jobs=jobs,
      timeout_seconds=30,rss_cap_bytes=3*1024**3,poll_seconds=.05,
      repetitions=1,scope='Full R1CS compilation only; times descriptive, no setup/proving',
      host=platform.platform(),cpu=platform.processor(),physical_memory_bytes=psutil.virtual_memory().total,
      sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
               for p in [MODULE/'circuit.go',MODULE/'go.mod',MODULE/'go.sum',MODULE/'cmd/compilebench/main.go',Path(__file__)]})
    (out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    print('OUTPUT',out,flush=True)
    results=[]
    for i,job in enumerate(jobs):
        log=out/f'case_{i:02d}.log'
        cmd=[str(binary)]+[v for key,val in job.items() for v in ('--'+key,str(val))]
        start=time.monotonic(); peak=0; status='ok'
        with log.open('w') as stream:
            p=subprocess.Popen(cmd,stdout=stream,stderr=subprocess.STDOUT,env={**os.environ,'GOMEMLIMIT':'2500MiB'})
            proc=psutil.Process(p.pid)
            while p.poll() is None:
                try: peak=max(peak,proc.memory_info().rss)
                except psutil.NoSuchProcess: pass
                if peak>plan['rss_cap_bytes']: status='rss_limit'; p.kill(); break
                if time.monotonic()-start>plan['timeout_seconds']: status='timeout'; p.kill(); break
                time.sleep(.05)
            rc=p.wait()
        row={**job,'status':status,'returncode':rc,'peak_sampled_rss_bytes':peak,
             'wall_seconds':time.monotonic()-start,'log':log.name}
        lines=[s for s in log.read_text().splitlines() if s.startswith('RESULT_JSON:')]
        if status=='ok' and rc==0 and len(lines)==1: row.update(json.loads(lines[0][12:]))
        elif status=='ok': row['status']='error'
        results.append(row)
        (out/'results.json').write_text(json.dumps(results,indent=2)+'\n')
        print(i+1,len(jobs),job,row['status'],row.get('constraints'),flush=True)
    assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in plan['sources'].items())
    print('COMPLETE',out,flush=True)

if __name__=='__main__': main()
