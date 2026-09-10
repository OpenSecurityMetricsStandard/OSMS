# SPDX-License-Identifier: MIT
"""Native typed KQL and DAX calculation queries, with explicit capacity gates."""
import json
import copy

def flatten(p):
    """Share row subexpressions; preserve the contract hash and operation order."""
    q=copy.deepcopy(p);derived={};cache={}
    def emit(e):
        if not isinstance(e,list):return e
        key=json.dumps(e,sort_keys=True)
        if key in cache:return {'field':cache[key]}
        value=[e[0],*[emit(a) for a in e[1:]]]
        name='_expr_'+str(len(cache));cache[key]=name;derived[name]=value
        return {'field':name}
    for name,e in p['derived'].items():derived[name]=emit(e)
    q['statistics']={k:{**s,'expr':emit(s['expr']),**({'where':emit(s['where'])} if 'where' in s else {})} for k,s in p['statistics'].items()}
    q['row_constraints']=[emit(e) for e in p['row_constraints']];q['derived']=derived
    return q

def lit(v,d):
    if v is None:return 'real(null)' if d=='kql' else 'BLANK()'
    if isinstance(v,bool):return str(v).lower() if d=='kql' else 'TRUE()' if v else 'FALSE()'
    if isinstance(v,(int,float)):return repr(float(v)) if d=='kql' else repr(v)
    return json.dumps(str(v),ensure_ascii=False) if d=='kql' else '"'+str(v).replace('"','""')+'"'

def expr(e,d,fields=None,stats=None):
    if isinstance(e,dict):
        k=e.get('field',e.get('stat'))
        return (fields or {}).get(k,k if d=='kql' else '['+k+']') if 'field' in e else (stats or {}).get(k,'_s_'+k if d=='kql' else '__'+k)
    if not isinstance(e,list):return lit(e,d)
    name,*args=e;x=[expr(a,d,fields,stats) for a in args]
    if name=='if':return ('iff' if d=='kql' else 'IF')+'('+','.join(x)+')'
    if name=='present':return ('isnotnull('+x[0]+')') if d=='kql' else '(NOT ISBLANK('+x[0]+'))'
    if name=='coalesce':return ('coalesce' if d=='kql' else 'COALESCE')+'('+','.join(x)+')'
    if name in ('and','or'):return '('+(' '+name+' ' if d=='kql' else ' && ' if name=='and' else ' || ').join(x)+')'
    if name=='not':return 'not(coalesce('+x[0]+',false))' if d=='kql' else 'NOT('+x[0]+')'
    if name in ('eq','ne','lt','le','gt','ge'):value='('+x[0]+{'eq':'==','ne':'!=','lt':'<','le':'<=','gt':'>','ge':'>='}[name]+x[1]+')'
    elif name in ('add','mul'):value='('+('+' if name=='add' else '*').join(x)+')'
    elif name=='sub':value='('+x[0]+'-'+x[1]+')'
    elif name=='div':value='iff('+x[1]+'==0.0,real(null),'+x[0]+'*1.0/'+x[1]+')' if d=='kql' else 'DIVIDE('+','.join(x)+')'
    elif name in ('min','max'):
        if d=='kql':
            value=name+'_of('+','.join(x)+')'
            for v in reversed(x):value='iff(isnull('+v+'),'+v+','+value+')'
        else:
            value=x[0]
            for v in x[1:]:value=name.upper()+'('+value+','+v+')'
    elif name in ('abs','sqrt'):value=(name if d=='kql' else name.upper())+'('+x[0]+')'
    elif name in ('hours','days','minutes'):
        value="(datetime_diff('microsecond',"+x[0]+','+x[1]+')/'+str({'hours':3600e6,'days':86400e6,'minutes':60e6}[name])+')' if d=='kql' else '('+x[0]+'-'+x[1]+')*'+str({'hours':24,'days':1,'minutes':1440}[name])
    else:raise ValueError('Unrendered '+d+' operation '+name)
    if d=='dax':
        value=value.replace('!=','<>')
        # DAX arithmetic converts BLANK to zero; the plan requires propagation.
        value='IF('+' || '.join('ISBLANK('+v+')' for v in x)+',BLANK(),'+value+')'
    return value

