#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run independent fixtures in installed Excel or disposable local DAX models."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

sys.path[:0]=[str(Path(__file__).resolve().parents[1])]
from portable.cases import cases
from semantic.cases import boundaries
from semantic.model import instant
from semantic_runner import equal
from incident_cases import cases as incident_cases
import xlsx_dialect as xl


def literal(v,kind):
    if v is None:return 'BLANK()'
    if kind=='timestamp':
        d=instant(v)
        return f'DATE({d.year},{d.month},{d.day})+TIME({d.hour},{d.minute},{d.second})+{d.microsecond}/86400000000.0'
    if isinstance(v,bool):return 'TRUE()' if v else 'FALSE()'
    if isinstance(v,(int,float)):return json.dumps(v,allow_nan=False)
    return '"'+str(v).replace('"','""')+'"'


def table(name,schema,rows):
    # Table constructors permit timestamp arithmetic; DATATABLE constants do
    # not permit the division needed to retain fractional-second fixtures.
    data=rows or [{}]
    values=','.join('('+','.join(literal(r.get(k),s['type']) for k,s in schema.items())+')' for r in data)
    if len(schema)==1:values=','.join(literal(r.get(next(iter(schema))),next(iter(schema.values()))['type']) for r in data)
    types={'number':'DOUBLE','boolean':'BOOLEAN','timestamp':'DATETIME','string':'STRING'}
    cols=','.join('"'+k+'",CONVERT([Value'+(str(i) if len(schema)>1 else '')+'],'+types[s['type']]+')' for i,(k,s) in enumerate(schema.items(),1))
    expression='SELECTCOLUMNS({'+values+'},'+cols+')'
    if not rows:expression='FILTER('+expression+',FALSE())'
    return {'name':name,'expression':expression,'columns':[{ 'name':k,'type':{'number':'Double','boolean':'Boolean','timestamp':'DateTime','string':'String'}[s['type']]} for k,s in schema.items()]}


def dax_request(profile,case,semantic):
    incident=profile['contract'].get('input_table')=='incidents'
    params=case['params'] if semantic or incident else {'scope_id':'prod','period_start':'2026-06-01','period_end':'2026-07-01'}
    p=profile['plan'] if semantic else profile['contract']
    schema=p['inputs'] if semantic else {} if incident else {k:{'type':'number' if k in ('numerator','denominator') else 'timestamp' if k.startswith('period_') else 'string'} for k in p['columns']}
    if incident:schema={k:{'type':'timestamp' if v=='date' else 'string'} for k,v in case['fields'].items()}
    tables=[table('Incidents' if incident else 'osms_input' if semantic else 'MetricInputs',schema,case['rows'])]
    query=profile['dialects']['dax']
    if semantic:
        names={'scope_id':'scopeId','segment_id':'segmentId','period_start':'periodStart','period_end':'periodEnd','population_complete':'populationComplete'}
        for k,v in params.items():
            query,n=re.subn(r'(?m)^VAR '+names[k]+r'=[^\n]+',lambda _: 'VAR '+names[k]+'='+literal(v,'timestamp' if k.startswith('period_') else 'string'),query)
            if n!=1:raise ValueError('Missing DAX parameter '+k)
    else:
        tables += [table('Scope',{'scope_id':{'type':'string'}},[{'scope_id':'prod'}]),
                   table('ReportingPeriod',{k:{'type':'timestamp'} for k in ('period_start','period_end')},[params])]
    return {'query':query,'tables':tables}


