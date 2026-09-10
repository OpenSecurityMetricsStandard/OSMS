# SPDX-License-Identifier: MIT
"""Exact ES|QL export/Python reduction with count, snapshot and warning checks."""
import hashlib
import json
from .model import compute

def protocol(plan):
    prefix='FROM osms_input | WHERE card_id == '+json.dumps(plan['card_id'])+' AND scope_id == ?scope_id AND segment_id == ?segment_id AND period_start == ?period_start AND period_end == ?period_end'
    return {'execution_mode':'esql_export_python_exact_reducer','queries':{
        'count':prefix+' | STATS source_rows=COUNT(*)',
        'rows':prefix+' | KEEP '+', '.join(plan['inputs'])+' | LIMIT 10000'},
        'reducer':'recipes/semantic/esql.py:reduce_export','native_percentile_claim':False,
        'requirements':'Both responses must refer to one immutable source snapshot. Reporting period fields use native dates with millisecond-aligned boundaries. Other business timestamps are preserved as ISO UTC keyword strings so the reducer retains submillisecond precision. Bind native UTC reporting datetime parameters; reject warnings, partial results, schema drift, missing/duplicate columns and count mismatch. Maximum 10000 records. Numeric outputs and rankings use the typed plan in the Python reducer.'}

def reduce_export(plan,count_response,rows_response,params,*,snapshot_hash):
    from .model import instant
    if any(instant(params[k]).microsecond%1000 for k in ('period_start','period_end')):raise ValueError('ES date transport requires millisecond-aligned reporting boundaries')
    if not isinstance(snapshot_hash,str) or len(snapshot_hash)!=64 or any(c not in '0123456789abcdef' for c in snapshot_hash):raise ValueError('Immutable SHA-256 snapshot identity required')
    for response in [count_response,rows_response]:
        if response.get('is_partial') or response.get('warnings') or response.get('error') or response.get('timed_out'):raise ValueError('Partial or warned export')
        clusters=response.get('_clusters',{})
        if any(clusters.get(k,0) for k in ['failed','skipped','partial','running']):raise ValueError('Incomplete cross-cluster export')
    if [c.get('name') for c in count_response.get('columns',[])]!=['source_rows']:raise ValueError('Invalid count schema')
    values=count_response.get('values')
    if not isinstance(values,list) or len(values)!=1 or len(values[0])!=1:raise ValueError('Invalid count result')
    n=values[0][0]
    if not isinstance(n,int) or isinstance(n,bool) or not 0<=n<=10000:raise ValueError('Export capacity exceeded or invalid count')
    columns=[c.get('name') for c in rows_response.get('columns',[])]
    if len(columns)!=len(set(columns)) or set(columns)!=set(plan['inputs']):raise ValueError('Export schema drift')
    values=rows_response.get('values')
    if not isinstance(values,list) or len(values)!=n or any(len(r)!=len(columns) for r in values):raise ValueError('Export count/shape mismatch')
    rows=[dict(zip(columns,r)) for r in values]
    output=compute(plan,rows,params)
    if output['selected_records']!=n:raise ValueError('Rows do not match the counted reporting population')
    return {'result':output,'export_snapshot_sha256':snapshot_hash,
            'export_response_sha256':hashlib.sha256(json.dumps(rows_response,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()}