def valid(p,d):
    rules=[]
    for k,s in p['inputs'].items():
        x=k if d=='kql' else '['+k+']'
        terms=[('isnotnull('+x+')') if d=='kql' else 'NOT ISBLANK('+x+')']
        if s['type']=='string':terms=["isnotempty(trim(@'\\s+',"+x+'))' if d=='kql' else 'LEN(TRIM('+x+'))>0']
        if s['type']=='number':
            terms += [x+'>='+lit(s.get('minimum',-1e15),d),x+'<='+lit(s.get('maximum',1e15),d)]
            if s.get('integer'):terms += [x+'==floor('+x+',1.0)' if d=='kql' else x+'==INT('+x+')']
        if 'enum' in s:
            terms.append('(' + (' or ' if d=='kql' else ' || ').join((x+'=='+lit(v,d)) if d=='kql' else 'EXACT('+x+','+lit(v,d)+')' for v in s['enum'])+')')
        rule='('+(' and ' if d=='kql' else ' && ').join(terms)+')'
        if s.get('nullable'):rule=('(isempty('+x+') or '+rule+')') if d=='kql' and s['type']=='string' else ('(isnull('+x+') or '+rule+')') if d=='kql' else '(ISBLANK('+x+') || '+rule+')'
        rules.append(rule)
    rules += [k+'=='+lit(p[k],d) if d=='kql' else 'EXACT(['+k+'],'+lit(p[k],d)+')' for k in ['card_version','contract_hash']]
    rules += [expr(e,d) for e in p['row_constraints']]
    return '('+(' and ' if d=='kql' else ' && ').join(rules)+')'

def identity(p,d):
    if d=='kql':return 'strcat('+','.join('strlen(tostring('+f+')),":",tolower(tostring('+f+')),"|"' for f in p['identity_fields'])+')'
    return ' & '.join('LEN(['+f+']) & ":" & LOWER(['+f+']) & "|"' for f in p['identity_fields'])