def execute(profile,case,engine,folder,args,semantic):
    incident=profile['contract'].get('input_table')=='incidents'
    request={'engine':engine,'response_path':str(folder/'response.json')}
    if engine=='excel':
        fixture=copy.deepcopy(case);spec=copy.deepcopy(profile['excel_spec'])
        if semantic:
            for row in fixture['rows']:
                for k,s in profile['plan']['inputs'].items():
                    if s['type']=='timestamp' and row.get(k) is not None:row[k]=instant(row[k]).isoformat()
        elif not incident:fixture['params']={'scope_id':'prod','period_start':'2026-06-01','period_end':'2026-07-01'}
        for name,col in spec.get('tabular_outputs',{}).items():
            for i in range(len(fixture['rows'])):spec['outputs'][name+'__'+str(i)]='=data!'+col+str(i+2)
        path=folder/'fixture.xlsx'
        request.update(workbook=str(path),output_rows=xl.build_workbook(spec,fixture,str(path)))
    else:request.update(dax_request(profile,case,semantic),server=args.server,tom_assembly=args.tom_assembly,adomd_assembly=args.adomd_assembly)
    path=folder/'request.json';path.write_text(json.dumps(request,ensure_ascii=False),encoding='utf-8')
    subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-File',str(Path(__file__).with_name('desktop_engine.ps1')),
                    '-RequestPath',str(path)],check=True,timeout=240,capture_output=True,text=True)
    result=json.loads((folder/'response.json').read_text(encoding='utf-8-sig'))
    if engine=='excel':
        actual=result['outputs']
        if semantic and profile['plan'].get('grouping'):
            services=[]
            for i in range(len(case['rows'])):
                key=actual.get('ranked_service_id__'+str(i))
                if key not in (None,'','#N/A',0):services.append({'business_service_id':key,
                    'service_risk_raw':actual['ranked_service_risk_raw__'+str(i)],'service_risk':actual['ranked_service_risk__'+str(i)],
                    'competition_rank':actual['competition_rank__'+str(i)]})
            actual['services']=sorted(services,key=lambda r:(-r['service_risk_raw'],r['business_service_id'])) if actual.get('service_count') not in (None,'#N/A') else None
        if not semantic and not incident:
            n,nv=actual.get('selected_rows'),actual.get('valid_rows')
            actual['evaluation_status']='invalid_input' if actual.get('parameter_valid')!=1 else 'missing_input' if n==0 else 'invalid_input' if n!=1 or nv!=1 else 'not_applicable' if actual.get('denominator')==0 else 'ok'
    else:
        rows=result['rows']
        if isinstance(rows,dict):rows=[rows]
        if semantic and profile['plan'].get('grouping'):
            status=rows[0].get('evaluation_status') if rows else 'not_applicable'
            services=[{k:r[k] for k in ('business_service_id','service_risk_raw','service_risk','competition_rank')} for r in rows if r.get('business_service_id') and status=='ok']
            actual={'services':services if status in ('ok','not_applicable') else None,'service_count':len(services) if status in ('ok','not_applicable') else None,'evaluation_status':status}
        else:
            if len(rows)!=1:raise ValueError('Expected one DAX result')
            actual=rows[0]
    return actual,result['engine_version']


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--bundle',default='recipes/out')
    ap.add_argument('--engine',required=True,choices=['excel','dax']);ap.add_argument('--cards')
    ap.add_argument('--server');ap.add_argument('--tom-assembly');ap.add_argument('--adomd-assembly');a=ap.parse_args()
    if sys.platform!='win32':ap.error('Native Windows desktop engine required; no emulated PASS')
    if a.engine=='dax' and not all((a.server,a.tom_assembly,a.adomd_assembly)):ap.error('DAX requires local server and installed TOM/ADOMD assembly paths')
    source=Path(a.bundle,'execution-profiles.json');bundle=json.loads(source.read_text(encoding='utf-8'))
    wanted=set(a.cards.split(',')) if a.cards else set(bundle['profiles'])
    if wanted-set(bundle['profiles']):ap.error('Unknown card')
    report={'engine':a.engine,'stage':'typed_calculation_profiles','profile_bundle_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'source_files_sha256':bundle['source_files_sha256'],'requested_subset':a.cards,'cases':[],'engine_version':None,'aborted':False}
    with tempfile.TemporaryDirectory(prefix='osms-desktop-') as d:
        for cid in sorted(wanted):
            ps=bundle['profiles'][cid];semantic='prepared_observations_v1' in ps
            pid='incident_snapshot_v1' if cid=='SOC-003' else 'prepared_observations_v1' if semantic else 'canonical_quotient_v1';p=ps[pid]
            fixtures=incident_cases() if cid=='SOC-003' else [c for f in p['fixtures'] for c in boundaries(p['plan'],f)] if semantic else cases(p['contract'])
            for c in fixtures:
                expected=c['expected'] if semantic else c['expect'];name=c['name'] if semantic else c['case_id']
                row={'card_id':cid,'case_id':name,'profile_id':pid,'outputs':list(expected),'status':'fail'}
                try:
                    actual,version=execute(p,c,a.engine,Path(d),a,semantic);report['engine_version']=version
                    contracts=p['plan']['output_contracts'] if semantic else p['contract']['outputs']
                    errors=[k for k,v in expected.items() if k not in actual or not equal(actual[k],v,contracts.get(k))]
                    if c.get('status') and a.engine=='dax' and actual.get('evaluation_status')!=c['status']:errors.append('evaluation_status')
                    row.update(status='fail' if errors else 'pass',failed_outputs=errors,actual=actual)
                except Exception as exc:
                    row['error']=type(exc).__name__+': '+str(exc)
                    if isinstance(exc,subprocess.CalledProcessError):row['error']+=' '+str(exc.stderr)[:2000]
                    report['aborted']=True
                report['cases'].append(row)
                if row['status']=='fail':print(cid,name,row.get('error',row.get('failed_outputs')),flush=True)
                if report['aborted']:break
            if report['aborted']:break
    report['passed']=sum(r['status']=='pass' for r in report['cases']);report['failed']=len(report['cases'])-report['passed']
    Path(a.bundle,'profile-report-desktop-'+a.engine+'.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(report['passed'],'passed;',report['failed'],'failed')
    return int(bool(report['failed']))

if __name__=='__main__':raise SystemExit(main())
