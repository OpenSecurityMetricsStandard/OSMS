#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run independent 119-card examples and rejection cases on named engines."""
import argparse,copy,csv,hashlib,importlib.metadata,io,json,math,platform,re,subprocess,sys,tempfile,uuid
import urllib.error
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from semantic.cases import boundaries
from semantic.check import duckdb_compute
from semantic.model import instant
from semantic.render import literal,typed_schema

def equal(actual,expected,contract=None):
    if expected is None:return actual is None or actual in ('#N/A','')
    if isinstance(expected,dict):return isinstance(actual,dict) and all(k in actual and equal(actual[k],v,(contract or {}).get(k)) for k,v in expected.items())
    if isinstance(expected,list):
        spec=(contract or {}).get('items',{})
        item_contracts={k:({'absolute_tolerance':0,'relative_tolerance':0} if v=='integer' else {}) for k,v in spec.items()}
        return isinstance(actual,list) and len(actual)==len(expected) and all(equal(a,b,item_contracts) for a,b in zip(actual,expected))
    if isinstance(expected,(int,float)):
        try:
            value=float(actual);c=contract or {}
            return math.isfinite(value) and abs(value-expected)<=max(c.get('absolute_tolerance',1e-8),abs(expected)*c.get('relative_tolerance',1e-12))
        except (ValueError,TypeError):return False
    return actual==expected

