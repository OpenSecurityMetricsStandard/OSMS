#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build source-bound, per-card review dossiers without manufacturing approvals."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile
import yaml

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'recipes'),str(ROOT/'tools')]
from framework_mappings import inventory
from portable.cases import cases as ratio_cases


def digest(data):return hashlib.sha256(data).hexdigest()


def symbols(expr,kind):
    if isinstance(expr,dict):
        return ({expr[kind]} if kind in expr else set()).union(*(symbols(v,kind) for v in expr.values()))
    if isinstance(expr,list):return set().union(*(symbols(v,kind) for v in expr))
    return set()


def inspect_card(card,profile_id,profile):
    errors=[];p=profile.get('plan');contract=profile['contract']
    if contract['card_id']!=card['id'] or contract['card_version']!=card['card_version']:
        errors.append('profile_identity_mismatch')
    if p:
        known=set(p['inputs'])
        for name,e in p['derived'].items():
            if symbols(e,'field')-known:errors.append('unbound_derived_input:'+name)
            known.add(name)
        for name,e in p['statistics'].items():
            if symbols(e,'field')-known:errors.append('unbound_statistic_input:'+name)
        if symbols(p['outputs'],'stat')-set(p['statistics']):errors.append('unbound_output_statistic')
        expected=set().union(*(set(c['expected']) for c in profile['fixtures']))
        if set(p['outputs'])-expected:errors.append('outputs_without_independent_oracle')
        if set(p['outputs'])!=set(contract['outputs']):errors.append('output_contract_mismatch')
    for name,spec in contract['outputs'].items():
        if name=='evaluation_status':continue
        if spec.get('type')=='array':
            if not spec.get('items'):errors.append('missing_array_item_contract:'+name)
            continue
        if not spec.get('unit'):errors.append('missing_output_unit:'+name)
        if spec.get('absolute_tolerance',-1)<0 or spec.get('relative_tolerance',-1)<0:
            errors.append('invalid_tolerance:'+name)
    for name in ('management_question','accountable_owner','decision_chain','guardrails','reproducibility'):
        if not card.get(name):errors.append('missing_decision_contract:'+name)
    declared=set(profile.get('dialects',{}))
    if 'esql_protocol' in profile:declared.add('esql')
    if declared!=set(('py','gsql','pg','kql','spl','esql','xlsx','dax')):
        errors.append('missing_or_unknown_dialect')
    return errors


