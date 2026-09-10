# SPDX-License-Identifier: MIT
"""Native Excel range formulas for typed observation plans (no macros)."""
import json
import xlsx_dialect as xl

def lit(v):
    if v is None:return '""'
    if isinstance(v,bool):return 'TRUE' if v else 'FALSE'
    if isinstance(v,(int,float)):return repr(v)
    return '"'+str(v).replace('"','""')+'"'

def expr(e,fields,stats=None):
    if isinstance(e,dict):return fields[e['field']] if 'field' in e else stats[e['stat']]
    if not isinstance(e,list):return lit(e)
    name,*args=e;x=[expr(a,fields,stats) for a in args]
    if name=='if':return 'IF('+','.join(x)+')'
    if name=='present':return '('+x[0]+'<>"")'
    if name=='coalesce':
        v='""'
        for item in reversed(x):v='IF('+item+'<>"",'+item+','+v+')'
        return v
    if name in ('and','or'):return name.upper()+'('+','.join(x)+')'
    if name=='not':return 'NOT('+x[0]+')'
    if name in ('eq','ne','lt','le','gt','ge'):
        value=('EXACT('+','.join(x)+')') if name=='eq' else 'NOT(EXACT('+','.join(x)+'))' if name=='ne' else '('+x[0]+{'lt':'<','le':'<=','gt':'>','ge':'>='}[name]+x[1]+')'
    elif name in ('add','mul'):value='('+('+' if name=='add' else '*').join(x)+')'
    elif name=='sub':value='('+x[0]+'-'+x[1]+')'
    elif name=='div':value='IF('+x[1]+'=0,"",'+x[0]+'/'+x[1]+')'
    elif name in ('min','max','abs','sqrt'):value=name.upper()+'('+','.join(x)+')'
    elif name in ('hours','days','minutes'):value='('+x[0]+'-'+x[1]+')*'+str({'hours':24,'days':1,'minutes':1440}[name])
    else:raise ValueError('Unrendered Excel operation: '+name)
    return 'IF(OR('+','.join(v+'=""' for v in x)+'),"",'+value+')'

