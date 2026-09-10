# SPDX-License-Identifier: MIT
"""Compile explicit calculation plans to executable retained platform profiles."""
import inspect
import json
from . import model

PARAMS={'scope_id':'prod','segment_id':'all','period_start':'2026-06-01T00:00:00Z','period_end':'2026-07-01T00:00:00Z','population_complete':True}

def literal(value,dialect='gsql'):
    if value is None:return 'NULL'
    if isinstance(value,bool):return 'TRUE' if value else 'FALSE'
    if isinstance(value,(int,float)):return repr(value)
    return "'"+str(value).replace("'","''")+"'"

def expression(e,d='gsql',fields=None,stats=None):
    if isinstance(e,dict):
        key=e.get('field',e.get('stat'))
        return (fields or {}).get(key,key) if 'field' in e else (stats or {}).get(key,key)
    if not isinstance(e,list):return literal(e,d)
    name,*args=e;x=[expression(a,d,fields,stats) for a in args]
    if name=='if':return f'(CASE WHEN {x[0]} THEN {x[1]} ELSE {x[2]} END)'
    if name=='present':return f'({x[0]} IS NOT NULL)'
    if name=='coalesce':return 'COALESCE('+','.join(x)+')'
    if name in ('and','or'):return '('+(' '+name.upper()+' ').join(x)+')'
    if name=='not':return '(NOT COALESCE('+x[0]+',FALSE))'
    if name in ('eq','ne','lt','le','gt','ge'):
        return '('+x[0]+{'eq':'=','ne':'<>','lt':'<','le':'<=','gt':'>','ge':'>='}[name]+x[1]+')'
    if name in ('add','mul'):return '('+('+' if name=='add' else '*').join(x)+')'
    if name=='sub':return '('+x[0]+'-'+x[1]+')'
    if name=='div':return '('+x[0]+'*1.0/NULLIF('+x[1]+',0))'
    if name in ('min','max'):
        # SQL LEAST/GREATEST skip NULL on these engines. The IR propagates NULL.
        return '(CASE WHEN '+' OR '.join(v+' IS NULL' for v in x)+' THEN NULL ELSE '+('LEAST' if name=='min' else 'GREATEST')+'('+','.join(x)+') END)'
    if name in ('abs','sqrt'):return name.upper()+'('+x[0]+')'
    if name in ('hours','days','minutes'):
        seconds={'hours':3600,'days':86400,'minutes':60}[name]
        return '(EXTRACT(EPOCH FROM ('+x[0]+'-'+x[1]+'))/'+str(seconds)+'.0)' if d=='pg' else "(date_diff('microsecond',"+x[1]+','+x[0]+')/'+str(seconds*1000000)+'.0)'
    raise ValueError('Unrendered SQL operator: '+name)

def typed_schema(p,d='gsql'):
    return {f:{'number':'DOUBLE PRECISION','boolean':'BOOLEAN','timestamp':'TIMESTAMPTZ','string':'VARCHAR'}[s['type']] for f,s in p['inputs'].items()}

def validity(p,d='gsql'):
    constraints=[]
    for f,s in p['inputs'].items():
        parts=[f+' IS NOT NULL']
        if s['type']=='string':parts.append("LENGTH(TRIM("+f+'))>0')
        if s['type']=='number':
            parts += [f+'>='+literal(s.get('minimum',-1e15)),f+'<='+literal(s.get('maximum',1e15))]
            if s.get('integer'):parts.append(f+'=FLOOR('+f+')')
        if 'enum' in s:parts.append(f+' IN ('+','.join(literal(v) for v in s['enum'])+')')
        cond='('+' AND '.join(parts)+')'
        if s.get('nullable'):cond='('+f+' IS NULL OR '+cond+')'
        constraints.append(cond)
    constraints += ['card_version='+literal(p['card_version']),'contract_hash='+literal(p['contract_hash'])]
    constraints += [expression(e,d) for e in p['row_constraints']]
    return ' AND '.join(constraints)

def identity(p):
    # Length-prefixed components avoid ambiguous concatenation of compound keys.
    parts=[]
    for f in p['identity_fields']:
        x='LOWER(CAST('+f+' AS VARCHAR))'
        parts.extend(['CAST(LENGTH('+x+') AS VARCHAR)',"':'",x,"'|' "])
    return 'CONCAT('+','.join(parts)+')'

