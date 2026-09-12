#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Probe actual native DAX ingestion of nonfinite values, with valid controls."""
import argparse, copy, hashlib, json, subprocess, sys, tempfile
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'recipes/ci'),str(ROOT/'recipes')]
from desktop_runner import dax_request, literal
from semantic_runner import equal

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--bundle',default='recipes/out')
    ap.add_argument('--server',required=True)
    ap.add_argument('--tom-assembly',required=True)
    ap.add_argument('--adomd-assembly',required=True)
    ap.add_argument('--out',required=True)
    a=ap.parse_args()
    if sys.platform!='win32':ap.error('Native Windows DAX is required')
    bundlepath=ROOT/a.bundle/'execution-profiles.json'
    b=json.loads(bundlepath.read_bytes())
    for name,sha in b['source_files_sha256'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=sha:raise ValueError('Stale source: '+name)
    report=dict(engine='dax',execution_kind='native_desktop',stage='native_nonfinite_input_probes',
      started_at=datetime.now(timezone.utc).isoformat(),
      profile_bundle_sha256=hashlib.sha256(bundlepath.read_bytes()).hexdigest(),
      source_files_sha256=b['source_files_sha256'],
      probe_source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in [Path(__file__),ROOT/'tools/native_dax_input_probe.ps1']},
      records=[])
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    kinds=[('control',None),('nan_text','NaN'),('positive_infinity_text','Infinity'),
           ('negative_infinity_text','-Infinity'),('nan_native_expression','0.0/0.0'),
           ('positive_infinity_native_expression','1.0/0.0'),
           ('negative_infinity_native_expression','-1.0/0.0')]
    with tempfile.TemporaryDirectory(prefix='osms-dax-input-') as tmp:
        folder=Path(tmp)
        for cid in ['STD-068','STD-069','STD-075']:
            p=b['profiles'][cid]['prepared_observations_v1']
            field=next(k for k,v in p['plan']['inputs'].items() if v['type']=='number')
            for kind,value in kinds:
                case=copy.deepcopy(p['fixtures'][0])
                if kind.endswith('_text'):case['rows'][0][field]=value
                req=dict(engine='dax',server=a.server,tom_assembly=a.tom_assembly,
                    adomd_assembly=a.adomd_assembly,response_path=str(folder/'engine-result.json'),
                    **dax_request(p,case,True))
                if kind.endswith('_native_expression'):
                    schema=p['plan']['inputs']
                    values=','.join('('+','.join(value if k==field and i==0 else literal(row.get(k),s['type'])
                        for k,s in schema.items())+')' for i,row in enumerate(case['rows']))
                    types={'number':'DOUBLE','boolean':'BOOLEAN','timestamp':'DATETIME','string':'STRING'}
                    columns=','.join('"'+k+'",CONVERT([Value'+str(i)+'],'+types[s['type']]+')'
                                     for i,(k,s) in enumerate(schema.items(),1))
                    req['tables'][0]['expression']='SELECTCOLUMNS({'+values+'},'+columns+')'
                requestpath=folder/'request.json'
                requestpath.write_bytes(json.dumps(req,ensure_ascii=False).encode())
                diagnostic=folder/'probe-result.json'
                run=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-File',
                    str(ROOT/'tools/native_dax_input_probe.ps1'),'-RequestPath',str(requestpath),
                    '-OutPath',str(diagnostic)],capture_output=True,text=True,timeout=150)
                if run.returncode:raise RuntimeError(run.stderr)
                raw=json.loads(diagnostic.read_text(encoding='utf-8-sig'))
                row=dict(card_id=cid,input_field=field,input_kind=kind,input_expression_or_text=value,
                    fixture=case,model_table=req['tables'][0],
                    query_sha256=hashlib.sha256(req['query'].encode()).hexdigest(),native=raw,status='fail')
                rows=raw.get('result',{}).get('rows',[])
                if isinstance(rows,dict):rows=[rows]
                if kind=='control':
                    if raw['outcome']=='evaluated' and len(rows)==1 and all(
                        k in rows[0] and equal(rows[0][k],v,p['plan']['output_contracts'].get(k))
                        for k,v in case['expected'].items()):
                        row['status']='pass'
                    else:raise RuntimeError('Native valid control failed: '+json.dumps(raw))
                elif raw['outcome'] in ('native_model_input_rejected','native_model_input_rejected_at_query'):
                    row['status']='pass'
                elif raw['outcome']=='evaluated' and len(rows)==1 and rows[0].get('value') is None and rows[0].get('evaluation_status')=='invalid_input':
                    row['status']='pass'
                report['records'].append(row)
                print(cid,kind,row['status'],raw['outcome'],flush=True)
                out.write_bytes((json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode())
    report.update(completed_at=datetime.now(timezone.utc).isoformat(),
        passed=sum(x['status']=='pass' for x in report['records']))
    report['failed']=len(report['records'])-report['passed']
    out.write_bytes((json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode())
    return int(report['failed'] or len(report['records'])!=21)

if __name__=='__main__':raise SystemExit(main())
