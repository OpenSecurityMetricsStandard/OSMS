#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare retained deployed artifacts with the complete repository contracts.

This validates supplied artifact snapshots and a deployment attestation, not
browser rendering, URL availability or authenticity of the deployment operator.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import yaml
ROOT=Path(__file__).resolve().parents[1]


def verify(catalog,schema,profiles,deployment,expected_commit,bundle):
    errors=[]
    source=yaml.safe_load((ROOT/'catalog/osms-catalog.yaml').read_text(encoding='utf-8'))['cards']
    by_id={c['id']:c for c in source}
    exported=json.loads((Path(bundle)/'catalog.json').read_text(encoding='utf-8'))
    expected_export={c['id']:c for c in exported}
    if not isinstance(catalog,list) or any(not isinstance(c,dict) for c in catalog):raise ValueError('Deployed catalog must be a card list')
    ids=[c.get('id') for c in catalog]
    if len(ids)!=len(set(ids)):errors.append('duplicate_card_identity')
    if set(ids)!=set(by_id):errors.append('catalog_population_mismatch')
    for c in catalog:
        cid=c.get('id')
        if cid not in by_id:continue
        expected=expected_export[cid]
        if any(expected.get(k)!=v for k,v in by_id[cid].items()):errors.append(str(cid)+':stale_local_catalog')
        for key in set(expected)|set(c):
            if key not in c or key not in expected or c[key]!=expected[key]:errors.append(str(cid)+':field_mismatch:'+key)
    if schema!=json.loads((ROOT/'schema/osms-card.schema.json').read_text(encoding='utf-8')):errors.append('schema_mismatch')
    local=json.loads((Path(bundle)/'execution-profiles.json').read_text(encoding='utf-8'))
    if profiles!=local:errors.append('execution_profile_mismatch')
    for name,digest in local['source_files_sha256'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest:errors.append('stale_local_profile:'+name)
    if not re.fullmatch('[0-9a-f]{40}',expected_commit):raise ValueError('Full expected commit SHA required')
    if deployment.get('source_commit')!=expected_commit:errors.append('deployment_commit_mismatch')
    for key in ('catalog_url','schema_url','profiles_url','deployment_evidence_ref'):
        if not isinstance(deployment.get(key),str) or not deployment[key].strip():errors.append('missing_deployment_field:'+key)
    return {'status':'fail' if errors else 'artifact_contracts_match','source_commit':expected_commit,
            'cards':len(catalog),'errors':errors,'live_rendering_verified':False,
            'deployment_authenticity_verified':False,'deployment_attestation':deployment}

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('catalog','schema','profiles','deployment','expected-commit','out'):ap.add_argument('--'+name,required=True)
    ap.add_argument('--bundle',default='recipes/out');a=ap.parse_args()
    r=verify(*(json.loads(Path(getattr(a,n)).read_text(encoding='utf-8')) for n in ('catalog','schema','profiles','deployment')),a.expected_commit,a.bundle)
    Path(a.out).write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8');print(r['status'],len(r['errors']),'mismatches');raise SystemExit(bool(r['errors']))
