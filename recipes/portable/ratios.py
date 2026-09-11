# SPDX-License-Identifier: MIT
"""Calculation-input profiles for literal catalog quotients, not source adapters.

Each selected row contains both named, reconciled measures for one card/scope/
period. These implementations do not count raw events or prove source coverage.
"""
import re
import json
import hashlib
from pathlib import Path

PATTERN = re.compile(r'^\(?\s*([A-Za-z_][A-Za-z0-9_]*)\s*/\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)?\s*(\*\s*100)?\s*$')
DIALECTS = ('py','gsql','pg','kql','spl','esql','xlsx','dax')
# Explicit exceptions, not an inference that every quotient is a proportion.
KINDS = {'HRM-004':'general_ratio','STD-005':'unit_cost','STD-076':'unit_cost',
         'STD-073':'general_ratio','SOC-063':'capacity_ratio','SOC-065':'event_rate'}
COLUMNS = ['card_id','card_version','contract_hash','scope_id','period_start','period_end',
           'numerator_name','denominator_name','numerator','denominator',
           'numerator_evidence_ref','denominator_evidence_ref','source_system','source_snapshot_hash']


def contract(card):
    m = PATTERN.fullmatch(card['formula'].strip())
    if not m:return None
    kind = KINDS.get(card['id'],'proportion')
    if kind == 'proportion' and not m.group(3):
        raise ValueError('Unclassified unscaled quotient: '+card['id'])
    definition = {k:card[k] for k in ('formula','reproducibility','special_cases_gates','unit','card_version',
        'numerator_denominator','scope','direction','minimum_data_fields','data_confidence',
        'confidence_production_rule','target_thresholds','decision_chain','version_break_rule')}
    digest=hashlib.sha256(json.dumps(definition,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    return {'card_id':card['id'],'card_version':card['card_version'],'profile_version':'1.0.0-draft',
            'contract_hash':digest,'kind':kind,'numerator_min':-1e15 if card['id'] in ('STD-005','STD-076','STD-073') else 0,'scale':100 if m.group(3) else 1,
            'numerator_name':m.group(1),'denominator_name':m.group(2),'unit':card['unit'],
            'stage':'calculation_inputs','input_table':'metric_inputs','columns':COLUMNS,
            'input_numeric_domain':'Finite numbers; numerator_min <= numerator <= 1e15; denominator = 0 or 1e-12 <= denominator <= 1e15. Convert and document units before evaluation if outside this representable profile.',
            'population_contract':card['reproducibility'],'additional_gates':card['special_cases_gates'],
            'source_adapter_status':'required','green_eligibility':'not_assessed',
            'outputs':{'value':{'unit':card['unit'],'nullable':True,'absolute_tolerance':1e-9,'relative_tolerance':1e-12},
                       'evaluation_status':{'type':'enum','values':['ok','not_applicable','invalid_input','missing_input']}},
            'verification':{d:'not_run' for d in DIALECTS}}


def python_code(c):
    return '''# Calculation inputs only. Bind typed UTC period parameters before calling.
import math
from datetime import datetime, timezone
CONTRACT = '''+repr({k:c[k] for k in ['card_id','card_version','contract_hash','numerator_name','denominator_name','kind','numerator_min','scale']})+'''
def compute(rows, period_start, period_end, scope_id):
    def timestamp(value):
        dt = datetime.fromisoformat(str(value).replace('Z','+00:00'))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    if timestamp(period_start) >= timestamp(period_end) or not isinstance(scope_id,str) or not scope_id.strip():
        raise ValueError('Invalid scope or period')
    chosen = [r for r in rows if r.get('card_id')==CONTRACT['card_id'] and r.get('scope_id')==scope_id and timestamp(r.get('period_start'))==timestamp(period_start) and timestamp(r.get('period_end'))==timestamp(period_end)]
    if not chosen:return {'value':None,'evaluation_status':'missing_input'}
    bad = {'value':None,'evaluation_status':'invalid_input'}
    if len(chosen)!=1:return bad
    row=chosen[0]
    if any(row.get(k)!=CONTRACT[k] for k in ('card_version','contract_hash','numerator_name','denominator_name')):return bad
    if any(not isinstance(row.get(k),str) or not row[k].strip() for k in ('numerator_evidence_ref','denominator_evidence_ref','source_system','source_snapshot_hash')):return bad
    a,b=row.get('numerator'),row.get('denominator')
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in (a,b)):return bad
    if not CONTRACT['numerator_min']<=a<=1e15 or not (b==0 or 1e-12<=b<=1e15):return bad
    if CONTRACT['kind']=='proportion' and a>b:return bad
    return {'value':CONTRACT['scale']*(a/b) if b else None,'evaluation_status':'ok' if b else 'not_applicable'}
'''


def sql_code(c,pg=False):
    stringbad=' OR '.join(f"{k} IS NULL OR {k}<>'{c[k]}'" for k in ['card_version','contract_hash','numerator_name','denominator_name'])
    refs=' OR '.join(f"NULLIF(TRIM({k}),'') IS NULL" for k in ['numerator_evidence_ref','denominator_evidence_ref','source_system','source_snapshot_hash'])
    numeric=f'numerator IS NULL OR denominator IS NULL OR NOT (numerator>={c["numerator_min"]} AND numerator<=1e15) OR NOT (denominator=0 OR (denominator>=1e-12 AND denominator<=1e15))'
    if c['kind']=='proportion':numeric+=' OR numerator>denominator'
    return f'''-- {c['card_id']}: canonical measures, not raw-event selection. Typed UTC period.
WITH selected AS (
 SELECT *, CASE WHEN {stringbad} OR {refs} OR {numeric} THEN 1 ELSE 0 END AS bad
 FROM metric_inputs WHERE card_id='{c['card_id']}' AND scope_id=:scope_id
 AND period_start=:period_start AND period_end=:period_end
), reduced AS (
 SELECT COUNT(*) AS n, COALESCE(SUM(bad),0) AS bad, MAX(numerator) AS a, MAX(denominator) AS b FROM selected
)
SELECT CASE WHEN :period_start < :period_end AND NULLIF(TRIM(:scope_id),'') IS NOT NULL AND n=1 AND bad=0 AND b>0 THEN {c['scale']}.0*(a/b) ELSE NULL END AS value,
 CASE WHEN :period_start IS NULL OR :period_end IS NULL OR NOT (:period_start < :period_end) OR NULLIF(TRIM(:scope_id),'') IS NULL THEN 'invalid_input' WHEN n=0 THEN 'missing_input' WHEN n<>1 OR bad>0 THEN 'invalid_input' WHEN b=0 THEN 'not_applicable' ELSE 'ok' END AS evaluation_status
FROM reduced;'''


def kql_code(c):
    terms=[f'{k} != "{c[k]}"' for k in ['card_version','contract_hash','numerator_name','denominator_name']]
    terms += [f'NotUsed' ] if False else []
    terms += [f'isempty(trim(@"\\s+",{k}))' for k in ['numerator_evidence_ref','denominator_evidence_ref','source_system','source_snapshot_hash']]
    terms += ['isnull(numerator)','isnull(denominator)','not(isfinite(numerator))','not(isfinite(denominator))',f'numerator<{c["numerator_min"]}','numerator>1e15','not(denominator==0 or (denominator>=1e-12 and denominator<=1e15))']
    if c['kind']=='proportion':terms+=['numerator>denominator']
    return f'''// {c['card_id']}: canonical measures; typed UTC columns, not source-event selection.
let p_start=datetime(2026-06-01); let p_end=datetime(2026-07-01); let scope="prod";
metric_inputs | where card_id=="{c['card_id']}" and scope_id==scope and period_start==p_start and period_end==p_end
| summarize n=count(), bad=countif({' or '.join(terms)}), a=max(numerator), b=max(denominator)
| extend evaluation_status=case(isnull(p_start) or isnull(p_end) or p_start>=p_end or isempty(trim(@"\\s+",scope)),"invalid_input",n==0,"missing_input",n!=1 or bad>0,"invalid_input",b==0,"not_applicable","ok")
| project value=iff(evaluation_status=="ok",{c['scale']}.0*(a/b),real(null)), evaluation_status'''


def spl_code(c):
    terms=[f'isnull({k}) OR {k}!="{c[k]}"' for k in ['card_version','contract_hash','numerator_name','denominator_name']]
    terms += [f'isnull({k}) OR len(trim({k}))=0' for k in ['numerator_evidence_ref','denominator_evidence_ref','source_system','source_snapshot_hash']]
    terms += ['isnull(a)','isnull(b)',f'NOT (a>={c["numerator_min"]} AND a<=1e15)','NOT (b=0 OR (b>=1e-12 AND b<=1e15))']
    if c['kind']=='proportion':terms+=['a>b']
    return f'''``` {c['card_id']}: canonical measures; period fields and tokens are UTC epoch seconds. ```
index=osms sourcetype=metric_inputs card_id="{c['card_id']}" scope_id=$scope_id$
| where card_id="{c['card_id']}" AND scope_id=$scope_id$ AND period_start=$period_start$ AND period_end=$period_end$
| eval a=tonumber(numerator), b=tonumber(denominator)
| eval invalid=if({' OR '.join(terms)},1,0)
| stats count AS n sum(invalid) AS bad max(a) AS a max(b) AS b
| eval evaluation_status=case($period_start$ >= $period_end$,"invalid_input",n=0,"missing_input",n!=1 OR bad>0,"invalid_input",b=0,"not_applicable",true(),"ok")
| eval value=if(evaluation_status="ok",{c['scale']}*(a/b),null())
| fields value, evaluation_status'''


def esql_code(c):
    terms=[f'{k} IS NULL OR {k}!="{c[k]}"' for k in ['card_version','contract_hash','numerator_name','denominator_name']]
    terms += [f'{k} IS NULL OR TRIM({k})==""' for k in ['numerator_evidence_ref','denominator_evidence_ref','source_system','source_snapshot_hash']]
    terms += ['numerator IS NULL','denominator IS NULL',f'NOT (numerator>={c["numerator_min"]} AND numerator<=1e15)','NOT (denominator==0 OR (denominator>=1e-12 AND denominator<=1e15))']
    if c['kind']=='proportion':terms+=['numerator>denominator']
    return f'''// {c['card_id']}: canonical measures; all text columns keyword, measures double, period columns date.
FROM metric_inputs
| WHERE card_id=="{c['card_id']}" AND scope_id==?scope_id AND period_start==?period_start AND period_end==?period_end
| EVAL invalid=CASE({' OR '.join(terms)},1,0)
| STATS n=COUNT(*), bad=SUM(invalid), a=MAX(numerator), b=MAX(denominator)
| EVAL evaluation_status=CASE(?period_start>=?period_end OR TRIM(?scope_id)=="","invalid_input",n==0,"missing_input",n!=1 OR bad>0,"invalid_input",b==0,"not_applicable","ok")
| EVAL value=CASE(evaluation_status=="ok",{c['scale']}.0*(a/b),TO_DOUBLE(NULL))
| KEEP value,evaluation_status
| LIMIT 1'''


def excel_spec(c):
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    from xlsx_dialect import LETTER,_rng
    col={k:'$'+LETTER(i+1)+'{r}' for i,k in enumerate(COLUMNS)}
    terms=[f'EXACT({col[k]},"{c[k]}")' for k in ['card_version','contract_hash','numerator_name','denominator_name']]
    terms += [f'TRIM({col[k]})<>""' for k in ['numerator_evidence_ref','denominator_evidence_ref','source_system','source_snapshot_hash']]
    a,b=col['numerator'],col['denominator']
    terms += [f'ISNUMBER({a})',f'ISNUMBER({b})',f'{a}>={c["numerator_min"]}',f'{a}<=1000000000000000',f'OR({b}=0,AND({b}>=0.000000000001,{b}<=1000000000000000))']
    if c['kind']=='proportion':terms+=[f'{a}<={b}']
    # Each helper is row-local; match counts cannot hide duplicate input snapshots.
    helpers=[('selected',f'=IF(AND(EXACT({col["card_id"]},"{c["card_id"]}"),EXACT({col["scope_id"]},result!$B$1),{col["period_start"]}=result!$B$2,{col["period_end"]}=result!$B$3),1,0)'),
             ('valid','=IF(AND(O{r}=1,'+','.join(terms)+'),1,0)'),
             ('a','=IF(P{r}=1,'+a+',0)'),('b','=IF(P{r}=1,'+b+',0)')]
    # n=1 and valid=1 prevents invalid rows and duplicates producing a result.
    n='SUM('+_rng('O')+')';good='SUM('+_rng('P')+')';aa='SUM('+_rng('Q')+')';bb='SUM('+_rng('R')+')'
    params='AND(ISNUMBER($B$2),ISNUMBER($B$3),$B$2<$B$3,TRIM($B$1)<>"")'
    output=f'=IF(AND({params},{n}=1,{good}=1,{bb}>0),{c["scale"]}*({aa}/{bb}),NA())'
    return {'columns':COLUMNS,'params':['scope','ps','pe'],'helpers':helpers,
            'outputs':{'value':output,'parameter_valid':'=IF('+params+',1,0)','selected_rows':'='+n,'valid_rows':'='+good,'numerator':'='+aa,'denominator':'='+bb},
            'note':'Calculation inputs only; no source selection. selected_rows=0: missing_input; selected_rows or valid_rows not 1: invalid_input; valid zero denominator: not_applicable. See contract for population, dimensions and additional reporting gates.'}


def dax_code(c):
    from dax_profiles import query
    terms=[f'EXACT(MetricInputs[{k}],"{c[k]}")' for k in ['card_version','contract_hash','numerator_name','denominator_name']]
    terms += [f'LEN(TRIM(MetricInputs[{k}]))>0' for k in ['numerator_evidence_ref','denominator_evidence_ref','source_system','source_snapshot_hash']]
    a,b='MetricInputs[numerator]','MetricInputs[denominator]'
    terms += [f'NOT ISBLANK({a})',f'NOT ISBLANK({b})',f'{a}>={c["numerator_min"]}',f'{a}<=1000000000000000',f'({b}=0 || ({b}>=1e-12 && {b}<=1e15))']
    if c['kind']=='proportion':terms+=[f'{a}<={b}']
    prefix=f'''VAR ps=SELECTEDVALUE(ReportingPeriod[period_start])
VAR pe=SELECTEDVALUE(ReportingPeriod[period_end])
VAR sc=SELECTEDVALUE(Scope[scope_id])
VAR selected=FILTER(ALL(MetricInputs),EXACT(MetricInputs[card_id],"{c['card_id']}") && EXACT(MetricInputs[scope_id],sc) && MetricInputs[period_start]=ps && MetricInputs[period_end]=pe)
VAR valid=FILTER(selected,{' && '.join(terms)})
VAR n=COUNTROWS(selected)+0
VAR nv=COUNTROWS(valid)+0
VAR a=MAXX(valid,MetricInputs[numerator])
VAR b=MAXX(valid,MetricInputs[denominator])
VAR invalidParams=ISBLANK(ps) || ISBLANK(pe) || ps>=pe || ISBLANK(sc)'''
    name=c['card_id'].replace('-','')
    text = f'''// Canonical measures in MetricInputs. Double measures; UTC DateTime period columns.
// Disconnected Scope[scope_id] and ReportingPeriod[period_start],[period_end]; select exactly one.
{name} Value :=
{prefix}
RETURN IF(invalidParams || n<>1 || nv<>1 || b=0,BLANK(),{c['scale']}.0*DIVIDE(a,b))

{name} Evaluation Status :=
{prefix}
RETURN SWITCH(TRUE(),invalidParams,"invalid_input",n=0,"missing_input",n<>1 || nv<>1,"invalid_input",b=0,"not_applicable","ok")'''

    return query(text,'MetricInputs',{'value':name+' Value','evaluation_status':name+' Evaluation Status'})


def generate(cards):
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    from xlsx_dialect import render
    result={}
    for card in cards:
        c=contract(card)
        if c is None:continue
        spec=excel_spec(c)
        result[card['id']]={'contract':c,'dialects':{'py':python_code(c),'gsql':sql_code(c),'pg':sql_code(c,True),
            'kql':kql_code(c),'spl':spl_code(c),'esql':esql_code(c),'xlsx':render(card['id'],spec),'dax':dax_code(c)},'excel_spec':spec}
    return result
