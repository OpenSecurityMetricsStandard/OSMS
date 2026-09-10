# SPDX-License-Identifier: MIT
"""Typed, inspectable calculation plans for the remaining OSMS card families.

Plans describe prepared observations and numerical outputs. A source adapter must
establish the card's population; a calculation plan does not attest that source.
"""
import datetime as dt
import hashlib
import json
import math
import statistics

VERSION='semantic-inputs/1'
COMMON={
    'card_id':{'type':'string'},'card_version':{'type':'string'},
    'contract_hash':{'type':'string'},'scope_id':{'type':'string'},
    'period_start':{'type':'timestamp'},'period_end':{'type':'timestamp'},
    'record_id':{'type':'string'},'evidence_ref':{'type':'string'},
    'source_system':{'type':'string'},'source_snapshot_hash':{'type':'string'},
    'segment_id':{'type':'string'},
}

def field(name):return {'field':name}
def stat(name):return {'stat':name}
def op(name,*args):return [name,*args]
def add(*args):return op('add',*args)
def mul(*args):return op('mul',*args)
def sub(a,b):return op('sub',a,b)
def div(a,b):return op('div',a,b)
def choose(c,a,b):return op('if',c,a,b)
def clip(a,lo=0,hi=100):return op('max',lo,op('min',hi,a))
def weighted(terms):return add(*(mul(w,field(f)) for f,w in terms.items()))
def number(lo=0,hi=1e15,nullable=False,integer=False,enum=None):
    return {'type':'number','minimum':lo,'maximum':hi,'nullable':nullable,'integer':integer,
            **({'enum':list(enum)} if enum is not None else {})}
def text(enum=None,nullable=False):
    return {'type':'string','nullable':nullable,**({'enum':list(enum)} if enum else {})}
def timestamp(nullable=False):return {'type':'timestamp','nullable':nullable}

