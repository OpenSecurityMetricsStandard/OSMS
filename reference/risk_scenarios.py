# SPDX-License-Identifier: MIT
"""Reproducible synthetic compound-Poisson annual loss benchmark (not pilot data)."""
import argparse, hashlib, json, math, platform
from pathlib import Path
import numpy as np

VERSION='compound-poisson/1'

def generate(profile):
    if profile.get('model_version')!=VERSION:raise ValueError('Unknown model version')
    if profile.get('numpy_version')!=np.__version__:raise ValueError('Restore the pinned NumPy runtime')
    if profile.get('bit_generator')!='PCG64':raise ValueError('Unsupported PRNG')
    n=profile.get('iterations');seed=profile.get('seed')
    if type(n) is not int or not 100000<=n<=1000000:raise ValueError('Require 100000..1000000 annual draws')
    if type(seed) is not int or not 0<=seed<2**64:raise ValueError('Invalid seed')
    if profile.get('horizon')!='year' or profile.get('currency')!='EUR':raise ValueError('Explicit benchmark units required')
    if profile.get('control_credit_policy')!='residual_losses_no_further_reduction':raise ValueError('Ambiguous control credit')
    dependence=profile.get('dependence')
    if dependence not in ('independent','shared_events_and_severity'):raise ValueError('Unknown dependence')
    scenarios=profile.get('scenarios',[]);ids=[s.get('id') for s in scenarios]
    if not ids or any(not isinstance(i,str) or not i.strip() for i in ids) or len(ids)!=len(set(ids)):raise ValueError('Unique scenario IDs required')
    def finite(x,lo,hi):return type(x) in (int,float) and math.isfinite(x) and lo<=x<=hi
    for s in scenarios:
        if not finite(s.get('annual_frequency'),0,20):raise ValueError('Invalid Poisson frequency')
        if s.get('severity') not in ('constant','pareto'):raise ValueError('Unknown severity distribution')
        if not finite(s.get('scale_eur'),0,1e9):raise ValueError('Invalid severity scale')
        if s['severity']=='pareto' and not finite(s.get('shape'),1.01,20):raise ValueError('Pareto shape must exceed one')
    parameters=[{k:v for k,v in s.items() if k!='id'} for s in scenarios]
    if dependence=='shared_events_and_severity' and any(s!=parameters[0] for s in parameters):raise ValueError('Shared benchmark requires identical marginal parameters')
    streams=np.random.SeedSequence(seed).spawn(len(scenarios))
    losses=[]
    for i,s in enumerate(scenarios):
        if i and dependence=='shared_events_and_severity':losses.append(losses[0].copy());continue
        rng=np.random.Generator(np.random.PCG64(streams[i]))
        count=rng.poisson(s['annual_frequency'],n)
        if s['severity']=='constant':annual=count.astype(float)*s['scale_eur']
        else:
            # NumPy pareto is Lomax; +1 gives Type I severity with minimum scale.
            severity=(rng.pareto(s['shape'],int(count.sum()))+1)*s['scale_eur']
            annual=np.bincount(np.repeat(np.arange(n),count),weights=severity,minlength=n)
        losses.append(annual)
    matrix=np.column_stack(losses);totals=matrix.sum(axis=1)
    if not np.isfinite(matrix).all():raise ValueError('Nonfinite model output')
    ordered=np.sort(totals);appetite=profile.get('risk_appetite_eur')
    if not finite(appetite,0,1e15):raise ValueError('Invalid appetite')
    digest=hashlib.sha256(matrix.astype('<f8').tobytes()).hexdigest()
    return {'synthetic':True,'model_version':VERSION,'numpy_version':np.__version__,
        'python_version':platform.python_version(),'scenario_ids':ids,'iterations':n,
        'profile_sha256':hashlib.sha256(json.dumps(profile,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
        'joint_draws_float64_le_sha256':digest,'unit':'EUR/year',
        'outputs':{'mean':math.fsum(totals)/n,'p50':float((ordered[(n-1)//2]+ordered[n//2])/2),
          'p90':float(ordered[math.ceil(.9*n)-1]),'probability_exceeding_appetite':int((totals>appetite).sum())/n,
          'zero_event_draws':int((totals==0).sum()),'maximum':float(ordered[-1])}}

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--profiles',default=str(Path(__file__).with_name('risk-scenarios.json')));ap.add_argument('--out',required=True);a=ap.parse_args()
    profiles=json.loads(Path(a.profiles).read_text())['profiles']
    Path(a.out).write_text(json.dumps({p['profile_id']:generate(p) for p in profiles},indent=2)+'\n')
