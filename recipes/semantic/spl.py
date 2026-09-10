# SPDX-License-Identifier: MIT
"""SPL over prepared UTC epoch-second observations, bounded to 10000 records."""
import json
from .platforms import flatten

def lit(v):
    if v is None:return 'null()'
    if isinstance(v,bool):return '1' if v else '0'
    return json.dumps(v)

def expression(e,condition=False):
    if isinstance(e,dict):value=e.get('field','_s_'+e.get('stat',''));return '('+value+'=1)' if condition else value
    if not isinstance(e,list):return ('true()' if e else 'false()') if condition and isinstance(e,bool) else lit(e)
    name,*args=e
    if name in ('and','or'):return '('+(' '+name.upper()+' ').join(expression(a,True) for a in args)+')'
    if name=='not':return '(NOT '+expression(args[0],True)+')'
    x=[expression(a) for a in args]
    if name=='if':return 'if('+expression(args[0],True)+','+x[1]+','+x[2]+')'
    if name=='present':return 'isnotnull('+x[0]+')'
    if name=='coalesce':return 'coalesce('+','.join(x)+')'
    if name in ('eq','ne','lt','le','gt','ge'):return '('+x[0]+{'eq':'=','ne':'!=','lt':'<','le':'<=','gt':'>','ge':'>='}[name]+x[1]+')'
    if name in ('add','mul'):return '('+('+' if name=='add' else '*').join(x)+')'
    if name=='sub':return '('+x[0]+'-'+x[1]+')'
    if name=='div':return 'if('+x[1]+'=0,null(),'+x[0]+'/'+x[1]+')'
    if name in ('min','max'):return 'if('+' OR '.join('isnull('+v+')' for v in x)+',null(),'+name+'('+','.join(x)+'))'
    if name in ('abs','sqrt'):return name+'('+x[0]+')'
    if name in ('hours','days','minutes'):return '('+x[0]+'-'+x[1]+')/'+str({'hours':3600,'days':86400,'minutes':60}[name])
    raise ValueError('Unrendered SPL operation '+name)

def bool_expr(e):return isinstance(e,list) and e[0] in ('and','or','not','present','eq','ne','lt','le','gt','ge')

