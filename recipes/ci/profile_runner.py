#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run declared calculation-input profiles, recording exact source and runtime.

Missing engines fail when requested; there is no successful native-engine skip.
The report must not be interpreted as source-adapter or pilot validation.
"""
import argparse
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile
import urllib.request
import urllib.parse
import urllib.error
import ssl
import base64

HERE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(HERE))
from portable.cases import cases
from portable.ratios import COLUMNS
PARAMS={'scope_id':'prod','period_start':'2026-06-01T00:00:00Z','period_end':'2026-07-01T00:00:00Z'}


def matches(actual,expected):
    for k,v in expected.items():
        a=actual.get(k)
        if v is None:
            if a is not None and a!='#N/A' and a!='':return False
        elif isinstance(v,str):
            if a!=v:return False
        elif a is None or isinstance(a,str) and a.startswith('#') or not math.isclose(float(a),v,rel_tol=1e-12,abs_tol=1e-9):return False
    return True


def literal(value):
    if value is None:return 'NULL'
    if isinstance(value,(int,float)) and not isinstance(value,bool):
        if not math.isfinite(value):raise ValueError('Nonfinite SQL fixture literal')
        return repr(value)
    return "'"+str(value).replace("'","''")+"'"


def native_http(engine, method, path, data=None):
    base=os.environ.get('OSMS_ES_URL','http://localhost:9200') if engine=='esql' else os.environ.get('OSMS_SPL_URL','https://localhost:8089')
    if urllib.parse.urlparse(base).hostname not in ('localhost','127.0.0.1','::1'):
        raise ValueError('This CI runner targets disposable loopback engine services')
    headers={};context=None
    if engine=='esql':
        body=json.dumps(data,allow_nan=False).encode() if data is not None else None
        headers['Content-Type']='application/json'
    else:
        body=urllib.parse.urlencode(data).encode() if data is not None else None
        user=os.environ.get('SPLUNK_USER','admin');password=os.environ.get('SPLUNK_PASSWORD','')
        headers['Authorization']='Basic '+base64.b64encode((user+':'+password).encode()).decode()
        context=ssl._create_unverified_context()  # isolated loopback test container
    req=urllib.request.Request(base+path,data=body,headers=headers,method=method)
    with urllib.request.urlopen(req,timeout=90,context=context) as response:
        if response.headers.get('Warning'):raise ValueError('Engine warning prevents a clean conformance result: '+response.headers['Warning'][:2000])
        return json.loads(response.read())


def inline_query(profile, case, engine):
    # Independent fixtures become native typed input rows, without changing an
    # index, ingestion configuration or production source. Duplicate cases use
    # two identical rows; other current fixtures have zero/one row.
    rows=case['rows'];row=rows[0] if rows else {}
    if len(rows)>1 and any(r!=row for r in rows):raise ValueError('Inline fixture only supports identical duplicates')
    values=[]
    for f in COLUMNS:
        v=row.get(f)
        if engine=='esql':
            ty='TO_DOUBLE' if f in ('numerator','denominator') else 'TO_DATETIME' if f.startswith('period_') else 'TO_STRING'
            lit='NULL' if v is None else json.dumps(v)
            values.append(f+'='+ty+'('+lit+')')
        else:
            if v is not None and f.startswith('period_'):
                from datetime import datetime
                v=datetime.fromisoformat(v.replace('Z','+00:00')).timestamp()
            values.append(f+'='+('null()' if v is None else json.dumps(v)))
    if engine=='esql':
        source='ROW '+', '.join(values)
        if len(rows)>1:source+=', duplicate_index=[0,1] | MV_EXPAND duplicate_index'
        if not rows:source+=' | WHERE false'
        q=re.sub(r'(?m)^FROM metric_inputs$',lambda _:source,profile['dialects']['esql'])
        for k,v in PARAMS.items():q=q.replace('?'+k,('TO_DATETIME('+json.dumps(v)+')' if k.startswith('period_') else json.dumps(v)))
    else:
        source='| makeresults count='+str(max(1,len(rows)))+' | eval '+', '.join(values)
        if not rows:source+=' | where 1=0'
        q=re.sub(r'(?m)^index=[^\n]+',lambda _:source,profile['dialects']['spl'])
        for k,v in PARAMS.items():
            if k.startswith('period_'):
                from datetime import datetime
                v=datetime.fromisoformat(v.replace('Z','+00:00')).timestamp()
            q=q.replace('$'+k+'$',json.dumps(v))
        q=re.sub(r'```.*?```','',q,flags=re.S).strip()
    return q


def run(profile,case,engine,folder,soffice=None):
    rows=case['rows'];dialects=profile['dialects']
    if engine in ('esql','spl'):
        q=inline_query(profile,case,engine)
        if engine=='esql':
            body=native_http(engine,'POST','/_query',{'query':q})
            if body.get('is_partial') or body.get('warnings'):raise ValueError('Incomplete/warned ES|QL query')
            if len(body.get('values',[]))!=1:raise ValueError('Expected one native ES|QL result row')
            return dict(zip([c['name'] for c in body['columns']],body['values'][0]))
        body=native_http(engine,'POST','/services/search/jobs',{'search':q,'exec_mode':'oneshot','output_mode':'json','count':'10'})
        if any(m.get('type','').upper() in ('ERROR','WARN') for m in body.get('messages',[])):raise ValueError('SPL query returned warning/error')
        results=body.get('results',[])
        if len(results)!=1:raise ValueError('Expected one native SPL result row')
        return results[0]
    if engine=='python':
        ns={};exec(dialects['py'],ns)
        return ns['compute'](rows,PARAMS['period_start'],PARAMS['period_end'],PARAMS['scope_id'])
    if engine=='duckdb':
        import duckdb
        import pandas as pd
        df=pd.DataFrame(rows,columns=COLUMNS)
        for f in COLUMNS:
            if f in ('numerator','denominator'):df[f]=df[f].astype('float64')
            elif f.startswith('period_'):df[f]=pd.to_datetime(df[f],utc=True)
            else:df[f]=df[f].astype('string')
        with duckdb.connect() as con:
            con.register('metric_inputs',df);q=dialects['gsql']
            for k in PARAMS:q=q.replace(':'+k,'$'+k)
            cur=con.execute(q,PARAMS)
            return dict(zip([d[0] for d in cur.description],cur.fetchone()))
    if engine=='postgresql':
        fields=','.join(f+' '+('double precision' if f in ('numerator','denominator') else 'timestamptz' if f.startswith('period_') else 'text') for f in COLUMNS)
        sql='BEGIN; CREATE TEMP TABLE metric_inputs ('+fields+');\n'
        if rows:sql+='INSERT INTO metric_inputs VALUES '+','.join('('+','.join(literal(row.get(f)) for f in COLUMNS)+')' for row in rows)+';\n'
        q=dialects['pg']
        for k,v in PARAMS.items():q=q.replace(':'+k,literal(v))
        sql+=q+'\nROLLBACK;'
        proc=subprocess.run(['psql','--no-psqlrc','--quiet','--csv','--tuples-only','--set','ON_ERROR_STOP=1','--command',sql],capture_output=True,text=True,check=True,timeout=30)
        results=list(csv.reader(io.StringIO(proc.stdout)))
        if len(results)!=1 or len(results[0])!=2:raise ValueError('Unexpected PostgreSQL result shape')
        return {'value':float(results[0][0]) if results[0][0] else None,'evaluation_status':results[0][1]}
    if engine in ('formulas','libreoffice'):
        import xlsx_dialect as xl
        path=str(Path(folder)/'case.xlsx');outs=xl.build_workbook(profile['excel_spec'],{'rows':rows,'params':PARAMS},path)
        got=xl.eval_formulas(path,outs) if engine=='formulas' else xl.eval_libreoffice(path,outs,soffice=soffice,user_installation=Path(folder,'lo-profile').as_uri())
        n,nv=got.get('selected_rows'),got.get('valid_rows');den=got.get('denominator')
        status='invalid_input' if got.get('parameter_valid')!=1 else 'missing_input' if n==0 else 'invalid_input' if n!=1 or nv!=1 else 'not_applicable' if den==0 else 'ok'
        return {'value':got.get('value'),'evaluation_status':status}
    raise ValueError('Unknown engine')


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--bundle',default='recipes/out')
    ap.add_argument('--engine',choices=['python','duckdb','postgresql','formulas','libreoffice','esql','spl'],required=True)
    ap.add_argument('--cards',help='Optional comma-separated subset, explicitly recorded in report')
    ap.add_argument('--report-suffix',default='',help='Filename suffix for separate positive/boundary reports')
    ap.add_argument('--case-ids',help='Optional comma-separated case subset, explicitly recorded')
    ap.add_argument('--soffice',default='soffice');a=ap.parse_args()
    source=Path(a.bundle,'execution-profiles.json');bundle=json.loads(source.read_text())
    selected=set(a.cards.split(',')) if a.cards else None
    profiles={cid:ps['canonical_quotient_v1'] for cid,ps in bundle['profiles'].items() if 'canonical_quotient_v1' in ps and (selected is None or cid in selected)}
    if selected and set(profiles)!=selected:ap.error('Requested card lacks a canonical quotient profile')
    if a.report_suffix and not re.fullmatch(r'[a-z0-9-]+',a.report_suffix):ap.error('Invalid report suffix')
    if a.engine=='esql':version=native_http('esql','GET','/')['version']['number']
    elif a.engine=='spl':version=native_http('spl','GET','/services/server/info?output_mode=json')['entry'][0]['content']['version']
    elif a.engine=='postgresql':version=subprocess.check_output(['psql','--no-psqlrc','--tuples-only','--command','SHOW server_version'],text=True,timeout=20).strip()
    elif a.engine=='libreoffice':
        with tempfile.TemporaryDirectory(prefix='osms-lo-version-') as probe:
            version=subprocess.check_output([a.soffice,'--headless','-env:UserInstallation='+Path(probe).as_uri(),'--version'],text=True,timeout=20).strip()
    elif a.engine=='python':version=platform.python_version()
    else:
        import importlib.metadata
        version=importlib.metadata.version(a.engine)
    report={'engine':a.engine,'engine_version':version,'stage':'calculation_inputs',
            'profile_bundle_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'source_files_sha256':bundle['source_files_sha256'],'requested_subset':sorted(selected) if selected else None,'requested_case_subset':a.case_ids.split(',') if a.case_ids else None,'cases':[]}
    aborted=False
    with tempfile.TemporaryDirectory(prefix='osms-profiles-') as folder:
        for cid,p in profiles.items():
            for case in cases(p['contract']):
                if a.case_ids and case['case_id'] not in a.case_ids.split(','):continue
                result={'card_id':cid,'case_id':case['case_id'],'outputs':['value','evaluation_status']}
                try:
                    actual=run(p,case,a.engine,folder,a.soffice);ok=matches(actual,case['expect'])
                    result.update(status='pass' if ok else 'fail',actual=actual,expected=case['expect'])
                except Exception as exc:
                    result.update(status='fail',error=type(exc).__name__+': '+str(exc)[:240])
                    if isinstance(exc,(subprocess.TimeoutExpired,FileNotFoundError,urllib.error.URLError)):
                        aborted=True
                report['cases'].append(result)
                if aborted:break
            if len(profiles)>20 and len(report['cases']) % 100 == 0:
                print(f'{a.engine}: {len(report["cases"])} cases evaluated',flush=True)
            if aborted:break
    if not report['cases']:ap.error('No matching test cases; refusing an empty PASS')
    failures=sum(c['status']!='pass' for c in report['cases']);report['status']='fail' if failures else 'pass'
    report['numeric_cards']=len({c['card_id'] for c in report['cases']});report['requested_cards']=len(profiles)
    report['execution_incomplete']=aborted;report['case_count']=len(report['cases']);report['failures']=failures
    path=Path(a.bundle,'profile-report-'+a.engine+('-'+a.report_suffix if a.report_suffix else '')+'.json');path.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(f'{a.engine} {version}: {report["numeric_cards"]}/{len(profiles)} requested cards, {len(report["cases"])} cases, {failures} failures; {path}')
    for c in [c for c in report['cases'] if c['status']!='pass'][:5]:print(c)
    return 1 if failures else 0

if __name__=='__main__':sys.exit(main())