def plan(card,inputs,stats,outputs,*,derived=None,row_constraints=None,aggregate_constraints=None,
         single=False,empty='not_applicable',segments=None,note='',output_units=None,primary_outputs=None,
         identity_fields=None,empty_outputs=None):
    """The formula and population stay bound to the published card version."""
    p={'card_id':card['id'],'card_version':card['card_version'],'profile_version':VERSION,
       'stage':'prepared_observations','inputs':{**COMMON,**inputs},'derived':derived or {},
       'statistics':stats,'outputs':outputs,'row_constraints':row_constraints or [],
       'aggregate_constraints':aggregate_constraints or [],'single_record':single,
       'empty':empty,'segments':segments or ['all'],'note':note,
       'empty_outputs':empty_outputs or {},
       'primary_outputs':primary_outputs or (['value'] if 'value' in outputs else [k for k in outputs if (output_units or {}).get(k)!='count']),
       'identity_fields':identity_fields or ['record_id'],
       'constant_fields':[k for k in inputs if k.endswith('_version') or k in ('currency','joint_scenario_set_hash')],
       'definition':{k:card[k] for k in ('formula','unit','reproducibility','numerator_denominator','special_cases_gates','target_thresholds')},
       'source_adapter_status':'requires_population_and_evidence_validation',
       'output_contracts':{k:{'unit':(output_units or {}).get(k,card['unit']),
           'nullable':True,'absolute_tolerance':0 if (output_units or {}).get(k)=='count' else 1e-8,
           'relative_tolerance':0 if (output_units or {}).get(k)=='count' else 1e-12} for k in outputs}}
    p['contract_hash']=hashlib.sha256(json.dumps(p,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
    return p

def instant(value):
    if value is None:return None
    if isinstance(value,dt.date) and not isinstance(value,dt.datetime):value=dt.datetime.combine(value,dt.time())
    if isinstance(value,str):value=dt.datetime.fromisoformat(value.replace('Z','+00:00'))
    if not isinstance(value,dt.datetime):raise ValueError('Expected an ISO timestamp or datetime')
    # An unqualified timestamp is a declared UTC timestamp, not local time.
    return value.replace(tzinfo=dt.timezone.utc) if value.tzinfo is None else value.astimezone(dt.timezone.utc)

def evaluate(expr,row=None,stats=None):
    if isinstance(expr,dict):return (row or {}).get(expr['field']) if 'field' in expr else (stats or {}).get(expr['stat'])
    if not isinstance(expr,list):return expr
    name,*args=expr
    if name=='if':return evaluate(args[1] if evaluate(args[0],row,stats) is True else args[2],row,stats)
    vals=[evaluate(a,row,stats) for a in args]
    if name=='present':return vals[0] is not None
    if name=='coalesce':return next((v for v in vals if v is not None),None)
    if name=='and':return all(v is True for v in vals)
    if name=='or':return any(v is True for v in vals)
    if name=='not':return vals[0] is not True
    if any(v is None for v in vals):return None
    if name=='eq':return vals[0]==vals[1]
    if name=='ne':return vals[0]!=vals[1]
    if name=='lt':return vals[0]<vals[1]
    if name=='le':return vals[0]<=vals[1]
    if name=='gt':return vals[0]>vals[1]
    if name=='ge':return vals[0]>=vals[1]
    if name=='add':return math.fsum(vals)
    if name=='mul':return math.prod(vals)
    if name=='sub':return vals[0]-vals[1]
    if name=='div':return vals[0]/vals[1] if vals[1]!=0 else None
    if name=='abs':return abs(vals[0])
    if name=='min':return min(vals)
    if name=='max':return max(vals)
    if name=='sqrt':return math.sqrt(vals[0]) if vals[0]>=0 else None
    if name in ('hours','days','minutes'):
        return (instant(vals[0])-instant(vals[1])).total_seconds()/({'hours':3600,'days':86400,'minutes':60}[name])
    raise ValueError('Unknown plan operation: '+name)

def valid(value,schema):
    if value is None:return bool(schema.get('nullable'))
    if schema['type']=='timestamp':
        try:instant(value);return True
        except (ValueError,TypeError,OverflowError):return False
    if schema['type']=='string':
        return isinstance(value,str) and bool(value.strip()) and ('enum' not in schema or value in schema['enum'])
    if schema['type']=='boolean':return isinstance(value,bool)
    if schema['type']=='number':
        return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and schema.get('minimum',-1e15)<=value<=schema.get('maximum',1e15) and (not schema.get('integer') or value==math.floor(value)) and ('enum' not in schema or value in schema['enum'])
    raise ValueError('Unknown plan input type')

def summarize(method,values,q=None):
    values=[v for v in values if v is not None]
    if method=='count':return len(values)
    if method=='sum':return math.fsum(values) if values else 0.0
    if not values:return None
    if method=='mean':return math.fsum(values)/len(values)
    if method=='max':return max(values)
    if method=='min':return min(values)
    if method=='median':return statistics.median(values)
    if method=='quantile':return sorted(values)[math.ceil(q*len(values))-1]
    if method=='stddev_population':return statistics.pstdev(values)
    raise ValueError('Unknown aggregate: '+method)

def rank_services(records):
    services={}
    for row in records:
        key=row['business_service_id']
        factors=(row['service_criticality'],row['dependency_factor'])
        if key in services and services[key]['factors']!=factors:
            raise ValueError('Conflicting service factors')
        service=services.setdefault(key,{'factors':factors,'risks':[]})
        service['risks'].append(row['asset_risk'])
    raw={key:math.fsum(v['risks'])*math.prod(v['factors']) for key,v in services.items()}
    maximum=max(raw.values())
    return [{'business_service_id':key,'service_risk_raw':raw[key],
             'service_risk':100*raw[key]/maximum if maximum else 0.,
             'competition_rank':1+sum(v>raw[key] for v in raw.values())}
            for key in sorted(raw,key=lambda key:(-raw[key],key))]

def compute(p,records,params):
    outputs={k:None for k in p['outputs']}
    base={'outputs':outputs,'evaluation_status':'invalid_input','selected_records':0,'invalid_records':0,
          'card_id':p['card_id'],'card_version':p['card_version'],'profile_version':p['profile_version']}
    try:
        ps,pe=instant(params['period_start']),instant(params['period_end'])
        scope=params['scope_id'];segment=params.get('segment_id','all')
        if not ps or not pe or ps>=pe or not isinstance(scope,str) or not scope.strip() or not isinstance(segment,str) or not segment.strip():return base
        if params.get('population_complete') is not True:
            return {**base,'evaluation_status':'population_unverified'}
    except (KeyError,ValueError,TypeError):return base
    selected=[]
    for record in records:
        if record.get('card_id')!=p['card_id'] or record.get('scope_id')!=scope or record.get('segment_id')!=segment:continue
        try:
            if instant(record.get('period_start'))!=ps or instant(record.get('period_end'))!=pe:continue
        except (ValueError,TypeError):
            base['invalid_records']+=1;continue
        selected.append(dict(record))
    base['selected_records']=len(selected)
    if not selected:
        if base['invalid_records']:return base
        return {**base,'evaluation_status':p['empty'],'outputs':{k:p.get('empty_outputs',{}).get(k,0.0 if p['empty']=='ok' else None) for k in outputs}}
    identities=[tuple(str(r.get(k)).lower() for k in p['identity_fields']) for r in selected]
    identity_bad=len(identities)!=len(set(identities))
    for row in selected:
        bad=not all(valid(row.get(k),s) for k,s in p['inputs'].items())
        bad|=row.get('card_version')!=p['card_version'] or row.get('contract_hash')!=p['contract_hash']
        if bad:base['invalid_records']+=1;continue
        for k,s in p['inputs'].items():
            if s['type']=='timestamp':row[k]=instant(row[k])
        for name,expr in p['derived'].items():row[name]=evaluate(expr,row)
        if any(evaluate(expr,row) is not True for expr in p['row_constraints']):base['invalid_records']+=1
    if base['invalid_records'] or identity_bad or p['single_record'] and len(selected)!=1:return base
    if any(len({r[k] for r in selected})!=1 for k in p.get('constant_fields',[])):return base
    if p.get('grouping')=='service_ranking':
        try:ranked=rank_services(selected)
        except ValueError:return base
        return {**base,'evaluation_status':'ok','outputs':{'services':ranked,'service_count':len(ranked)}}
    aggregates={}
    for name,s in p['statistics'].items():
        values=[evaluate(s['expr'],row) for row in selected if 'where' not in s or evaluate(s['where'],row) is True]
        aggregates[name]=summarize(s['method'],values,s.get('q'))
    if any(evaluate(expr,stats=aggregates) is not True for expr in p['aggregate_constraints']):return base
    results={k:evaluate(expr,stats=aggregates) for k,expr in p['outputs'].items()}
    if any(isinstance(v,(int,float)) and not isinstance(v,bool) and not math.isfinite(v) for v in results.values()):return base
    primary=[results[k] for k in p['primary_outputs'] or list(results)]
    status='ok' if all(v is not None for v in primary) else 'partial' if any(v is not None for v in primary) else 'not_applicable'
    return {**base,'outputs':results,'evaluation_status':status}

def aggregate(method,expr,q=None,where=None):
    return {'method':method,'expr':expr,**({'q':q} if q is not None else {}),**({'where':where} if where is not None else {})}