def kql(p):
    if p.get('grouping'):return ranking_kql(p)
    p=flatten(p)
    head='''// Bind these five parameters to the declared reporting population.
let scope_id_parameter="prod";
let segment_id_parameter="all";
let period_start_parameter=datetime(2026-06-01);
let period_end_parameter=datetime(2026-07-01);
let population_complete_parameter=false;
osms_input
'''
    lines=[head+'| where card_id=='+lit(p['card_id'],'kql')+' and scope_id==scope_id_parameter and segment_id==segment_id_parameter and period_start==period_start_parameter and period_end==period_end_parameter']
    for k,e in p['derived'].items():lines.append('| extend '+k+'='+expr(e,'kql'))
    lines.append('| extend row_invalid=iff('+valid(p,'kql')+',0,1), identity_key='+identity(p,'kql'))
    aggs=['selected_records=count()','invalid_records=sum(row_invalid)','identities=make_set(identity_key,1048576)'];after=[]
    aggs += ['_constant_'+k+'=make_set('+k+',2)' for k in p.get('constant_fields',[])]
    for k,s in p['statistics'].items():
        k='_s_'+k
        x=expr(s['expr'],'kql')
        if 'where' in s:x='iff('+expr(s['where'],'kql')+','+x+',real(null))'
        m=s['method']
        if m in ('median','quantile'):
            aggs.append('_array_'+k+'=make_list('+x+',1048576)')
            after.append('| extend _array_'+k+'=array_sort_asc(_array_'+k+')')
            n='array_length(_array_'+k+')';a='_array_'+k
            v='(toreal('+a+'[toint(floor(('+n+'-1)/2.0,1.0))])+toreal('+a+'[toint(floor('+n+'/2.0,1.0))]))/2.0' if m=='median' else 'toreal('+a+'[toint(ceiling('+str(s['q'])+'*'+n+')-1)])'
            after.append('| extend '+k+'=iff('+n+'==0,real(null),'+v+')')
        else:
            v='countif(isnotnull('+x+'))' if m=='count' else {'sum':'sum','mean':'avg','max':'max','min':'min','stddev_population':'stdevp'}[m]+'('+x+')'
            aggs.append(k+'='+v)
    lines.append('| summarize '+',\n '.join(aggs));lines+=after
    invalid='invalid_records>0 or array_length(identities)!=selected_records'+(' or selected_records!=1' if p['single_record'] else '')
    invalid+=''.join(' or array_length(_constant_'+k+')!=1' for k in p.get('constant_fields',[]))
    for c in p['aggregate_constraints']:invalid+=' or not(coalesce('+expr(c,'kql')+',false))'
    params='isnull(period_start_parameter) or isnull(period_end_parameter) or period_start_parameter>=period_end_parameter or isempty(trim(@"\\s+",scope_id_parameter)) or isempty(trim(@"\\s+",segment_id_parameter))'
    values={k:expr(e,'kql') for k,e in p['outputs'].items()}
    primary=[values[k] for k in p['primary_outputs'] or values]
    status='case('+params+',"invalid_input",not(population_complete_parameter),"population_unverified",selected_records>1048576,"capacity_exceeded",selected_records==0,'+lit(p['empty'],'kql')+','+invalid+',"invalid_input",'+' and '.join('isnotnull('+x+')' for x in primary)+',"ok",'+' or '.join('isnotnull('+x+')' for x in primary)+',"partial","not_applicable")'
    lines.append('| extend evaluation_status='+status)
    outs=[]
    for k,v in values.items():
        empty=p.get('empty_outputs',{}).get(k,0 if p['empty']=='ok' else None)
        outs.append(k+'=case(evaluation_status in ("invalid_input","population_unverified","capacity_exceeded"),real(null),selected_records==0,'+lit(empty,'kql')+',toreal('+v+'))')
    lines.append('| project '+',\n '.join(outs+['evaluation_status','selected_records','invalid_records']))
    return '\n'.join(lines)

