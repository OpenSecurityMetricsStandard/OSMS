#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Seed consequential implementation faults and require independent tests to fail.

Only in-memory copies are changed. No repository source or expected result is
mutated. A baseline failure is an error, never a killed mutant.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'recipes'),str(ROOT/'recipes/ci')]
import yaml
from portable.ratios import generate
from portable.cases import cases
from semantic.registry import register
from semantic.cases import examples,boundaries
from semantic.model import compute
from semantic_runner import equal


def replace(expr, predicate, replacement):
    if predicate(expr):return replacement
    if isinstance(expr,list):return [replace(x,predicate,replacement) for x in expr]
    if isinstance(expr,dict):return {k:replace(v,predicate,replacement) for k,v in expr.items()}
    return expr


def detects(plan,fixtures):
    for c in fixtures:
        try:
            actual=compute(plan,c['rows'],c['params'])
        except Exception as exc:
            return c['name'],'exception:'+type(exc).__name__
        if c.get('status') and actual['evaluation_status']!=c['status']:
            return c['name'],'status'
        for k,v in c['expected'].items():
            if k not in actual['outputs'] or not equal(actual['outputs'][k],v,plan['output_contracts'].get(k)):
                return c['name'],'output:'+k
    return None,None


def audit(cards):
    report=[];ratios=generate(cards)
    for cid,p in ratios.items():
        fixtures=cases(p['contract']);code=p['dialects']['py']
        def failed(source):
            ns={};exec(source,ns)
            for c in fixtures:
                a=ns['compute'](c['rows'],'2026-06-01','2026-07-01','prod')
                if any(k not in a or not equal(a[k],v,p['contract']['outputs'].get(k)) for k,v in c['expect'].items()):return c['case_id']
            return None
        if failed(code):raise ValueError('Invalid baseline '+cid)
        mutations={'swapped_operands':('CONTRACT[\'scale\']*(a/b)','CONTRACT[\'scale\']*(b/a) if a else None'),
                   'zero_is_measured':("'not_applicable'","'ok'"),
                   'accept_duplicate_snapshot':('if len(chosen)!=1:return bad','if False:return bad'),
                   'skip_contract_binding':("'card_version','contract_hash','numerator_name','denominator_name'","'card_version','numerator_name','denominator_name'")}
        for name,(before,after) in mutations.items():
            if code.count(before)!=1:raise ValueError('Mutation no longer applies '+cid+'/'+name)
            try:case=failed(code.replace(before,after,1));reason='mismatch'
            except Exception as exc:case='fixture execution';reason='exception:'+type(exc).__name__
            report.append({'card_id':cid,'mutation':name,'detected':case is not None,'witness':case,'reason':reason})
    plans=register(cards);fixtures=examples(plans)
    selected=[]
    for cid in ['SOC-002','CFG-002']:
        p=copy.deepcopy(plans[cid]);s=p['statistics']['p50']
        s.update(method='quantile',q=.5) if s['method']=='median' else s.update(method='median')
        selected.append((cid,'wrong_p50_estimator',p))
    p=copy.deepcopy(plans['STD-011'])
    p=replace(p,lambda e:e==['eq',{'field':'mandatory_failures'},0],True)
    selected.append(('STD-011','remove_mandatory_confidence_override',p))
    for cid in ['STD-075','STD-068','STD-069']:
        p=copy.deepcopy(plans[cid]);p['statistics']['value']['expr'][1][1]+=0.1
        selected.append((cid,'changed_fixed_weight',p))
    for cid in ['STD-001','HRM-001']:
        p=copy.deepcopy(plans[cid]);p['statistics']['value']['expr']=0
        selected.append((cid,'plausible_zero_score',p))
    p=copy.deepcopy(plans['VAL-001']);p['statistics']['overall_band']['expr']=0
    selected.append(('VAL-001','force_green_band',p))
    for cid,name,p in selected:
        cs=[c for f in fixtures[cid] for c in boundaries(plans[cid],f)]
        case,why=detects(plans[cid],cs)
        if case:raise ValueError('Invalid baseline '+cid+': '+case+' '+why)
        case,why=detects(p,cs)
        report.append({'card_id':cid,'mutation':name,'detected':case is not None,'witness':case,'reason':why})
    return report


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',default='preboard-mutations.json');a=ap.parse_args()
    path=ROOT/'catalog/osms-catalog.yaml';r=audit(yaml.safe_load(path.read_text(encoding='utf-8'))['cards'])
    report={'scope':'Explicit seeded faults; not exhaustive mutation coverage',
            'catalog_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'mutations':r,'detected':sum(x['detected'] for x in r),'survived':sum(not x['detected'] for x in r)}
    Path(a.out).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(report['detected'],'detected;',report['survived'],'survived')
    return int(bool(report['survived']))

if __name__=='__main__':raise SystemExit(main())