def spec(p):
    columns=list(p['inputs']);fields={k:'$'+xl.LETTER(i+1)+'{r}' for i,k in enumerate(columns)}
    helpers=[]
    def helper(name,formula):
        helpers.append((name,'='+formula));fields[name]='$'+xl.LETTER(len(columns)+len(helpers))+'{r}'
        return fields[name]
    def rng(name):
        col=fields[name].split('{')[0].replace('$','');return f'data!{col}$2:{col}$100000'
    selected=helper('_selected','IFERROR(IF(AND('+','.join([
        'EXACT('+fields['card_id']+','+lit(p['card_id'])+')',
        'EXACT('+fields['scope_id']+',result!$B$1)','EXACT('+fields['segment_id']+',result!$B$4)',
        fields['period_start']+'=result!$B$2',fields['period_end']+'=result!$B$3'])+'),1,0),0)')
    row_cache={}
    def row_expr(e):
        if not isinstance(e,list):return expr(e,fields)
        key=json.dumps(e,sort_keys=True)
        if key in row_cache:return row_cache[key]
        args=[row_expr(a) for a in e[1:]]
        formula=expr([e[0],*[{'field':str(i)} for i in range(len(args))]],{str(i):v for i,v in enumerate(args)})
        out=helper('_expr_'+str(len(row_cache)),'IF('+selected+'=1,'+formula+',"")')
        row_cache[key]=out;return out
    for k,e in p['derived'].items():helper(k,row_expr(e))
    valid=[]
    for k,s in p['inputs'].items():
        x=fields[k];terms=[x+'<>""']
        if s['type']=='number':
            terms.extend(['ISNUMBER('+x+')',x+'>='+lit(s.get('minimum',-1e15)),x+'<='+lit(s.get('maximum',1e15))])
            if s.get('integer'):terms.append(x+'=INT('+x+')')
        elif s['type']=='timestamp':terms.append('ISNUMBER('+x+')')
        elif s['type']=='boolean':terms.append('ISLOGICAL('+x+')')
        else:terms.extend(['ISTEXT('+x+')','LEN(TRIM('+x+'))>0'])
        if 'enum' in s:
            checks=['EXACT('+x+','+lit(v)+')' for v in s['enum']]
            if len(checks)>32:
                checks=[helper('_enum_'+k+'_'+str(i),'OR('+','.join(checks[i:i+32])+')') for i in range(0,len(checks),32)]
            terms.append('OR('+','.join(checks)+')')
        value='AND('+','.join(terms)+')'
        if s.get('nullable'):value='OR('+x+'="",'+value+')'
        valid.append(value)
    valid.extend(['EXACT('+fields[k]+','+lit(p[k])+')' for k in ['card_version','contract_hash']])
    for k in p.get('constant_fields',[]):
        escaped='SUBSTITUTE(SUBSTITUTE(SUBSTITUTE('+fields[k]+',"~","~~"),"*","~*"),"?","~?")'
        valid.append('COUNTIFS('+rng(k)+','+escaped+','+rng('_selected')+',1)=SUM('+rng('_selected')+')')
    valid.extend(row_expr(e) for e in p['row_constraints'])
    parts=[helper('_valid_'+str(i),'IFERROR(AND('+','.join(valid[i:i+12])+'),FALSE)') for i in range(0,len(valid),12)]
    helper('_invalid','IF('+selected+'=1,IFERROR(IF(AND('+','.join(parts)+'),0,1),1),0)')
    key=helper('_identity','IF('+selected+'=1,'+'&'.join('LEN('+fields[k]+')&":"&LOWER('+fields[k]+')&"|"' for k in p['identity_fields'])+',"")')
    escaped='SUBSTITUTE(SUBSTITUTE(SUBSTITUTE('+key+',"~","~~"),"*","~*"),"?","~?")'
    helper('_duplicate','IF('+selected+'=1,IF(COUNTIFS('+rng('_identity')+','+escaped+','+rng('_selected')+',1)>1,1,0),0)')
    if p.get('grouping'):
        return ranking_spec(p,columns,helpers,fields,helper,rng)
    statforms={};statrefs={}
    for k,s in p['statistics'].items():
        cond=selected+'=1'
        if 'where' in s:cond='AND('+cond+','+row_expr(s['where'])+')'
        helper('_stat_'+k,'IF('+cond+','+row_expr(s['expr'])+',"")')
        r=rng('_stat_'+k);m=s['method'];n='COUNT('+r+')'
        if m=='quantile':a='SMALL('+r+',CEILING('+str(s['q'])+'*'+n+',1))'
        elif m=='median':a='MEDIAN('+r+')'
        else:a={'sum':'SUM','count':'COUNT','mean':'AVERAGE','min':'MIN','max':'MAX','stddev_population':'STDEVP'}[m]+'('+r+')'
        if m not in ('sum','count'):a='IF('+n+'=0,"",'+a+')'
        statforms[k]='='+a;statrefs[k]='calculation!$B$'+str(len(statforms))
    ns='SUM('+rng('_selected')+')';bad='SUM('+rng('_invalid')+')+SUM('+rng('_duplicate')+')'
    gate='AND(ISNUMBER(result!$B$2),ISNUMBER(result!$B$3),result!$B$2<result!$B$3,LEN(TRIM(result!$B$1))>0,LEN(TRIM(result!$B$4))>0,ISLOGICAL(result!$B$5),result!$B$5=TRUE)'
    agg_cache={}
    def agg_expr(e):
        if not isinstance(e,list):return expr(e,fields,statrefs)
        key=json.dumps(e,sort_keys=True)
        if key in agg_cache:return agg_cache[key]
        args=[agg_expr(a) for a in e[1:]]
        formula=expr([e[0],*[{'field':str(i)} for i in range(len(args))]],{str(i):v for i,v in enumerate(args)})
        statforms['_expr_'+str(len(agg_cache))]='='+formula
        out='calculation!$B$'+str(len(statforms));agg_cache[key]=out;return out
    constraints=['('+bad+')=0']+([ns+'=1'] if p['single_record'] else [])+[agg_expr(e) for e in p['aggregate_constraints']]
    ok='IFERROR(AND('+','.join(constraints)+'),FALSE)'
    outputs={}
    for k,e in p['outputs'].items():
        empty=p.get('empty_outputs',{}).get(k,0 if p['empty']=='ok' else None)
        value=agg_expr(e)
        outputs[k]='=IFERROR(IF(NOT('+gate+'),NA(),IF('+ns+'=0,'+('NA()' if empty is None else lit(empty))+',IF('+ok+',IF('+value+'="",NA(),'+value+'),NA()))),NA())'
    outputs['selected_records']='='+ns;outputs['invalid_records']='='+bad
    return {'columns':columns,'helpers':helpers,'outputs':outputs,'params':['scope','ps','pe','segment','complete'],
            'extra_params':{'B4':['segment_id','all'],'B5':['population_complete',False]},'result_start':8,
            'calculation_cells':statforms,'note':'Prepared observations; exact UTC scope/period. Explicit population completeness attestation in B5. NA blocks missing/invalid results. Input evidence authenticity and source population require separate validation.'}

