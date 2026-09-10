#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Exact SOC duration execution from a sealed ES|QL input export.

The query engine selects typed rows; the shipped Python reducer computes exact
multiset statistics. This is a two-stage ES|QL profile, not a native PERCENTILE
claim. Execute both queries against the same immutable input snapshot. Reject
partial results, warnings, row limits and missing fields before calculation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys


def queries(scope_parameter='?scope_id'):
    fields='incident_id, scope_id, evidence_ref, detected_at, resolved_at, alert_at, ack_at, contained_at'
    return {'count':f'FROM incidents | WHERE scope_id == {scope_parameter} | STATS source_rows=COUNT(*)',
            'rows':f'FROM incidents | WHERE scope_id == {scope_parameter} | KEEP {fields} | LIMIT 10000'}


def decode(response):
    if response.get('is_partial') or response.get('warnings') or response.get('warning'):
        raise ValueError('Partial or warned ES|QL response cannot establish complete input')
    columns=[c['name'] for c in response['columns']]
    if len(columns)!=len(set(columns)):raise ValueError('Duplicate ES|QL output column')
    if any(len(row)!=len(columns) for row in response['values']):raise ValueError('Malformed ES|QL response')
    return [dict(zip(columns,row)) for row in response['values']]


def reduce_export(count_response, rows_response, *, period_start, period_end, scope_id, snapshot_hash):
    import pandas as pd
    from soc003 import compute
    if not isinstance(snapshot_hash,str) or len(snapshot_hash)!=64 or any(c not in '0123456789abcdef' for c in snapshot_hash):
        raise ValueError('Sealed source snapshot SHA-256 is required')
    counts=decode(count_response);rows=decode(rows_response)
    if len(counts)!=1 or not isinstance(counts[0].get('source_rows'),int) or isinstance(counts[0]['source_rows'],bool) or counts[0]['source_rows']<0:
        raise ValueError('One exact source count required')
    if counts[0]['source_rows']!=len(rows):raise ValueError('Truncated or inconsistent ES|QL export; partition the sealed input before evaluation')
    cols=[c['name'] for c in rows_response['columns']]
    if any(row.get('scope_id')!=scope_id for row in rows):raise ValueError('ES|QL export scope mismatch')
    result=compute(pd.DataFrame(rows,columns=cols),period_start,period_end,scope_id)
    return {'card_id':'SOC-003','execution_mode':'esql_export_python_exact_reducer','source_snapshot_hash':snapshot_hash,
            'export_sha256':hashlib.sha256(json.dumps(rows_response,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
            'result':result,'native_esql_percentile_verified':False}


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--count-json',required=True);ap.add_argument('--rows-json',required=True)
    ap.add_argument('--period-start',required=True);ap.add_argument('--period-end',required=True)
    ap.add_argument('--scope-id',required=True);ap.add_argument('--snapshot-hash',required=True)
    ap.add_argument('--out',required=True)
    a=ap.parse_args()
    r=reduce_export(json.loads(Path(a.count_json).read_text()),json.loads(Path(a.rows_json).read_text()),
        period_start=a.period_start,period_end=a.period_end,scope_id=a.scope_id,snapshot_hash=a.snapshot_hash)
    Path(a.out).write_text(json.dumps(r,indent=2,allow_nan=False)+'\n')