def dax(p):
    if p.get('grouping'):return ranking_dax(p)
    p=flatten(p)
    lines=['''// Typed UTC osms_input table. Set populationComplete only with population evidence.
EVALUATE
VAR scopeId="prod"
VAR segmentId="all"
VAR periodStart=DATE(2026,6,1)
VAR periodEnd=DATE(2026,7,1)
VAR populationComplete=FALSE()
VAR selected=FILTER(ALL(osms_input),EXACT(osms_input[card_id],'''+lit(p['card_id'],'dax')+''') && EXACT(osms_input[scope_id],scopeId) && EXACT(osms_input[segment_id],segmentId) && osms_input[period_start]==periodStart && osms_input[period_end]==periodEnd)''']
    prev='selected'
    for i,(k,e) in enumerate(p['derived'].items()):
        name='__derived'+str(i);lines.append('VAR '+name+'=ADDCOLUMNS('+prev+','+lit(k,'dax')+','+expr(e,'dax')+')');prev=name
    lines += ['VAR selectedRecords=COUNTROWS(selected)+0','VAR invalidRecords=COUNTROWS(FILTER('+prev+',NOT('+valid(p,'dax')+')))+0',
              'VAR distinctRecords=COUNTROWS(DISTINCT(SELECTCOLUMNS('+prev+',"identity",'+identity(p,'dax')+')))+0']
    for k,s in p['statistics'].items():
        x=expr(s['expr'],'dax');table=prev
        if 'where' in s:table='FILTER('+table+','+expr(s['where'],'dax')+')'
        table='FILTER('+table+',NOT ISBLANK('+x+'))';m=s['method']
        if m=='quantile':a='MAXX(TOPN(ROUNDUP('+str(s['q'])+'*COUNTROWS('+table+'),0),'+table+','+x+',ASC),'+x+')'
        elif m=='count':a='COUNTROWS('+table+')+0'
        else:a={'sum':'SUMX','mean':'AVERAGEX','max':'MAXX','min':'MINX','median':'MEDIANX','stddev_population':'STDEVX.P'}[m]+'('+table+','+x+')'
        if m=='sum':a='COALESCE('+a+',0)'
        if m=='stddev_population':a='IF(COUNTROWS('+table+')=1,0,IF(COUNTROWS('+table+')=0,BLANK(),'+a+'))'
        lines.append('VAR __'+k+'='+a)
    bad='invalidRecords>0 || distinctRecords<>selectedRecords'+(' || selectedRecords<>1' if p['single_record'] else '')
    bad+=''.join(' || COUNTROWS(DISTINCT(SELECTCOLUMNS('+prev+',"v",['+k+'])))<>1' for k in p.get('constant_fields',[]))
    for c in p['aggregate_constraints']:bad+=' || NOT('+expr(c,'dax')+')'
    params='ISBLANK(periodStart) || ISBLANK(periodEnd) || periodStart>=periodEnd || LEN(TRIM(scopeId))=0 || LEN(TRIM(segmentId))=0'
    values={k:expr(e,'dax') for k,e in p['outputs'].items()};primary=[values[k] for k in p['primary_outputs'] or values]
    status='SWITCH(TRUE(),'+params+',"invalid_input",NOT(populationComplete),"population_unverified",selectedRecords=0,'+lit(p['empty'],'dax')+','+bad+',"invalid_input",'+' && '.join('NOT ISBLANK('+x+')' for x in primary)+',"ok",'+' || '.join('NOT ISBLANK('+x+')' for x in primary)+',"partial","not_applicable")'
    lines.append('VAR evaluationStatus='+status);outs=[]
    for k,v in values.items():
        empty=p.get('empty_outputs',{}).get(k,0 if p['empty']=='ok' else None)
        outs += [lit(k,'dax'),'IF(evaluationStatus IN {"invalid_input","population_unverified"},BLANK(),IF(selectedRecords=0,'+lit(empty,'dax')+','+v+'))']
    outs += ['"evaluation_status"','evaluationStatus','"selected_records"','selectedRecords','"invalid_records"','invalidRecords']
    lines.append('RETURN ROW('+',\n '.join(outs)+')');return '\n'.join(lines)

def ranking_kql(p):
    # The numeric ranking and its summary are emitted as one dynamic array.
    return '''let scope_id_parameter="prod";
let segment_id_parameter="all";
let period_start_parameter=datetime(2026-06-01);
let period_end_parameter=datetime(2026-07-01);
let population_complete_parameter=false;
let selected=materialize(osms_input | where card_id=="STD-003" and scope_id==scope_id_parameter and segment_id==segment_id_parameter and period_start==period_start_parameter and period_end==period_end_parameter
| extend row_invalid=iff('''+valid(p,'kql')+''',0,1),identity_key='''+identity(p,'kql')+''');
let checks=selected | summarize selected_records=count(),invalid_records=sum(row_invalid),identities=make_set(identity_key,1048576);
let groups=materialize(selected | summarize asset_sum=sum(asset_risk),cmin=min(service_criticality),cmax=max(service_criticality),dmin=min(dependency_factor),dmax=max(dependency_factor) by business_service_id
| extend service_risk_raw=asset_sum*cmax*dmax,factor_conflict=iff(cmin!=cmax or dmin!=dmax,1,0));
let maximum=toscalar(groups | summarize max(service_risk_raw));
let packed=groups | sort by service_risk_raw desc,business_service_id asc | serialize
| extend position=row_number(),previous_risk=prev(service_risk_raw)
| extend rank_start=iff(isnull(previous_risk) or previous_risk!=service_risk_raw,position,long(null))
| scan declare (competition_rank:long=0) with (step s:true => competition_rank=iff(isnotnull(rank_start),rank_start,s.competition_rank);)
| extend service_risk=iff(maximum==0,0.0,100.0*service_risk_raw/maximum)
| summarize services=make_list(bag_pack("business_service_id",business_service_id,"service_risk_raw",service_risk_raw,"service_risk",service_risk,"competition_rank",competition_rank),1048576),service_count=count(),factor_conflicts=sum(factor_conflict);
checks | extend join_key=1 | join kind=inner (packed | extend join_key=1) on join_key
| extend evaluation_status=case(isnull(period_start_parameter) or isnull(period_end_parameter) or period_start_parameter>=period_end_parameter or isempty(scope_id_parameter) or isempty(segment_id_parameter),"invalid_input",not(population_complete_parameter),"population_unverified",selected_records>1048576,"capacity_exceeded",invalid_records>0 or array_length(identities)!=selected_records or factor_conflicts>0,"invalid_input",selected_records==0,"not_applicable","ok")
| project services=iff(evaluation_status in ("ok","not_applicable"),services,dynamic(null)),service_count=iff(evaluation_status in ("ok","not_applicable"),service_count,long(null)),evaluation_status,selected_records,invalid_records'''

