#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Functional conformance on a disposable, loopback Kusto query engine.

No production ingestion or performance benchmarks. Expected values come from
the same independent fixtures used by the other engines, never from KQL itself.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import urllib.parse
import urllib.request
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from portable.cases import cases
from semantic.cases import boundaries
from semantic.model import instant
from semantic_runner import equal


def request(base, query, database=None, management=False):
    if urllib.parse.urlparse(base).hostname not in ('localhost','127.0.0.1','::1'):
        raise ValueError('Disposable loopback emulator required')
    body = {'csl': query, 'properties': json.dumps({'Options': {'notruncation': True}})}
    if database:
        body['db'] = database
    endpoint = '/v1/rest/mgmt' if management else '/v2/rest/query'
    req = urllib.request.Request(base+endpoint, data=json.dumps(body).encode(),
                                 headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req, timeout=90) as response:
        if response.headers.get('Warning'):
            raise ValueError('Engine warning')
        result = json.load(response)
    if isinstance(result, dict):
        if result.get('error') or result.get('Exceptions'):
            raise ValueError('Kusto execution error: '+json.dumps(result)[:1500])
        return result
    if not isinstance(result, list):
        raise ValueError('Invalid Kusto response')
    completion = [f for f in result if f.get('FrameType')=='DataSetCompletion']
    if len(completion)!=1 or completion[0].get('HasErrors') or completion[0].get('Cancelled'):
        raise ValueError('Incomplete/failed Kusto result: '+json.dumps(completion))
    tables = [f for f in result if f.get('FrameType')=='DataTable' and f.get('TableKind')=='PrimaryResult']
    if len(tables)!=1:
        raise ValueError('Expected one primary result table')
    names = [c['ColumnName'] for c in tables[0]['Columns']]
    if len(set(names))!=len(names):
        raise ValueError('Duplicate result columns')
    return [dict(zip(names, row)) for row in tables[0]['Rows']]


def literal(value, kind):
    if value is None:
        return {'string':'""','timestamp':'datetime(null)','number':'real(null)',
                'boolean':'bool(null)'}[kind]
    if kind=='timestamp':
        return 'datetime('+instant(value).isoformat()+')'
    if kind=='number':
        return 'real('+json.dumps(value, allow_nan=False)+')'
    return json.dumps(value, ensure_ascii=False)


def inline(profile, fixture, semantic):
    contract = profile['plan'] if semantic else profile['contract']
    if semantic:
        inputs = contract['inputs']
        table = 'osms_input'
        params = fixture['params']
    else:
        inputs = {k:{'type':'number' if k in ('numerator','denominator') else
                         'timestamp' if k.startswith('period_') else 'string'}
                  for k in contract['columns']}
        table = 'metric_inputs'
        params = {'period_start':'2026-06-01','period_end':'2026-07-01','scope_id':'prod'}
    schema = ','.join(k+':'+{'number':'real','timestamp':'datetime','boolean':'bool','string':'string'}[s['type']]
                      for k,s in inputs.items())
    values = ','.join(literal(row.get(k),s['type']) for row in fixture['rows'] for k,s in inputs.items())
    query = profile['dialects']['kql']
    bindings = ({k+'_parameter':(v, 'timestamp' if k.startswith('period_') else 'boolean' if k=='population_complete' else 'string')
                 for k,v in params.items()} if semantic else
                {'p_start':(params['period_start'],'timestamp'), 'p_end':(params['period_end'],'timestamp'),
                 'scope':(params['scope_id'],'string')})
    for key,(value,kind) in bindings.items():
        query, n = re.subn(r'\blet\s+'+key+r'\s*=\s*[^;]+;',
                          lambda _: 'let '+key+'='+literal(value,kind)+';', query)
        if n!=1:
            raise ValueError('Missing/duplicate query parameter '+key)
    return 'let '+table+'=datatable('+schema+')['+values+'];\n'+query


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--bundle',default='recipes/out');ap.add_argument('--url',default='http://localhost:8080')
    ap.add_argument('--cards');a=ap.parse_args()
    path=Path(a.bundle,'execution-profiles.json');bundle=json.loads(path.read_text(encoding='utf-8'))
    version=request(a.url,'.show version',management=True)
    db='osms_'+uuid.uuid4().hex
    request(a.url,'.create database '+db+' persist (@"/kustodata/'+db+'/md", @"/kustodata/'+db+'/data")',management=True)
    wanted=set(a.cards.split(',')) if a.cards else set(bundle['profiles'])-{'SOC-003'}
    if wanted-set(bundle['profiles']) or 'SOC-003' in wanted:
        ap.error('This runner covers canonical and prepared-observation profiles; SOC-003 is separate')
    report={'engine':'kusto','engine_version':json.dumps(version,sort_keys=True),'stage':'typed_calculation_profiles',
            'image_digest':os.environ.get('OSMS_KUSTO_IMAGE_DIGEST'),
            'profile_bundle_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'source_files_sha256':bundle['source_files_sha256'],'requested_subset':a.cards,'cases':[]}
    for cid in sorted(wanted):
        ps=bundle['profiles'][cid];semantic='prepared_observations_v1' in ps
        pid='prepared_observations_v1' if semantic else 'canonical_quotient_v1';p=ps[pid]
        fixtures=[c for f in p['fixtures'] for c in boundaries(p['plan'],f)] if semantic else cases(p['contract'])
        for c in fixtures:
            expected=c['expected'] if semantic else c['expect'];name=c['name'] if semantic else c['case_id']
            row={'card_id':cid,'profile_id':pid,'case_id':name,'outputs':list(expected),'status':'fail'}
            try:
                result=request(a.url,inline(p,c,semantic),db)
                if len(result)!=1:raise ValueError('Expected exactly one result row')
                actual=result[0]
                contracts=p['plan']['output_contracts'] if semantic else p['contract']['outputs']
                failed=[k for k,v in expected.items() if k not in actual or not equal(actual[k],v,contracts.get(k))]
                status=c.get('status') if semantic else None
                if status and actual.get('evaluation_status')!=status:failed.append('evaluation_status')
                row.update(status='fail' if failed else 'pass',failed_outputs=failed,actual=actual)
            except Exception as exc:
                row['error']=type(exc).__name__+': '+str(exc)
                if hasattr(exc,'read'):row['error']+=' '+exc.read().decode(errors='replace')[:2000]
            report['cases'].append(row)
            if row['status']=='fail':print(cid,name,row.get('error',row.get('failed_outputs')),flush=True)
    report['passed']=sum(r['status']=='pass' for r in report['cases']);report['failed']=len(report['cases'])-report['passed']
    Path(a.bundle,'profile-report-kusto.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Kusto:',report['passed'],'passed;',report['failed'],'failed',flush=True)
    return int(bool(report['failed']))

if __name__=='__main__':raise SystemExit(main())
