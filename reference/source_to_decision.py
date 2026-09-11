#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Executable synthetic source-to-decision examples with reconciled populations.

These adapters illustrate two declared source contracts. They are not connectors
for arbitrary production systems, nor authentication of source attestations.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import yaml

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'recipes'),str(ROOT/'reference')]
from portable.ratios import contract,python_code
from semantic.model import instant
from semantic.registry import register
from semantic.cases import metadata
from semantic.render import PARAMS
from assurance import confidence,CONFIDENCE_WEIGHTS
from execution_store import capture,replay


def snapshot(records,receipt):
    observed=hashlib.sha256(json.dumps(records,sort_keys=True,allow_nan=False).encode()).hexdigest()
    if receipt.get('sha256')!=observed or receipt.get('record_count')!=len(records):
        raise ValueError('Source snapshot/count does not match retained receipt')
    if receipt.get('complete') is not True:raise ValueError('Population not attested complete')
    ids=[r.get('id') for r in records]
    if any(not isinstance(i,str) or not i.strip() for i in ids) or len(ids)!=len(set(ids)):
        raise ValueError('Missing or duplicate source identity')
    return observed


def make_receipt(records):
    return {'sha256':hashlib.sha256(json.dumps(records,sort_keys=True).encode()).hexdigest(),
            'record_count':len(records),'complete':True,'evidence_class':'synthetic_fixture'}


def detection_inputs(card,records,receipt,params):
    source_hash=snapshot(records,receipt);selected=[];excluded=[]
    for r in records:
        if not isinstance(r.get('confirmed'),bool):raise ValueError('Explicit case classification required')
        keep=(r.get('scope_id')==params['scope_id'] and r['confirmed'] and
              instant(params['period_start'])<=instant(r['confirmed_at'])<instant(params['period_end']))
        if not keep:excluded.append(r['id']);continue
        if not r.get('evidence_ref') or r.get('detection_source') not in ('SOC','SIEM','EDR','NDR','TIP','USER','THIRD_PARTY','AUDIT'):
            raise ValueError('Unknown source classification or missing evidence')
        selected.append(r)
    numerator=[r['id'] for r in selected if r['detection_source'] in ('SOC','SIEM','EDR','NDR','TIP')]
    c=contract(card)
    row={k:c[k] for k in ('card_id','card_version','contract_hash','numerator_name','denominator_name')}
    row.update(params,numerator=len(numerator),denominator=len(selected),
        numerator_evidence_ref='synthetic:lineage/numerator',denominator_evidence_ref='synthetic:lineage/denominator',
        source_system='synthetic-incidents',source_snapshot_hash=source_hash)
    ns={};exec(python_code(c),ns)
    result=ns['compute']([row],params['period_start'],params['period_end'],params['scope_id'])
    return {'result':result,'prepared_input':row,'lineage':{'numerator_ids':numerator,
        'denominator_ids':[r['id'] for r in selected],'excluded_ids':excluded},'receipt':receipt}


def examples():
    cards=yaml.safe_load((ROOT/'catalog/osms-catalog.yaml').read_text(encoding='utf-8'))['cards']
    card=next(c for c in cards if c['id']=='SOC-004');params={k:PARAMS[k] for k in ('scope_id','period_start','period_end')}
    records=[{'id':str(i),'scope_id':'prod','confirmed':True,'confirmed_at':'2026-06-15T00:00:00Z',
              'detection_source':source,'evidence_ref':'synthetic:incident/'+str(i)}
             for i,source in enumerate(('SOC','EDR','SIEM','USER'))]
    records += [{**records[0],'id':'other-period','confirmed_at':'2026-07-01T00:00:00Z'},
                {**records[0],'id':'reclassified-test','confirmed':False},
                {**records[0],'id':'other-scope','scope_id':'test'}]
    detection=detection_inputs(card,records,make_receipt(records),params)
    if detection['result']!={'value':75.0,'evaluation_status':'ok'}:raise AssertionError('3/4 oracle')
    dimensions={k:{'passed':10,'eligible':10,'evidence_ref':'synthetic:checks/'+k,
                    'check_definition_version':'example/1','mandatory_failures':[]} for k in CONFIDENCE_WEIGHTS}
    dq=confidence(dimensions,'example/1',reported_card_id=card['id'],reported_card_version=card['card_version'],**params)
    detection['confidence']=dq;detection['band']='amber';detection['decision_context']=card['decision_chain']
    detection['decision_state']='requires_previous_period_to_evaluate_two_amber_trigger'
    damaged=copy.deepcopy(dimensions);damaged['reconciliation_quality']['mandatory_failures']=['source-total-mismatch']
    blocked=confidence(damaged,'example/1',reported_card_id=card['id'],reported_card_version=card['card_version'],**params)
    if blocked['management_green_eligible']:raise AssertionError('Mandatory failure bypass')
    plan=register(cards)['STD-006']
    controls=[{'id':'control-A','passed_checks':8,'eligible_checks':10,'criticality_weight':2},
              {'id':'control-B','passed_checks':6,'eligible_checks':10,'criticality_weight':1},
              {'id':'control-C','passed_checks':7,'eligible_checks':10,'criticality_weight':1}]
    source_hash=snapshot(controls,make_receipt(controls));rows=[]
    for i,r in enumerate(controls):
        rows.append({**metadata(plan,i),'effectiveness_score':100*r['passed_checks']/r['eligible_checks'],
            'criticality_weight':r['criticality_weight'],'weight_profile_version':'osms-reference/0.9.2',
            'evidence_ref':'synthetic:control/'+r['id'],'source_snapshot_hash':source_hash})
    with sqlite3.connect(':memory:') as con:
        receipt=capture(con,'synthetic-control-report',plan,rows,PARAMS)
        restored=replay(con,receipt['report_id'],receipt['manifest_sha256'])
    if restored['result']['outputs']['value']!=72.5:raise AssertionError('(80*2+60+70)/4 oracle')
    return {'evidence_class':'synthetic','production_source_validation':False,
            'detection':detection,'mandatory_failure_example':blocked,
            'control_effectiveness':{'source_records':controls,'prepared_observations':rows,'receipt':receipt,'replay':restored}}

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);a=ap.parse_args()
    result=examples();Path(a.out).write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('Source selection, independent totals, confidence override and historical replay passed')