def ranking_spec(p,columns,helpers,fields,helper,rng):
    selected=fields['_selected'];service=fields['business_service_id']
    helper('_selected_service','IF('+selected+'=1,'+service+',"")')
    escaped='SUBSTITUTE(SUBSTITUTE(SUBSTITUTE('+service+',"~","~~"),"*","~*"),"?","~?")'
    sr=rng('_selected_service');sel=rng('_selected')
    count='COUNTIFS('+sr+','+escaped+','+sel+',1)'
    same='COUNTIFS('+sr+','+escaped+','+sel+',1,'+rng('service_criticality')+','+fields['service_criticality']+','+rng('dependency_factor')+','+fields['dependency_factor']+')'
    case='EXACT('+service+',INDEX('+sr+',MATCH('+escaped+','+sr+',0)))'
    helper('_factor_conflict','IF('+selected+'=1,IFERROR(IF(AND('+same+'='+count+','+case+'),0,1),1),0)')
    first='COUNTIFS('+sr.replace('$100000','{r}')+','+escaped+','+sel.replace('$100000','{r}')+',1)=1'
    helper('_service_first','IF(AND('+selected+'=1,'+first+'),1,0)')
    helper('_service_raw','IF('+fields['_service_first']+'=1,SUMIFS('+rng('asset_risk')+','+sr+','+escaped+','+sel+',1)*'+fields['service_criticality']+'*'+fields['dependency_factor']+',"")')
    ns='SUM('+sel+')';bad='SUM('+rng('_invalid')+')+SUM('+rng('_duplicate')+')+SUM('+rng('_factor_conflict')+')'
    ready='AND(ISNUMBER(result!$B$2),ISNUMBER(result!$B$3),result!$B$2<result!$B$3,LEN(TRIM(result!$B$1))>0,LEN(TRIM(result!$B$4))>0,ISLOGICAL(result!$B$5),result!$B$5=TRUE,('+bad+')=0)'
    show='AND('+ready+','+fields['_service_first']+'=1)'
    raw=fields['_service_raw'];maximum='MAX('+rng('_service_raw')+')'
    names=['ranked_service_id','ranked_service_risk_raw','ranked_service_risk','competition_rank']
    for name,value in zip(names,[service,raw,'IF('+maximum+'=0,0,100*'+raw+'/'+maximum+')','1+COUNTIF('+rng('_service_raw')+',">"&'+raw+')']):helper(name,'IFERROR(IF('+show+','+value+',""),NA())')
    return {'columns':columns,'helpers':helpers,'outputs':{'service_count':'=IF('+ready+',SUM('+rng('_service_first')+'),NA())',
        'selected_records':'='+ns,'invalid_records':'='+bad},'params':['scope','ps','pe','segment','complete'],
        'extra_params':{'B4':['segment_id','all'],'B5':['population_complete',False]},'result_start':8,
        'tabular_outputs':{name:fields[name].split('{')[0].replace('$','') for name in names},
        'note':'Ranking rows are the four named helper columns on data; filter nonblank ranked_service_id and sort by competition_rank then case-sensitive service ID. Empty complete population has zero services and no ranks. Invalid or unverified input blocks the ranking.'}