def run(profile,case,engine,folder,soffice='soffice'):
    p=profile['plan'];rows=case['rows'];params=case['params']
    if engine=='python':
        ns={};exec(profile['dialects']['py'],ns)
        return ns['compute'](rows,**params)
    if engine=='duckdb':return duckdb_compute(p,rows,params)
    if engine in ('spl','esql'):
        from profile_runner import native_http
        if engine=='spl':
            values=[]
            for k,s in p['inputs'].items():
                terms=[]
                for i,row in enumerate(rows,1):
                    v=row.get(k)
                    if v is not None and s['type']=='timestamp':v=instant(v).timestamp()
                    if isinstance(v,bool):v=int(v)
                    terms += ['fixture_row_number='+str(i),'null()' if v is None else json.dumps(v)]
                values.append(k+'=case('+','.join(terms+['true()','null()'])+')')
            source='| makeresults count='+str(max(1,len(rows)))+' | streamstats count as fixture_row_number | eval '+','.join(values)
            if not rows:source+=' | where 1=0'
            query=re.sub(r'```.*?```','',profile['dialects']['spl'],flags=re.S)
            query=re.sub(r'(?m)^index=osms_input[^\n]*',lambda _:source,query).strip()
            for k,v in params.items():
                if k in ('period_start','period_end'):v=instant(v).timestamp()
                if isinstance(v,bool):v=int(v)
                query=query.replace('$'+k+'$',json.dumps(v))
            response=native_http('spl','POST','/services/search/jobs',{'search':query,'exec_mode':'oneshot','output_mode':'json','count':'10001'})
            if any(m.get('type','').upper() in ('ERROR','WARN','FATAL') for m in response.get('messages',[])):raise ValueError('SPL warning/error: '+json.dumps(response.get('messages'))[:2000])
            result=response.get('results',[])
            if p.get('grouping'):
                status=result[0].get('evaluation_status') if result else 'not_applicable'
                services=[{k:(r[k] if k=='business_service_id' else float(r[k])) for k in ['business_service_id','service_risk_raw','service_risk','competition_rank']} for r in result if r.get('business_service_id') and status=='ok']
                return {'evaluation_status':status,'outputs':{'services':services if status in ('ok','not_applicable') else None,'service_count':len(services) if status in ('ok','not_applicable') else None}}
            if len(result)!=1:raise ValueError('Expected one SPL result row: '+json.dumps(response)[:2000])
            actual=result[0]
            # SPL JSON omits null fields. Decode the explicit recipe transport
            # marker while still rejecting genuinely absent declared outputs.
            actual={k:(None if v=='__OSMS_NULL__' and k in p['outputs'] else v) for k,v in actual.items()}
            return {'evaluation_status':actual.pop('evaluation_status'),'outputs':actual}
        from semantic.esql import reduce_export
        # Only the explicitly selected ES test runner creates disposable fixture
        # indexes. A random name and successful create are required before cleanup.
        index='osms-semantic-fixture-'+uuid.uuid4().hex
        mapping={k:{'type':('date' if k in ('period_start','period_end') else 'keyword') if s['type']=='timestamp' else {'number':'double','string':'keyword','boolean':'boolean'}[s['type']]} for k,s in p['inputs'].items()}
        native_http('esql','PUT','/'+index,{'mappings':{'dynamic':'strict','properties':mapping}})
        try:
            for i,row in enumerate(rows):native_http('esql','PUT','/'+index+'/_doc/'+str(i),row)
            native_http('esql','POST','/'+index+'/_refresh')
            responses={}
            for kind,query in profile['esql_protocol']['queries'].items():
                query=query.replace('FROM osms_input','FROM '+index)
                for k,v in params.items():
                    literal_value='TO_DATETIME('+json.dumps(instant(v).isoformat())+')' if k in ('period_start','period_end') else json.dumps(v)
                    query=query.replace('?'+k,literal_value)
                responses[kind]=native_http('esql','POST','/_query',{'query':query})
            return reduce_export(p,responses['count'],responses['rows'],params,snapshot_hash=hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest())['result']
        finally:native_http('esql','DELETE','/'+index)
    if engine=='postgresql':
        fields=typed_schema(p,'pg');sql='BEGIN; CREATE TEMP TABLE osms_input ('+','.join(k+' '+v for k,v in fields.items())+');\n'
        if rows:sql+='INSERT INTO osms_input VALUES '+','.join('('+','.join(literal(r.get(k)) for k in fields)+')' for r in rows)+';\n'
        query=profile['dialects']['pg']
        for k,v in params.items():query=query.replace(':'+k,literal(v))
        # JSON transport preserves column names, nulls, counts and ranking arrays.
        sql+='SELECT row_to_json(osms_result) FROM ('+query.rstrip().rstrip(';')+') AS osms_result;\nROLLBACK;'
        proc=subprocess.run(['psql','--no-psqlrc','--quiet','--tuples-only','--set','ON_ERROR_STOP=1'],input=sql,capture_output=True,text=True,check=True,timeout=30)
        actual=json.loads(proc.stdout);status=actual.pop('evaluation_status');actual.pop('selected_records');actual.pop('invalid_records')
        return {'evaluation_status':status,'outputs':actual}
    if engine in ('formulas','libreoffice'):
        import xlsx_dialect as xl
        fixture=copy.deepcopy(case);spec=copy.deepcopy(profile['excel_spec'])
        for row in fixture['rows']:
            for k,s in p['inputs'].items():
                if s['type']=='timestamp' and row.get(k) is not None:row[k]=instant(row[k]).isoformat()
        for k in ['period_start','period_end']:fixture['params'][k]=instant(params[k]).isoformat()
        tabular=spec.get('tabular_outputs',{})
        for name,col in tabular.items():
            for i in range(len(rows)):spec['outputs'][name+'__'+str(i)]='=data!'+col+str(i+2)
        path=str(Path(folder)/'semantic.xlsx');outs=xl.build_workbook(spec,fixture,path)
        actual=xl.eval_formulas(path,outs) if engine=='formulas' else xl.eval_libreoffice(path,outs,soffice=soffice,user_installation=Path(folder,'lo-profile').as_uri())
        if tabular:
            service_rows=[]
            for i in range(len(rows)):
                key=actual.get('ranked_service_id__'+str(i))
                if key not in (None,'','#N/A',0):service_rows.append({'business_service_id':key,'service_risk_raw':actual['ranked_service_risk_raw__'+str(i)],'service_risk':actual['ranked_service_risk__'+str(i)],'competition_rank':actual['competition_rank__'+str(i)]})
            actual['services']=sorted(service_rows,key=lambda r:(-r['service_risk_raw'],r['business_service_id'])) if actual.get('service_count') not in ('#N/A',None) else None
        return {'outputs':actual}
    raise ValueError('Unsupported engine')

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--bundle',default='recipes/out')
    ap.add_argument('--engine',choices=['python','duckdb','postgresql','formulas','libreoffice','esql','spl'],required=True)
    ap.add_argument('--cards');ap.add_argument('--positive-only',action='store_true');ap.add_argument('--soffice',default='soffice')
    ap.add_argument('--shard',help='Disjoint card partition I/N, zero-based');a=ap.parse_args()
    source=Path(a.bundle,'execution-profiles.json');bundle=json.loads(source.read_text(encoding='utf-8'))
    profiles={cid:ps['prepared_observations_v1'] for cid,ps in bundle['profiles'].items() if 'prepared_observations_v1' in ps}
    if a.cards:
        wanted=set(a.cards.split(','))
        if wanted-set(profiles):ap.error('Unknown semantic cards')
        profiles={cid:p for cid,p in profiles.items() if cid in wanted}
    if a.shard:
        from partitions import partition
        wanted=set(partition(list(profiles),a.shard))
        profiles={cid:p for cid,p in profiles.items() if cid in wanted}
        a.cards=','.join(sorted(wanted))
    if a.engine in ('esql','spl'):
        from profile_runner import native_http
        version=native_http('esql','GET','/')['version']['number'] if a.engine=='esql' else native_http('spl','GET','/services/server/info?output_mode=json')['entry'][0]['content']['version']
    elif a.engine=='python':version=platform.python_version()
    elif a.engine=='postgresql':version=subprocess.check_output(['psql','--no-psqlrc','--tuples-only','--command','SHOW server_version'],text=True,timeout=20).strip()
    elif a.engine=='libreoffice':
        with tempfile.TemporaryDirectory() as d:version=subprocess.check_output([a.soffice,'--headless','-env:UserInstallation='+Path(d).as_uri(),'--version'],text=True,timeout=20).strip()
    else:version=importlib.metadata.version(a.engine)
    report={'engine':a.engine,'engine_version':version,'stage':'prepared_observations','profile_id':'prepared_observations_v1',
            'profile_bundle_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'source_files_sha256':bundle['source_files_sha256'],
            'requested_subset':a.cards,'positive_only':a.positive_only,'cases':[]}
    aborted=False
    with tempfile.TemporaryDirectory(prefix='osms-semantic-') as folder:
        for cid,p in profiles.items():
            for fixture in p['fixtures']:
                for c in [fixture] if a.positive_only else boundaries(p['plan'],fixture):
                    row={'card_id':cid,'case_id':c['name'],'outputs':list(c['expected']),'status':'fail'}
                    try:
                        actual=run(p,c,a.engine,folder,a.soffice)
                        errors=[k for k,v in c['expected'].items() if k not in actual['outputs'] or not equal(actual['outputs'][k],v,p['plan']['output_contracts'].get(k))]
                        if c.get('status') and 'evaluation_status' in actual and actual['evaluation_status']!=c['status']:errors.append('evaluation_status')
                        row.update(status='fail' if errors else 'pass',failed_outputs=errors,actual=actual)
                    except Exception as exc:
                        row.update(error=type(exc).__name__+': '+str(exc))
                        if isinstance(exc,urllib.error.HTTPError):row['error']+=' '+exc.read().decode('utf-8',errors='replace')[:2000]
                        if isinstance(exc,(subprocess.TimeoutExpired,FileNotFoundError,urllib.error.URLError)):aborted=True
                    report['cases'].append(row)
                    if row['status']=='fail':print(cid,c['name'],row.get('failed_outputs',row.get('error')),json.dumps(row.get('actual',{}),ensure_ascii=False)[:2500],flush=True)
                    if aborted:break
                if aborted:break
            if aborted:break
    report['aborted']=aborted;report['passed']=sum(c['status']=='pass' for c in report['cases']);report['failed']=len(report['cases'])-report['passed']
    suffix='positive' if a.positive_only else 'boundaries'
    if a.shard:suffix+='-shard-'+a.shard.replace('/','-of-')
    Path(a.bundle,'profile-report-semantic-'+a.engine+'-'+suffix+'.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(a.engine,report['passed'],'passed;',report['failed'],'failed; aborted',aborted)
    return int(bool(report['failed'] or aborted))

if __name__=='__main__':raise SystemExit(main())