def build(bundle_path,out):
    bundle_path=Path(bundle_path);out=Path(out);out.mkdir(parents=True,exist_ok=True)
    data=(bundle_path/'execution-profiles.json').read_bytes();bundle=json.loads(data)
    for name,expected in bundle['source_files_sha256'].items():
        if digest((ROOT/name).read_bytes())!=expected:raise ValueError('Stale source bundle: '+name)
    cards=yaml.safe_load((ROOT/'catalog/osms-catalog.yaml').read_text(encoding='utf-8'))['cards']
    reviews=yaml.safe_load((ROOT/'catalog/framework-mapping-reviews.yaml').read_text(encoding='utf-8'))['reviews']
    mappings=inventory(cards,reviews);rows=[];errors=[]
    manifest={'bundle_sha256':digest(data),'catalog_sha256':digest((ROOT/'catalog/osms-catalog.yaml').read_bytes()),
              'generation_is_review_approval':False,'cards':rows}
    matrix_path=bundle_path/'conformance-matrix.json'
    evidence=json.loads(matrix_path.read_text(encoding='utf-8')) if matrix_path.exists() else None
    if evidence and evidence.get('profile_bundle_sha256')!=digest(data):raise ValueError('Stale evidence matrix')
    for card in cards:
        cid=card['id'];profiles=bundle['profiles'][cid]
        checks=[e for pid,p in profiles.items() for e in inspect_card(card,pid,p)]
        errors.extend(cid+':'+e for e in checks)
        row={'card_id':cid,'card_version':card['card_version'],'priority':card['priority'],
             'source_card_sha256':digest(json.dumps(card,ensure_ascii=False,sort_keys=True).encode()),
             'structural_binding_status':'fail' if checks else 'pass','errors':checks,
             'semantic_review_status':'requires_independent_review','reviewer':None,'decision':None,
             'profile_ids':list(profiles),'management_question':card['management_question'],
             'decision_chain':card['decision_chain'],
             'mapping_ids':[r['mapping_id'] for r in mappings['mappings'] if r['card_id']==cid]}
        rows.append(row)
        text=[f'# {cid} — {card["name"]}',f'Card version: {card["card_version"]}; priority: {card["priority"]}.',
              'This dossier assembles evidence. Its existence is not an approval.',
              '## Decision and measurement',
              *[f'**{k}**\n\n'+(json.dumps(card[k],ensure_ascii=False,indent=2) if not isinstance(card[k],str) else card[k])
                for k in ('management_question','accountable_owner','definition','formula','unit','numerator_denominator',
                           'reproducibility','special_cases_gates','data_confidence','target_thresholds','decision_chain','guardrails')],
              '## Calculation contracts and independent examples']
        for pid,p in profiles.items():
            fixtures=p.get('fixtures') or (ratio_cases(p['contract']) if pid=='canonical_quotient_v1' else
                json.loads((ROOT/'recipes/fixtures/soc003.json').read_text(encoding='utf-8')))
            text.extend([f'### {pid}','```json',json.dumps({'contract':p['contract'],'examples':fixtures},ensure_ascii=False,indent=2),'```'])
        runs=[r for r in evidence['matrix'] if r['card_id']==cid] if evidence else []
        text.extend(['## Native evidence','```json',json.dumps(runs,indent=2),'```' if runs else '```',
            'Absent evidence is unverified. Calculation input fixtures do not prove a production adapter.',
            '## Questions for the independent reviewer',
            '- Does the selected population answer the management question, including excluded and late cases?',
            '- Do numerator, denominator, units and estimator match the defined output?',
            '- Can missing evidence, changing case mix or duplicated upstream contributions improve the displayed result?',
            '- Are thresholds and normalization anchors appropriate for the declared local risk appetite?',
            '- Which empirical assumptions still need pilot evidence?',
            '## Disposition', 'Reviewer, independence declaration, date, evidence references, decision and rationale: pending actual review.'])
        (out/'cards').mkdir(exist_ok=True);(out/'cards'/f'{cid}.md').write_text('\n\n'.join(text)+'\n',encoding='utf-8')
    manifest['errors']=errors
    (out/'review-matrix.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    by_id={c['id']:c for c in cards}
    for entry in mappings['mappings']:
        c=by_id[entry['card_id']]
        entry['review_material']={'metric_definition':c['definition'],'population':c['reproducibility'],
            'decision':c['decision_chain'],'required_assessment':['edition and exact clause/category',
            'which requirement this observation supports','which requirements it does not establish',
            'source evidence and reviewer rationale']}
    (out/'mapping-review-material.json').write_text(json.dumps(mappings,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    index=['# OSMS pre-board review packet',f'327 cards; {len(mappings["mappings"])} mapping associations.',
           'Read the source-bound review matrix first. Structural PASS is not semantic approval.',
           'The mapping file includes each exact source reference, identifier check and card-specific decision context.',
           '| Card | Priority | Version | Structural binding |','|---|---|---|---|']
    index += [f'| [{r["card_id"]}](cards/{r["card_id"]}.md) | {r["priority"]} | {r["card_version"]} | {r["structural_binding_status"]} |' for r in rows]
    (out/'index.md').write_text('\n\n'.join(index[:4])+'\n\n'+'\n'.join(index[4:])+'\n',encoding='utf-8')
    files={p.relative_to(out).as_posix():digest(p.read_bytes()) for p in sorted(out.rglob('*')) if p.is_file() and p.name!='manifest.json'}
    (out/'manifest.json').write_text(json.dumps({'bundle_sha256':digest(data),'files':files},indent=2)+'\n')
    with zipfile.ZipFile(out.with_suffix('.zip'),'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(out.rglob('*')):
            if p.is_file():z.write(p,p.relative_to(out))
    return manifest


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--bundle',default='recipes/out');ap.add_argument('--out',default='recipes/out/board-packet');a=ap.parse_args()
    r=build(a.bundle,a.out);print(len(r['cards']),'cards;',len(r['errors']),'structural errors')
    if r['errors']:print('\n'.join(r['errors']));raise SystemExit(1)
