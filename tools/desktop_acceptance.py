#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Plan or verify complete native Excel/DAX fixture evidence, never emulate it."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'recipes/ci'),str(ROOT/'recipes')]
from desktop_runner import expected_cases, fixture_hash
from semantic_runner import equal

AUDIT_CARDS={'SOC-002','APP-010','CFG-002','SOC-078','STD-055','STD-069','STD-068','STD-075'}


def case_plan(bundle, scope='all'):
    wanted=AUDIT_CARDS if scope=='audit-critical' else set(bundle['profiles'])
    if wanted-set(bundle['profiles']):raise ValueError('Missing required audit card')
    result={}
    for cid,pid,p,c,semantic in expected_cases(bundle,wanted):
        name=c['name'] if semantic else c['case_id'];key=(cid,pid,name)
        if key in result:raise ValueError('Duplicate independent fixture ID')
        result[key]={'fixture_sha256':fixture_hash(c),'expected':c['expected'] if semantic else c['expect'],
            'expected_status':c.get('status'),'contracts':p['plan']['output_contracts'] if semantic else p['contract']['outputs']}
    return result


def verify(report,bundle,bundle_hash,engine,scope='all'):
    expected=case_plan(bundle,scope);errors=[];actual={}
    if report.get('profile_bundle_sha256')!=bundle_hash:errors.append('stale_bundle')
    if report.get('source_files_sha256')!=bundle.get('source_files_sha256'):errors.append('source_binding_mismatch')
    if report.get('engine')!=engine or report.get('execution_kind')!='native_desktop':errors.append('wrong_engine_or_execution_kind')
    if report.get('stage')!='typed_calculation_profiles' or not report.get('engine_version'):errors.append('missing_stage_or_version')
    if report.get('aborted') is not False:errors.append('aborted_or_unspecified_run')
    try:
        start=datetime.fromisoformat(report['started_at']);end=datetime.fromisoformat(report['completed_at'])
        if start.tzinfo is None or end.tzinfo is None or not start<=end<=datetime.now(timezone.utc):raise ValueError()
    except (KeyError,TypeError,ValueError):errors.append('invalid_execution_interval')
    rows=report.get('cases',[])
    if not isinstance(rows,list):rows=[];errors.append('invalid_cases')
    for row in rows:
        key=tuple(row.get(k) for k in ('card_id','profile_id','case_id'))
        if key in actual:errors.append('duplicate_case:'+str(key))
        actual[key]=row
        if row.get('status')!='pass' or row.get('failed_outputs') or row.get('error'):errors.append('failed_case:'+str(key))
    if report.get('failed')!=0 or report.get('passed')!=len(rows):errors.append('counter_mismatch')
    missing=set(expected)-set(actual)
    errors.extend('missing_case:'+str(k) for k in sorted(missing))
    if scope=='all':errors.extend('unknown_case:'+str(k) for k in sorted(set(actual)-set(expected)))
    for key in expected.keys() & actual.keys():
        plan=expected[key];row=actual[key];outputs=row.get('actual',{})
        if row.get('fixture_sha256')!=plan['fixture_sha256']:errors.append('changed_fixture:'+str(key))
        if set(row.get('outputs',[]))!=set(plan['expected']):errors.append('output_coverage:'+str(key))
        for name,value in plan['expected'].items():
            if name not in outputs or not equal(outputs[name],value,plan['contracts'].get(name)):
                errors.append('wrong_output:'+str(key)+':'+name)
        # Excel expresses rejection through #N/A; its numeric output oracle is
        # required above. DAX additionally exposes the explicit status string.
        if engine=='dax' and plan['expected_status'] and outputs.get('evaluation_status')!=plan['expected_status']:
            errors.append('wrong_evaluation_status:'+str(key))
    return {'engine':engine,'scope':scope,'ok':not errors,'errors':errors,'required_cases':len(expected),
        'observed_cases':len(actual),'required_cards':len({k[0] for k in expected}),
        'profile_bundle_sha256':bundle_hash,'board_approval':False,
        'notice':'Evidence consistency and fixture-output verification only. Retain the original native execution record and actual verifier; this does not authenticate its author or prove production/capacity conformity.'}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--bundle',default='recipes/out');ap.add_argument('--out',required=True)
    ap.add_argument('--scope',choices=['all','audit-critical'],default='all');ap.add_argument('--plan-only',action='store_true')
    ap.add_argument('--engine',choices=['excel','dax']);ap.add_argument('--report');a=ap.parse_args()
    data=Path(a.bundle,'execution-profiles.json').read_bytes();bundle=json.loads(data);sha=hashlib.sha256(data).hexdigest()
    for name,expected in bundle['source_files_sha256'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=expected:ap.error('Stale source bundle: '+name)
    if a.plan_only:
        rows=case_plan(bundle,a.scope)
        result={'kind':'unexecuted_native_test_plan','scope':a.scope,'profile_bundle_sha256':sha,
            'native_pass':False,'required_cases':len(rows),'required_cards':len({k[0] for k in rows}),
            'cases':[dict(card_id=k[0],profile_id=k[1],case_id=k[2],**v) for k,v in rows.items()]}
    else:
        if not a.engine or not a.report:ap.error('Verification requires --engine and --report')
        raw=Path(a.report).read_bytes();result=verify(json.loads(raw),bundle,sha,a.engine,a.scope)
        result['report_sha256']=hashlib.sha256(raw).hexdigest()
    Path(a.out).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(result['required_cases'],'required cases;',result.get('ok','not executed'))
    return 0 if a.plan_only or result['ok'] else 1


if __name__=='__main__':raise SystemExit(main())