def ranking_dax(p):
    return '''EVALUATE
VAR scopeId="prod"
VAR segmentId="all"
VAR periodStart=DATE(2026,6,1)
VAR periodEnd=DATE(2026,7,1)
VAR populationComplete=FALSE()
VAR selected=FILTER(ALL(osms_input),EXACT([card_id],"STD-003") && EXACT([scope_id],scopeId) && EXACT([segment_id],segmentId) && [period_start]==periodStart && [period_end]==periodEnd)
VAR invalidRecords=COUNTROWS(FILTER(selected,NOT('''+valid(p,'dax')+''')))+0
VAR distinctRecords=COUNTROWS(DISTINCT(SELECTCOLUMNS(selected,"identity",'''+identity(p,'dax')+''')))+0
VAR groups=GROUPBY(selected,osms_input[business_service_id],"asset_sum",SUMX(CURRENTGROUP(),[asset_risk]),"cmin",MINX(CURRENTGROUP(),[service_criticality]),"cmax",MAXX(CURRENTGROUP(),[service_criticality]),"dmin",MINX(CURRENTGROUP(),[dependency_factor]),"dmax",MAXX(CURRENTGROUP(),[dependency_factor]))
VAR scores=ADDCOLUMNS(groups,"service_risk_raw",[asset_sum]*[cmax]*[dmax])
VAR maximum=MAXX(scores,[service_risk_raw])
VAR result=ADDCOLUMNS(scores,"service_risk",IF(maximum=0,0,DIVIDE(100*[service_risk_raw],maximum)),"competition_rank",RANKX(scores,[service_risk_raw],,DESC,SKIP))
VAR n=COUNTROWS(selected)+0
VAR evaluationStatus=SWITCH(TRUE(),ISBLANK(periodStart) || ISBLANK(periodEnd) || periodStart>=periodEnd || LEN(TRIM(scopeId))=0 || LEN(TRIM(segmentId))=0,"invalid_input",NOT(populationComplete),"population_unverified",invalidRecords>0 || distinctRecords<>n || COUNTROWS(FILTER(groups,[cmin]<>[cmax] || [dmin]<>[dmax]))>0,"invalid_input",n=0,"not_applicable","ok")
VAR summary=ROW("row_kind","summary","business_service_id",BLANK(),"service_risk_raw",BLANK(),"service_risk",BLANK(),"competition_rank",BLANK(),"evaluation_status",evaluationStatus,"selected_records",n,"invalid_records",invalidRecords,"service_count",IF(evaluationStatus IN {"ok","not_applicable"},COUNTROWS(groups)+0,BLANK()))
VAR details=SELECTCOLUMNS(FILTER(result,evaluationStatus="ok"),"row_kind","service","business_service_id",[business_service_id],"service_risk_raw",[service_risk_raw],"service_risk",[service_risk],"competition_rank",[competition_rank],"evaluation_status",evaluationStatus,"selected_records",n,"invalid_records",invalidRecords,"service_count",COUNTROWS(groups)+0)
RETURN UNION(summary,details)
ORDER BY [row_kind] DESC,[service_risk_raw] DESC,[business_service_id] ASC'''