def sql(p,d='gsql'):
    if p.get('grouping')=='service_ranking':return ranking_sql(p,d)
    lines=['-- '+p['card_id']+' '+p['profile_version']+'; prepared observations, not a source attestation.',
           '-- osms_input columns/types and population requirements are in the companion contract.',
           '-- Bind scope_id, segment_id, period_start, period_end, population_complete.',
           'WITH selected AS (SELECT * FROM osms_input WHERE card_id='+literal(p['card_id'])+
           ' AND scope_id=:scope_id AND segment_id=:segment_id AND period_start=CAST(:period_start AS TIMESTAMPTZ) AND period_end=CAST(:period_end AS TIMESTAMPTZ))']
    previous='selected'
    for i,(key,e) in enumerate(p['derived'].items()):
        name='derived_'+str(i);lines.append(', '+name+' AS (SELECT *, '+expression(e,d)+' AS '+key+' FROM '+previous+')');previous=name
    lines.append(', checked AS (SELECT *, CASE WHEN COALESCE(('+validity(p,d)+'),FALSE) THEN 0 ELSE 1 END AS row_invalid FROM '+previous+')')
    aggs=['COUNT(*) AS selected_records','COALESCE(SUM(row_invalid),0) AS invalid_records','COUNT(DISTINCT '+identity(p)+') AS distinct_records']
    aggs += ['COUNT(DISTINCT '+k+') AS _constant_'+k for k in p.get('constant_fields',[])]
    for key,s in p['statistics'].items():
        x=expression(s['expr'],d)
        if 'where' in s:x='CASE WHEN '+expression(s['where'],d)+' THEN '+x+' ELSE NULL END'
        m=s['method']
        if m=='quantile':a=f'percentile_disc({s["q"]}) WITHIN GROUP (ORDER BY {x})'
        elif m=='median':a=f'percentile_cont(0.5) WITHIN GROUP (ORDER BY {x})'
        else:a={'sum':'SUM','count':'COUNT','mean':'AVG','min':'MIN','max':'MAX','stddev_population':'STDDEV_POP'}[m]+'('+x+')'
        if m=='sum':a='COALESCE('+a+',0)'
        aggs.append(a+' AS '+key)
    lines.append(', aggregated AS (SELECT '+',\n '.join(aggs)+' FROM checked)')
    constraints=' AND '.join(expression(e,d) for e in p['aggregate_constraints']) or 'TRUE'
    invalid='invalid_records>0 OR distinct_records<>selected_records'+(' OR selected_records<>1' if p['single_record'] else '')+' OR NOT COALESCE(('+constraints+'),FALSE)'
    invalid+=''.join(' OR _constant_'+k+'<>1' for k in p.get('constant_fields',[]))
    params="CAST(:period_start AS TIMESTAMPTZ) IS NULL OR CAST(:period_end AS TIMESTAMPTZ) IS NULL OR CAST(:period_start AS TIMESTAMPTZ)>=CAST(:period_end AS TIMESTAMPTZ) OR NULLIF(TRIM(:scope_id),'') IS NULL OR NULLIF(TRIM(:segment_id),'') IS NULL"
    ready='NOT ('+params+') AND COALESCE(CAST(:population_complete AS BOOLEAN),FALSE)'
    columns=[]
    for key,e in p['outputs'].items():
        value=expression(e,d);empty=literal(p.get('empty_outputs',{}).get(key,0.0 if p['empty']=='ok' else None))
        columns.append('CASE WHEN NOT ('+ready+') THEN NULL WHEN selected_records=0 THEN '+empty+' WHEN '+invalid+' THEN NULL ELSE '+value+' END AS '+key)
    primary=[expression(p['outputs'][k],d) for k in p['primary_outputs'] or p['outputs']]
    status="CASE WHEN "+params+" THEN 'invalid_input' WHEN NOT COALESCE(CAST(:population_complete AS BOOLEAN),FALSE) THEN 'population_unverified' WHEN selected_records=0 THEN "+literal(p['empty'])+" WHEN "+invalid+" THEN 'invalid_input' WHEN "+' AND '.join(x+' IS NOT NULL' for x in primary)+" THEN 'ok' WHEN "+' OR '.join(x+' IS NOT NULL' for x in primary)+" THEN 'partial' ELSE 'not_applicable' END AS evaluation_status"
    lines.append('SELECT '+',\n '.join(columns+[status,'selected_records','invalid_records'])+' FROM aggregated;')
    return '\n'.join(lines)

