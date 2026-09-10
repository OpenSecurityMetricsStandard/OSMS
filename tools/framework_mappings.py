#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Inventory source-bound framework associations and validate explicit reviews."""
import argparse,hashlib,json,re
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[1]

def inventory(cards,reviews):
    entries={}
    for card in cards:
        for reference in card['framework_mapping']:
            key=card['id']+':'+hashlib.sha256(reference.encode()).hexdigest()[:16]
            if key in entries:raise ValueError('Duplicate framework association '+key)
            edition=re.search(r':(20\d{2})\b|\b(?:v|Rev\.?\s*)(\d+(?:\.\d+)*)\b|\bCSF (2\.0)\b',reference)
            entries[key]={'mapping_id':key,'card_id':card['id'],'card_version':card['card_version'],
                'source_reference':reference,'source_reference_sha256':hashlib.sha256(reference.encode()).hexdigest(),
                'edition_stated':next((g for g in edition.groups() if g),None) if edition else None,
                'relationship':'not_assessed','review_status':'unreviewed','rationale':None,'evidence_ref':None,
                'reviewer':None,'decision_date':None,'conformity_claim':False}
    seen=set()
    for review in reviews:
        key=review.get('mapping_id')
        if key not in entries or key in seen:raise ValueError('Unknown or duplicate mapping review '+str(key))
        seen.add(key);entry=entries[key]
        for k in ['card_version','source_reference_sha256']:
            if review.get(k)!=entry[k]:raise ValueError('Stale mapping review '+key+' '+k)
        if review.get('relationship') not in ('supports_measurement_of','partial_support','no_claim'):raise ValueError('Unknown reviewed relationship')
        for k in ['framework','edition','reference','rationale','evidence_ref','reviewer','decision_date']:
            if not isinstance(review.get(k),str) or not review[k].strip():raise ValueError('Missing reviewed mapping field '+k)
        import datetime
        datetime.date.fromisoformat(review['decision_date'])
        if review.get('conformity_claim',False) is not False:raise ValueError('A mapping does not establish conformity')
        entry.update({k:review[k] for k in ['framework','edition','reference','relationship','rationale','evidence_ref','reviewer','decision_date']})
        entry['review_status']='reviewed'
    return {'schema_version':'1.0','conformity_claim':False,'mapping_count':len(entries),
        'reviewed_count':len(seen),'not_assessed_count':len(entries)-len(seen),'mappings':list(entries.values())}

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',required=True);ap.add_argument('--require-reviewed',action='store_true');a=ap.parse_args()
    source=ROOT/'catalog/osms-catalog.yaml';cards=yaml.safe_load(source.read_text())['cards']
    reviews=yaml.safe_load((ROOT/'catalog/framework-mapping-reviews.yaml').read_text())['reviews']
    report=inventory(cards,reviews);report['source_catalog_sha256']=hashlib.sha256(source.read_bytes()).hexdigest()
    Path(a.out).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(str(report['mapping_count'])+' mappings; '+str(report['reviewed_count'])+' reviewed; '+str(report['not_assessed_count'])+' not assessed')
    if a.require_reviewed and report['not_assessed_count']:raise SystemExit(1)