def query(plan):
    p=flatten(plan)
    lines=['''```Prepared osms_input observations. All timestamps are UTC epoch seconds;
booleans are integer 0/1. Bind literal scope, segment, ps, pe and completeness.
Reject server warnings/partial searches; this exact profile supports <=10000 rows.```
index=osms_input earliest=0 latest=now
| where card_id='''+lit(p['card_id'])+''' AND scope_id=$scope_id$ AND segment_id=$segment_id$ AND period_start=$period_start$ AND period_end=$period_end$''']
    for k,e in p['derived'].items():
        value=expression(e)
        if bool_expr(e):value='if('+value+',1,0)'
        lines.append('| eval '+k+'='+value)
    rules=[]
    for k,s in p['inputs'].items():
        terms=['isnotnull('+k+')']
        if s['type']=='string':terms.append('len(trim('+k+'))>0')
        elif s['type'] in ('number','timestamp'):
            terms.append('isnum('+k+')')
            if s['type']=='number':
                terms.extend([k+'>='+lit(s.get('minimum',-1e15)),k+'<='+lit(s.get('maximum',1e15))])
                if s.get('integer'):terms.append(k+'=floor('+k+')')
        else:terms.append('('+k+'=0 OR '+k+'=1)')
        if 'enum' in s:terms.append('('+' OR '.join(k+'='+lit(v) for v in s['enum'])+')')
        rule='('+' AND '.join(terms)+')'
        if s.get('nullable'):rule='(isnull('+k+') OR '+rule+')'
        rules.append(rule)
    rules += [k+'='+lit(p[k]) for k in ['card_version','contract_hash']]+[expression(c,True) for c in p['row_constraints']]
    identity=' . '.join('len(tostring('+f+')) . ":" . lower(tostring('+f+')) . "|"' for f in p['identity_fields'])
    lines.append('| eval row_invalid=if('+' AND '.join(rules)+',0,1),identity_key='+identity+',_selected=1')
    if p.get('grouping'):return ranking_tail(p,lines)
    aggregates=['sum(_selected) as selected_records','sum(row_invalid) as invalid_records','dc(identity_key) as distinct_records'];checks=[]
    aggregates += ['dc('+k+') as _constant_'+k for k in p.get('constant_fields',[])]
    for k,s in p['statistics'].items():
        f='_v_'+k;x=expression(s['expr'])
        if bool_expr(s['expr']):x='if('+x+',1,0)'
        if 'where' in s:x='if('+expression(s['where'],True)+','+x+',null())'
        lines.append('| eval '+f+'='+x);m=s['method']
        if m in ('median','quantile'):
            n='_n_'+k;rank='_r_'+k;v='_pick_'+k
            lines += ['| eventstats count('+f+') as '+n,'| sort 0 + '+f,'| streamstats window=0 count('+f+') as '+rank]
            match=rank+'=ceil('+str(s['q'])+'*'+n+')' if m=='quantile' else '('+rank+'=floor(('+n+'+1)/2) OR '+rank+'=ceil(('+n+'+1)/2))'
            lines.append('| eval '+v+'=if(isnotnull('+f+') AND '+match+','+f+',null())')
            aggregates.extend(['avg('+v+') as _s_'+k,'max('+rank+') as _last_'+k,'max('+n+') as '+n,'count('+rank+') as _ranks_'+k])
            checks.extend(['_last_'+k+'!='+n,'_ranks_'+k+'!=selected_records'])
        else:aggregates.append({'sum':'sum','count':'count','mean':'avg','min':'min','max':'max','stddev_population':'stdevp'}[m]+'('+f+') as _s_'+k)
    lines.append('| stats '+' '.join(aggregates))
    lines.append('| eval selected_records=coalesce(selected_records,0),invalid_records=coalesce(invalid_records,0)')
    for k,s in p['statistics'].items():
        if s['method'] in ('sum','count'):lines.append('| eval _s_'+k+'=coalesce(_s_'+k+',0)')
    invalid='invalid_records>0 OR distinct_records!=selected_records'+(' OR selected_records!=1' if p['single_record'] else '')
    invalid+=''.join(' OR _constant_'+k+'!=1' for k in p.get('constant_fields',[]))
    invalid+=''.join(' OR NOT '+expression(c,True) for c in p['aggregate_constraints'])
    invalid+=''.join(' OR '+c for c in checks)
    vals={k:expression(e) for k,e in p['outputs'].items()};primary=[vals[k] for k in p['primary_outputs'] or vals]
    status='case($period_start$>=$period_end$ OR len(trim($scope_id$))=0 OR len(trim($segment_id$))=0,"invalid_input",$population_complete$!=1,"population_unverified",selected_records>10000,"capacity_exceeded",selected_records=0,'+lit(p['empty'])+','+invalid+',"invalid_input",'+' AND '.join('isnotnull('+v+')' for v in primary)+',"ok",'+' OR '.join('isnotnull('+v+')' for v in primary)+',"partial",true(),"not_applicable")'
    lines.append('| eval evaluation_status='+status)
    for k,v in vals.items():
        empty=p.get('empty_outputs',{}).get(k,0 if p['empty']=='ok' else None)
        lines.append('| eval '+k+'=case(evaluation_status="invalid_input" OR evaluation_status="population_unverified" OR evaluation_status="capacity_exceeded",null(),selected_records=0,'+lit(empty)+',true(),'+v+')')
    lines.append('| table '+' '.join([*vals,'evaluation_status','selected_records','invalid_records']))
    return '\n'.join(lines)

def ranking_tail(p,lines):
    lines += ['| eventstats count as selected_records sum(row_invalid) as invalid_records dc(identity_key) as distinct_records',
        '| stats sum(asset_risk) as asset_sum min(service_criticality) as cmin max(service_criticality) as cmax min(dependency_factor) as dmin max(dependency_factor) as dmax max(selected_records) as selected_records max(invalid_records) as invalid_records max(distinct_records) as distinct_records by business_service_id',
        '| eval service_risk_raw=asset_sum*cmax*dmax,factor_conflict=if(cmin!=cmax OR dmin!=dmax,1,0)',
        '| eventstats max(service_risk_raw) as maximum sum(factor_conflict) as factor_conflicts',
        '| sort 0 - service_risk_raw + business_service_id',
        '| streamstats window=0 count as position',
        '| eventstats min(position) as competition_rank by service_risk_raw',
        '| eval service_risk=if(maximum=0,0,100*service_risk_raw/maximum)',
        '| appendpipe [ stats count as _existing | where _existing=0 | eval selected_records=0,invalid_records=0,distinct_records=0,factor_conflicts=0 ]',
        '| eval evaluation_status=case($period_start$>=$period_end$ OR len(trim($scope_id$))=0 OR len(trim($segment_id$))=0,"invalid_input",$population_complete$!=1,"population_unverified",selected_records>10000,"capacity_exceeded",invalid_records>0 OR selected_records!=distinct_records OR factor_conflicts>0,"invalid_input",selected_records=0,"not_applicable",true(),"ok")',
        '| eval service_risk_raw=if(evaluation_status="ok",service_risk_raw,null()),service_risk=if(evaluation_status="ok",service_risk,null()),competition_rank=if(evaluation_status="ok",competition_rank,null())',
        '| table business_service_id service_risk_raw service_risk competition_rank evaluation_status selected_records invalid_records']
    return '\n'.join(lines)