def ranking_sql(p,d):
    rows="jsonb_agg(jsonb_build_object('business_service_id',business_service_id,'service_risk_raw',service_risk_raw,'service_risk',service_risk,'competition_rank',competition_rank) ORDER BY service_risk_raw DESC,business_service_id)" if d=='pg' else "to_json(list(struct_pack(business_service_id:=business_service_id,service_risk_raw:=service_risk_raw,service_risk:=service_risk,competition_rank:=competition_rank) ORDER BY service_risk_raw DESC,business_service_id))"
    empty="'[]'::jsonb" if d=='pg' else "'[]'::json"
    return f'''-- Full evidenced asset/service population; scope and period are exact.
WITH selected AS (SELECT * FROM osms_input WHERE card_id={literal(p['card_id'])}
AND scope_id=:scope_id AND segment_id=:segment_id AND period_start=CAST(:period_start AS TIMESTAMPTZ) AND period_end=CAST(:period_end AS TIMESTAMPTZ)),
checked AS (SELECT *,CASE WHEN COALESCE(({validity(p,d)}),FALSE) THEN 0 ELSE 1 END AS row_invalid FROM selected),
checks AS (SELECT COUNT(*) AS selected_records,COALESCE(SUM(row_invalid),0) AS invalid_records,COUNT(DISTINCT {identity(p)}) AS distinct_records FROM checked),
services AS (SELECT business_service_id,SUM(asset_risk)*MAX(service_criticality)*MAX(dependency_factor) AS service_risk_raw,
CASE WHEN MIN(service_criticality)=MAX(service_criticality) AND MIN(dependency_factor)=MAX(dependency_factor) THEN 0 ELSE 1 END AS factor_conflict
FROM checked GROUP BY business_service_id),
ranked AS (SELECT *,CASE WHEN MAX(service_risk_raw) OVER ()=0 THEN 0 ELSE 100*service_risk_raw/MAX(service_risk_raw) OVER () END AS service_risk,
RANK() OVER (ORDER BY service_risk_raw DESC) AS competition_rank FROM services),
packed AS (SELECT COALESCE({rows},{empty}) AS services,COUNT(*) AS service_count,COALESCE(SUM(factor_conflict),0) AS factor_conflicts FROM ranked),
result AS (SELECT *,CASE WHEN CAST(:period_start AS TIMESTAMPTZ)>=CAST(:period_end AS TIMESTAMPTZ) OR NULLIF(TRIM(:scope_id),'') IS NULL OR NULLIF(TRIM(:segment_id),'') IS NULL THEN 'invalid_input'
WHEN NOT COALESCE(CAST(:population_complete AS BOOLEAN),FALSE) THEN 'population_unverified'
WHEN invalid_records>0 OR distinct_records<>selected_records OR factor_conflicts>0 THEN 'invalid_input'
WHEN selected_records=0 THEN 'not_applicable' ELSE 'ok' END AS evaluation_status FROM checks CROSS JOIN packed)
SELECT CASE WHEN evaluation_status IN ('ok','not_applicable') THEN services ELSE NULL END AS services,
CASE WHEN evaluation_status IN ('ok','not_applicable') THEN service_count ELSE NULL END AS service_count,
evaluation_status,selected_records,invalid_records FROM result;'''

def python_code(p):
    functions=[model.instant,model.evaluate,model.valid,model.summarize,model.rank_services,model.compute]
    code='import datetime as dt\nimport math\nimport statistics\n\nPLAN = '+repr(p)+'\n\n'
    for f in functions:
        src=inspect.getsource(f)
        if f is model.compute:src=src.replace('def compute(', 'def _compute(',1)
        code+=src+'\n'
    code+='def compute(records, period_start, period_end, scope_id, segment_id="all", population_complete=False):\n'
    code+='    return _compute(PLAN, records, dict(period_start=period_start, period_end=period_end, scope_id=scope_id, segment_id=segment_id, population_complete=population_complete))\n'
    return code
