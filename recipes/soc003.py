# SPDX-License-Identifier: MIT
"""SOC-003 execution contract. UTC snapshot; one incident per scope/incident_id.

P50 is the arithmetic median; P90 is exact nearest rank. Every output has its
own valid and invalid counts. An invalid pair prevents that output's KPI from
being published; it does not silently shrink the denominator. Open stock is
measured immediately before period_end. No source completeness is inferred.
"""
import inspect
import math

PAIRS = {'mttr': ('detected_at', 'resolved_at'),
         'mtta': ('alert_at', 'ack_at'), 'mttc': ('detected_at', 'contained_at')}
VERSION = '1.0.0-draft'


def compute(records, period_start, period_end, scope_id):
    import pandas as pd
    import math
    pairs = {'mttr': ('detected_at', 'resolved_at'),
             'mtta': ('alert_at', 'ack_at'), 'mttc': ('detected_at', 'contained_at')}
    ps, pe = pd.to_datetime(period_start, utc=True), pd.to_datetime(period_end, utc=True)
    if pd.isna(ps) or pd.isna(pe) or ps >= pe or not str(scope_id).strip():
        raise ValueError('A nonempty scope and an increasing UTC period are required')
    required = {'scope_id', 'incident_id', 'evidence_ref'} | {f for p in pairs.values() for f in p}
    if not required <= set(records.columns):
        raise ValueError('Missing required SOC-003 columns: ' + ', '.join(sorted(required-set(records.columns))))
    rows = records.loc[records.scope_id == scope_id].copy()
    for f in {f for p in pairs.values() for f in p}:
        rows[f] = pd.to_datetime(rows[f], utc=True, errors='raise', format='mixed')
    closed = (rows.resolved_at >= ps) & (rows.resolved_at < pe)
    stock = (rows.detected_at < pe) & (rows.resolved_at.isna() | (rows.resolved_at >= pe))
    relevant = closed | stock
    identity_bad = int((relevant & (
        rows.incident_id.fillna('').astype(str).str.strip().eq('') |
        rows.evidence_ref.fillna('').astype(str).str.strip().eq('') |
        rows.incident_id.fillna('').astype(str).str.lower().duplicated(keep=False))).sum())
    result = {'closed_cases': int(closed.sum()), 'identity_errors': identity_bad,
              'open_cases_at_period_end': None if identity_bad else int(stock.sum())}
    for name, (start, end) in pairs.items():
        valid = closed & rows[start].notna() & rows[end].notna() & (rows[end] >= rows[start]) & (rows[end] <= rows.resolved_at)
        values = sorted(((rows.loc[valid, end]-rows.loc[valid, start]).dt.total_seconds()/3600).tolist())
        n, invalid = len(values), int((closed & ~valid).sum())
        status = 'invalid_data' if identity_bad or invalid else ('ok' if n else 'not_applicable')
        result.update({name+'_valid_cases': n, name+'_invalid_cases': invalid, name+'_status': status,
                       name+'_p50_h': (values[(n-1)//2]+values[n//2])/2 if status == 'ok' else None,
                       name+'_p90_h': values[math.ceil(.9*n)-1] if status == 'ok' else None,
                       name+'_mean_h_supplementary': math.fsum(values)/n if status == 'ok' else None})
    return result


def sql(dialect='gsql'):
    fragments, outputs = [], []
    for name, (a,b) in PAIRS.items():
        valid = f'closed_case AND {a} IS NOT NULL AND {b} IS NOT NULL AND {b} >= {a} AND {b} <= resolved_at'
        elapsed = f'EXTRACT(EPOCH FROM ({b}-{a}))/3600.0' if dialect == 'pg' else f"date_diff('microsecond', {a}, {b})/3600000000.0"
        fragments += [f'CASE WHEN {valid} THEN {elapsed} END AS {name}_h', f'CASE WHEN closed_case AND NOT COALESCE(({valid}), FALSE) THEN 1 ELSE 0 END AS {name}_bad']
        bad = f'SUM({name}_bad)>0 OR COALESCE(SUM(identity_bad),0)>0'
        n = f'COUNT({name}_h)'
        outputs += [f'{n} AS {name}_valid_cases', f'COALESCE(SUM({name}_bad),0) AS {name}_invalid_cases',
                    f"CASE WHEN {bad} THEN 'invalid_data' WHEN {n}=0 THEN 'not_applicable' ELSE 'ok' END AS {name}_status"]
        for key, agg in [('p50_h',f'percentile_cont(0.5) WITHIN GROUP (ORDER BY {name}_h)'),('p90_h',f'percentile_disc(0.9) WITHIN GROUP (ORDER BY {name}_h)'),('mean_h_supplementary',f'AVG({name}_h)')]:
            outputs.append(f'CASE WHEN {bad} THEN NULL ELSE {agg} END AS {name}_{key}')
    return '''-- SOC-003; typed UTC timestamps; bind :period_start, :period_end, :scope_id.
-- Validate period_start < period_end before query execution.
WITH scoped AS (
 SELECT *, COUNT(*) OVER (PARTITION BY LOWER(incident_id)) AS identity_count
 FROM incidents WHERE scope_id = :scope_id
), base AS (
 SELECT *, COALESCE(resolved_at >= :period_start AND resolved_at < :period_end, FALSE) AS closed_case,
 COALESCE(detected_at < :period_end AND (resolved_at IS NULL OR resolved_at >= :period_end), FALSE) AS open_case
 FROM scoped
), measured AS (
 SELECT *, CASE WHEN (closed_case OR open_case) AND
 (NULLIF(TRIM(incident_id),'') IS NULL OR NULLIF(TRIM(evidence_ref),'') IS NULL OR identity_count <> 1)
 THEN 1 ELSE 0 END AS identity_bad,
 ''' + ',\n '.join(fragments) + ''' FROM base
)
SELECT COALESCE(SUM(CASE WHEN closed_case THEN 1 ELSE 0 END),0) AS closed_cases,
 COALESCE(SUM(identity_bad),0) AS identity_errors,
 CASE WHEN COALESCE(SUM(identity_bad),0)>0 THEN NULL ELSE COALESCE(SUM(CASE WHEN open_case THEN 1 ELSE 0 END),0) END AS open_cases_at_period_end,
 ''' + ',\n '.join(outputs) + '\nFROM measured;'


def excel_spec(cols):
    from xlsx_dialect import LETTER, _rng
    cm = {f: '$'+LETTER(i+1)+'{r}' for i,f in enumerate(cols)}
    helpers = []
    def add(name, form):
        helpers.append((name,form));return LETTER(len(cols)+len(helpers))
    selected_scope = add('selected_scope', f'=IF(EXACT({cm["scope_id"]},result!$B$1),1,0)')
    closed = add('closed_case', f'=IF(AND(EXACT({cm["scope_id"]},result!$B$1),ISNUMBER({cm["resolved_at"]}),{cm["resolved_at"]}>=result!$B$2,{cm["resolved_at"]}<result!$B$3),1,0)')
    stock = add('open_case', f'=IF(AND(EXACT({cm["scope_id"]},result!$B$1),ISNUMBER({cm["detected_at"]}),{cm["detected_at"]}<result!$B$3,OR({cm["resolved_at"]}="",{cm["resolved_at"]}>=result!$B$3)),1,0)')
    idrange = _rng(cm['incident_id'].replace('$','').replace('{r}',''))
    scrange = _rng(selected_scope)
    idcriteria = 'SUBSTITUTE(SUBSTITUTE(SUBSTITUTE('+cm['incident_id']+',"~","~~"),"*","~*"),"?","~?")'
    badid = add('identity_bad', '=IF(AND(OR('+closed+'{r}=1,'+stock+'{r}=1),OR(TRIM('+cm['incident_id']+')="",TRIM('+cm['evidence_ref']+')="",COUNTIFS('+idrange+','+idcriteria+','+scrange+',1)<>1)),1,0)')
    out = {'closed_cases':'=SUM('+_rng(closed)+')', 'identity_errors':'=SUM('+_rng(badid)+')',
           'open_cases_at_period_end':'=IF(SUM('+_rng(badid)+')>0,NA(),SUM('+_rng(stock)+'))'}
    for name,(a,b) in PAIRS.items():
        cond = f'AND({closed}{{r}}=1,ISNUMBER({cm[a]}),ISNUMBER({cm[b]}),{cm[b]}>={cm[a]},{cm[b]}<={cm["resolved_at"]})'
        val = add(name+'_h', f'=IF({cond},({cm[b]}-{cm[a]})*24,"")')
        bad = add(name+'_bad',f'=IF(AND({closed}{{r}}=1,NOT(ISNUMBER({val}{{r}}))),1,0)')
        v, invalid = _rng(val), _rng(bad)
        out[name+'_valid_cases'] = f'=COUNT({v})'
        out[name+'_invalid_cases'] = f'=SUM({invalid})'
        for key,agg in [('p50_h',f'MEDIAN({v})'),('p90_h',f'SMALL({v},CEILING(0.9*COUNT({v}),1))'),('mean_h_supplementary',f'AVERAGE({v})')]:
            out[name+'_'+key] = f'=IF(OR(SUM({_rng(badid)})>0,SUM({invalid})>0,COUNT({v})=0),NA(),{agg})'
    return {'columns':cols,'params':['scope','ps','pe'],'helpers':helpers,'outputs':out,
            'note':'UTC timestamps. Resolved cohort [start,end); open stock immediately before end. One incident per ID. Each duration rejects missing/negative/after-resolution pairs; retain invalid counts. Numeric cells are n/a on invalid input. Risk-appetite and source-confidence gates apply separately.'}


def kql():
    lines = ['// SOC-003; UTC datetime columns. Validate p_start < p_end.',
             'let p_start = datetime(2026-06-01); let p_end = datetime(2026-07-01); let scope = "prod";',
             'let scoped = incidents | where scope_id == scope | extend identity_key=tolower(incident_id);',
             'let ids = scoped | summarize identity_count=count() by identity_key;',
             'scoped | join kind=leftouter ids on identity_key',
             '| extend closed_case = isnotnull(resolved_at) and resolved_at >= p_start and resolved_at < p_end, open_case = isnotnull(detected_at) and detected_at < p_end and (isnull(resolved_at) or resolved_at >= p_end)',
             '| extend identity_bad = (closed_case or open_case) and (isempty(trim(@"\\s+",incident_id)) or isempty(trim(@"\\s+",evidence_ref)) or identity_count != 1)']
    aggs = ['closed_cases=countif(closed_case)','identity_errors=countif(identity_bad)','open_count=countif(open_case)']
    for name,(a,b) in PAIRS.items():
        lines.append(f'| extend {name}_h = iff(closed_case and isnotnull({a}) and isnotnull({b}) and {b} >= {a} and {b} <= resolved_at, ({b}-{a})/1h, real(null))')
        aggs.extend([f'{name}_arr=make_list({name}_h,1048576)',f'{name}_valid_cases=countif(isnotnull({name}_h))',f'{name}_invalid_cases=countif(closed_case and isnull({name}_h))',f'{name}_mean_raw=avg({name}_h)'])
    lines.append('| summarize '+', '.join(aggs))
    lines.append('| extend open_cases_at_period_end=iff(identity_errors>0,long(null),open_count)')
    fields=['closed_cases','identity_errors','open_cases_at_period_end']
    for name in PAIRS:
        n=f'{name}_valid_cases';s=f'{name}_sorted'
        lines.append(f'| extend {s}=array_sort_asc({name}_arr)')
        lines.append(f'| extend {name}_status=case(identity_errors>0 or {name}_invalid_cases>0,"invalid_data",array_length({s})!={n},"capacity_exceeded",{n}==0,"not_applicable","ok")')
        ok = f'{name}_status == "ok"'
        lines.append(f'| extend {name}_p50_h=iff({ok},(todouble({s}[toint(ceiling(0.5*{n}))-1])+todouble({s}[toint(0.5*{n})]))/2.0,real(null)), {name}_p90_h=iff({ok},todouble({s}[toint(ceiling(0.9*{n}))-1]),real(null)), {name}_mean_h_supplementary=iff({ok},{name}_mean_raw,real(null))')
        fields += [name+'_'+k for k in ['valid_cases','invalid_cases','status','p50_h','p90_h','mean_h_supplementary']]
    lines.append('| project '+', '.join(fields))
    return '\n'.join(lines)


def spl():
    lines = ['``` SOC-003; timestamps are UTC epoch seconds. Bind and validate period and scope tokens. ```',
             'index=security_incidents sourcetype=incident scope_id=$scope_id$',
             '| where scope_id=$scope_id$',
             '| eval identity_key=lower(incident_id)',
             '| eventstats count AS identity_count BY identity_key',
             '| eval closed_case=if(isnotnull(resolved_at) AND resolved_at >= $period_start$ AND resolved_at < $period_end$,1,0), open_case=if(isnotnull(detected_at) AND detected_at < $period_end$ AND (isnull(resolved_at) OR resolved_at >= $period_end$),1,0)',
             '| eval identity_bad=if((closed_case=1 OR open_case=1) AND (isnull(incident_id) OR len(trim(incident_id))=0 OR isnull(evidence_ref) OR len(trim(evidence_ref))=0 OR identity_count!=1),1,0)',
             '| eventstats sum(closed_case) AS closed_cases sum(open_case) AS open_count sum(identity_bad) AS identity_errors']
    for name,(a,b) in PAIRS.items():
        lines += [f'| eval {name}_h=if(closed_case=1 AND isnotnull({a}) AND isnotnull({b}) AND {b}>={a} AND {b}<=resolved_at,({b}-{a})/3600,null())',
                  f'| eval {name}_bad=if(closed_case=1 AND isnull({name}_h),1,0)',
                  f'| sort 0 {name}_h',
                  f'| streamstats count({name}_h) AS {name}_rank',
                  f'| eventstats count({name}_h) AS {name}_valid_cases sum({name}_bad) AS {name}_invalid_cases avg({name}_h) AS {name}_mean_raw',
                  f'| eval {name}_lo=if({name}_rank=ceiling(0.5*{name}_valid_cases),{name}_h,null()), {name}_hi=if({name}_rank=floor(0.5*{name}_valid_cases)+1,{name}_h,null()), {name}_tail=if({name}_rank=ceiling(0.9*{name}_valid_cases),{name}_h,null())',
                  f'| eventstats max({name}_lo) AS {name}_p50_lo max({name}_hi) AS {name}_p50_hi max({name}_tail) AS {name}_p90_raw']
    fields=['closed_cases','open_count','identity_errors']+[n+'_'+s for n in PAIRS for s in ['valid_cases','invalid_cases','mean_raw','p50_lo','p50_hi','p90_raw']]
    lines.append('| stats '+', '.join(f'max({f}) AS {f}' for f in fields))
    lines.append('| fillnull value=0 closed_cases identity_errors open_count '+' '.join(n+'_'+s for n in PAIRS for s in ['valid_cases','invalid_cases']))
    lines.append('| eval open_cases_at_period_end=if(identity_errors>0,null(),open_count)')
    fields=['closed_cases','open_cases_at_period_end','identity_errors']
    for n in PAIRS:
        lines.append(f'| eval {n}_status=case(identity_errors>0 OR {n}_invalid_cases>0,"invalid_data",{n}_valid_cases=0,"not_applicable",true(),"ok")')
        lines.append(f'| eval {n}_p50_h=if({n}_status="ok",({n}_p50_lo+{n}_p50_hi)/2,null()), {n}_p90_h=if({n}_status="ok",{n}_p90_raw,null()), {n}_mean_h_supplementary=if({n}_status="ok",{n}_mean_raw,null())')
        fields.extend(n+'_'+s for s in ['valid_cases','invalid_cases','status','p50_h','p90_h','mean_h_supplementary'])
    lines.append('| fields '+', '.join(fields))
    return '\n'.join(lines)


def dax():
    # Complete measure definitions: import UTC DateTime columns into Incidents;
    # select exactly one disconnected Scope and ReportingPeriod row.
    lines=['// SOC-003. Measures for Incidents and disconnected Scope/ReportingPeriod tables.',
           '// Scope[scope_id]; ReportingPeriod[period_start], [period_end]. UTC DateTime columns.',
           '// ALL(Incidents) intentionally removes implicit visual filters; scope/period remain explicit.']
    scope='SELECTEDVALUE(Scope[scope_id])'
    base=f'FILTER(ALL(Incidents),EXACT(Incidents[scope_id],{scope}))'
    params='VAR ps=SELECTEDVALUE(ReportingPeriod[period_start])\nVAR pe=SELECTEDVALUE(ReportingPeriod[period_end])\nVAR sc=SELECTEDVALUE(Scope[scope_id])'
    guard='ISBLANK(ps) || ISBLANK(pe) || ps>=pe || ISBLANK(sc)'
    relevant='(NOT ISBLANK(Incidents[resolved_at]) && Incidents[resolved_at]>=ps && Incidents[resolved_at]<pe) || (NOT ISBLANK(Incidents[detected_at]) && Incidents[detected_at]<pe && (ISBLANK(Incidents[resolved_at]) || Incidents[resolved_at]>=pe))'
    lines += [f'SOC003 Identity Errors :=\n{params}\nVAR scoped={base}\nVAR relevant=FILTER(scoped,{relevant})\nVAR bad=FILTER(relevant,VAR iid=Incidents[incident_id] RETURN LEN(TRIM(iid))=0 || LEN(TRIM(Incidents[evidence_ref]))=0 || COUNTROWS(FILTER(scoped,LOWER(Incidents[incident_id])=LOWER(iid)))<>1)\nRETURN IF({guard},BLANK(),COUNTROWS(bad)+0)']
    for name,(a,b) in PAIRS.items():
        local=f'''{params}
VAR cohort=FILTER({base},NOT ISBLANK(Incidents[resolved_at]) && Incidents[resolved_at]>=ps && Incidents[resolved_at]<pe)
VAR valid=FILTER(cohort,NOT ISBLANK(Incidents[{a}]) && NOT ISBLANK(Incidents[{b}]) && Incidents[{b}]>=Incidents[{a}] && Incidents[{b}]<=Incidents[resolved_at])
VAR n=COUNTROWS(valid)+0
VAR bad=(COUNTROWS(cohort)+0)-n
VAR durations=ADDCOLUMNS(valid,"@h",(Incidents[{b}]-Incidents[{a}])*24.0)'''
        expressions={'Valid Cases':'n','Invalid Cases':'bad','P50 h':'MEDIANX(durations,[@h])','P90 h':'MAXX(TOPN(ROUNDUP(0.9*n,0),durations,[@h],ASC),[@h])','Mean h supplementary':'AVERAGEX(durations,[@h])'}
        for label,expr in expressions.items():
            g=guard if label.endswith('Cases') else guard+' || [SOC003 Identity Errors]>0 || bad>0 || n=0'
            lines.append(f'SOC003 {name.upper()} {label} :=\n{local}\nRETURN IF({g},BLANK(),{expr})')
    lines.append(f'SOC003 Closed Cases :=\n{params}\nRETURN IF({guard},BLANK(),COUNTROWS(FILTER({base},NOT ISBLANK(Incidents[resolved_at]) && Incidents[resolved_at]>=ps && Incidents[resolved_at]<pe))+0)')
    lines.append(f'SOC003 Open Cases at Period End :=\n{params}\nRETURN IF({guard} || [SOC003 Identity Errors]>0,BLANK(),COUNTROWS(FILTER({base},NOT ISBLANK(Incidents[detected_at]) && Incidents[detected_at]<pe && (ISBLANK(Incidents[resolved_at]) || Incidents[resolved_at]>=pe)))+0)')
    from dax_profiles import query
    outputs = {'identity_errors':'SOC003 Identity Errors','closed_cases':'SOC003 Closed Cases','open_cases_at_period_end':'SOC003 Open Cases at Period End'}
    for n in PAIRS:
        for suffix,label in [('valid_cases','Valid Cases'),('invalid_cases','Invalid Cases'),('p50_h','P50 h'),('p90_h','P90 h'),('mean_h_supplementary','Mean h supplementary')]:
            outputs[n+'_'+suffix] = 'SOC003 '+n.upper()+' '+label
    return query('\n\n'.join(lines),'Incidents',outputs)


def snippets(cols):
    from xlsx_dialect import render
    return {'py':inspect.getsource(compute), 'gsql':sql(), 'pg':sql('pg'),
            'kql':kql(), 'spl':spl(), 'dax':dax(), 'xlsx':render('SOC-003',excel_spec(cols))}
