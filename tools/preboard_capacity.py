#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Execute independent full-population capacity and reporting-boundary oracles."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import duckdb
import pandas as pd
import yaml
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'recipes'))
from semantic.registry import register
from semantic.cases import metadata
from semantic.render import PARAMS,python_code,sql,typed_schema
from semantic.model import instant
from semantic.esql import reduce_export


def run():
    cards=yaml.safe_load((ROOT/'catalog/osms-catalog.yaml').read_text(encoding='utf-8'))['cards']
    plan=register(cards)['STD-002a'];ns={};exec(python_code(plan),ns)
    base={**metadata(plan,0),'annual_portfolio_loss':0,'risk_appetite':50000,
          'model_profile_version':'osms-reference/0.9.2','joint_scenario_set_hash':'synthetic:ordered-losses', 'currency':'EUR'}
    results=[]
    # Losses are exactly the consecutive integers 0..n-1. Oracles are closed form,
    # independent of the generated computation and its percentile functions.
    for n,p50,p90,eligible in ((99999,49999,89999,0),(100000,49999.5,89999,1),(100001,50000,90000,1)):
        rows=[dict(base,record_id=str(i),annual_portfolio_loss=i) for i in range(n)]
        expected={'draw_count':n,'p50_loss':p50,'mean_loss':p50,'p90_loss':p90,
                  'probability_above_appetite':(n-50001)/n,'reporting_eligible':eligible}
        start=time.monotonic();actual=ns['compute'](rows,**PARAMS)
        for engine,out in [('python',actual)]:
            if out['evaluation_status']!='ok' or out['outputs']!=expected:raise AssertionError((engine,n,out,expected))
            results.append({'engine':engine,'records':n,'outputs':out['outputs'],'seconds':time.monotonic()-start,'status':'pass'})
        start=time.monotonic()
        # Bulk registration avoids measuring row-at-a-time INSERT overhead.
        frame=pd.DataFrame(rows)
        for key,spec in plan['inputs'].items():
            if spec['type']=='timestamp':frame[key]=pd.to_datetime(frame[key],utc=True)
        with duckdb.connect() as con:
            con.register('source_rows',frame)
            types=typed_schema(plan,'gsql')
            con.execute('CREATE TABLE osms_input AS SELECT '+','.join('CAST('+k+' AS '+t+') AS '+k for k,t in types.items())+' FROM source_rows')
            q=sql(plan,'gsql')
            for k in PARAMS:q=q.replace(':'+k,'$'+k)
            cursor=con.execute(q,PARAMS);out=dict(zip((d[0] for d in cursor.description),cursor.fetchone()))
        if out['evaluation_status']!='ok' or any(abs(out[k]-v)>1e-10 for k,v in expected.items()):raise AssertionError(('duckdb',n,out,expected))
        results.append({'engine':'duckdb','records':n,'outputs':{k:out[k] for k in expected},'seconds':time.monotonic()-start,'status':'pass'})
    # The ES response reducer must never mistake a truncated result for this
    # reportable population. Test both sides of its separately declared 10k cap.
    cols=list(plan['inputs'])
    for n in (9999,10000,10001):
        count={'columns':[{'name':'source_rows'}],'values':[[n]]}
        records=[dict(base,record_id=str(i),annual_portfolio_loss=i) for i in range(min(n,10000))]
        rows={'columns':[{'name':k} for k in cols],'values':[[r[k] for k in cols] for r in records]}
        try:out=reduce_export(plan,count,rows,PARAMS,snapshot_hash='0'*64)
        except ValueError:
            if n<=10000:raise
            results.append({'engine':'esql_response_reducer','records':n,'expected_status':'capacity_rejected','status':'pass'});continue
        if n>10000:raise AssertionError('Truncated population accepted')
        if out['result']['outputs']['reporting_eligible']!=0:raise AssertionError('Subminimum reportable')
        results.append({'engine':'esql_response_reducer','records':n,'expected_status':'calculation_only_below_reporting_minimum','status':'pass'})
    return {'evidence_class':'synthetic_capacity','native_esql_execution':False,'plan_contract_hash':plan['contract_hash'],
            'engine_versions':{'python':sys.version,'duckdb':duckdb.__version__},
            'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),ROOT/'catalog/osms-catalog.yaml']},
            'cases':results,'passed':len(results)}

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',required=True);a=ap.parse_args()
    r=run();Path(a.out).write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8');print(r['passed'],'capacity checks passed')
