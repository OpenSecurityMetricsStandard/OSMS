#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Evaluate reconciled binary-outcome pilot snapshots without inventing evidence."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',', ':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def instant(value):
    d=datetime.fromisoformat(value.replace('Z','+00:00'))
    if d.tzinfo is None:raise ValueError('Timestamp requires a timezone')
    return d


def text(record,*keys):
    for k in keys:
        if not isinstance(record.get(k),str) or not record[k].strip():raise ValueError('Missing '+k)


def wilson(success,n):
    if not n:return None
    z=1.959963984540054;p=success/n;den=1+z*z/n
    center=(p+z*z/(2*n))/den;half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [max(0,center-half),min(1,center+half)]


def evaluate(document,catalog_sha256):
    text(document,'pilot_id','scope_id','card_id','output_id','definition_ref','normalization_ref','weight_profile_ref',
         'source_evidence_ref','verifier_record_ref','sampling_rationale')
    if document.get('source_catalog_sha256')!=catalog_sha256:raise ValueError('Stale pilot catalog')
    if document.get('evidence_class') not in ('real_pilot','synthetic_example'):raise ValueError('Declare real or synthetic evidence')
    if document['evidence_class']=='real_pilot' and any(document[k].startswith(('synthetic:','fixture:')) for k in ('source_evidence_ref','verifier_record_ref')):
        raise ValueError('Synthetic references cannot substantiate real-pilot provenance')
    sampling=document.get('population_kind')
    if sampling not in ('census','binomial_sample'):raise ValueError('Declare population model')
    if sampling=='binomial_sample' and document.get('independent_bernoulli_justified') is not True:
        raise ValueError('Binomial intervals require a justified independent sampling model')
    for k in ('minimum_observed_denominator','outcome_maturity_days','late_arrival_days'):
        if type(document.get(k)) is not int or document[k]<0:raise ValueError('Invalid pilot threshold '+k)
    if document['minimum_observed_denominator']<1:raise ValueError('Minimum denominator must be positive')
    snapshots=document.get('snapshots',[])
    if not isinstance(snapshots,list) or len(snapshots)<2:raise ValueError('At least two actual snapshots are required')
    results=[];previous=None;previous_time=None;previous_rows={}
    for snapshot in snapshots:
        text(snapshot,'as_of','source_receipt_ref');as_of=instant(snapshot['as_of'])
        if as_of>datetime.now(timezone.utc):raise ValueError('Future pilot snapshot')
        if previous_time is not None and as_of<=previous_time:raise ValueError('Snapshots must be strictly chronological')
        rows=snapshot.get('rows');receipt=snapshot.get('receipt',{})
        if not isinstance(rows,list) or not rows:raise ValueError('Empty pilot snapshot')
        if receipt.get('complete') is not True or type(receipt.get('record_count')) is not int or receipt.get('record_count')!=len(rows) or receipt.get('rows_sha256')!=digest(rows):
            raise ValueError('Unreconciled source receipt')
        groups={};ids=set();late=0;changed=0;pending_mature=0
        by_id={}
        for row in rows:
            text(row,'record_id','cohort_id','campaign_id','event_at','known_at')
            rid=row['record_id']
            if rid in ids:raise ValueError('Duplicate pilot record')
            ids.add(rid);by_id[rid]=row
            event=instant(row['event_at']);known=instant(row['known_at'])
            if not event<=known<=as_of:raise ValueError('Future knowledge or invalid event order')
            outcome=row.get('outcome')
            if outcome is not None and type(outcome) is not bool:raise ValueError('Only binary outcomes are supported')
            if outcome is None:
                if row.get('outcome_at') is not None:raise ValueError('Pending outcome has a resolved timestamp')
                if (as_of-event).total_seconds()>=86400*document['outcome_maturity_days']:pending_mature+=1
            elif not event<=instant(row['outcome_at'])<=as_of:raise ValueError('Future outcome or invalid outcome order')
            if (known-event).total_seconds()>86400*document['late_arrival_days']:late+=1
            if rid in previous_rows:
                old=previous_rows[rid]
                if any(old.get(k)!=row.get(k) for k in ('event_at','known_at','cohort_id','campaign_id')):
                    raise ValueError('Historical membership changed; declare a new pilot baseline')
                if old.get('outcome') is not None and (old.get('outcome'),old.get('outcome_at'))!=(outcome,row.get('outcome_at')):
                    text(row,'correction_evidence_ref');changed+=1
            key=(row['cohort_id'],row['campaign_id'])
            g=groups.setdefault(key,{'eligible':0,'observed':0,'success':0,'pending':0})
            g['eligible']+=1;g['pending']+=outcome is None;g['observed']+=outcome is not None;g['success']+=outcome is True
        if set(previous_rows)-ids:raise ValueError('Previously eligible cases silently disappeared')
        for g in groups.values():
            g['rate']=g['success']/g['observed'] if g['observed'] else None
            g['interval_95']=wilson(g['success'],g['observed']) if sampling=='binomial_sample' else None
        total={k:sum(g[k] for g in groups.values()) for k in ('eligible','observed','success','pending')}
        total['rate']=total['success']/total['observed'] if total['observed'] else None
        total['interval_95']=wilson(total['success'],total['observed']) if sampling=='binomial_sample' else None
        total['evidence_statement']='below_declared_minimum' if total['observed']<document['minimum_observed_denominator'] else 'meets_declared_minimum_only'
        total.update(late_arrivals=late,mature_pending_outcomes=pending_mature,corrected_outcomes=changed,
            newly_known_records=len(ids-set(previous_rows)) if previous is not None else None)
        comparison=None
        if previous is not None:
            base=previous['groups'];base_n=sum(g['observed'] for g in base.values())
            supported=bool(base_n) and all(k in groups and groups[k]['observed'] for k,g in base.items() if g['observed'])
            standardized=sum(groups[k]['rate']*g['observed']/base_n for k,g in base.items() if g['observed']) if supported else None
            mix_change=sum(abs(groups.get(k,{}).get('eligible',0)/total['eligible']-base.get(k,{}).get('eligible',0)/previous['total']['eligible']) for k in groups.keys()|base.keys())/2
            baseline_rate=previous['total']['rate']
            comparison={'previous_as_of':previous['as_of'],'raw_rate_change':None if baseline_rate is None or total['rate'] is None else total['rate']-baseline_rate,
                'previous_observed_mix_standardized_rate':standardized,
                'standardized_rate_change':None if standardized is None or baseline_rate is None else standardized-baseline_rate,
                'eligible_mix_total_variation':mix_change,'missing_previous_strata':not supported,
                'new_strata':[list(k) for k in groups.keys()-base.keys()],
                'causal_effect_claim':False}
        internal={'as_of':snapshot['as_of'],'groups':groups,'total':total};previous=internal;previous_time=as_of;previous_rows=by_id
        results.append({'as_of':snapshot['as_of'],'source_receipt_ref':snapshot['source_receipt_ref'],'rows_sha256':receipt['rows_sha256'],
            'total':total,'strata':[dict(cohort_id=k[0],campaign_id=k[1],**g) for k,g in sorted(groups.items())],'comparison':comparison})
    return {'schema_version':'1.0','pilot_id':document['pilot_id'],'card_id':document['card_id'],'output_id':document['output_id'],
        'source_catalog_sha256':catalog_sha256,'input_sha256':digest(document),'evidence_class':document['evidence_class'],
        'population_kind':sampling,'snapshots':results,'automatic_finding_closure':False,'board_approval':False,
        'limitations':['Real-pilot provenance and verifier identity require the linked actual records.',
            'Counts, selection, delayed outcomes and mix sensitivity do not prove causal effectiveness or stability across all plausible populations.',
            'No binomial interval for a census; declared minimum basis is a local review criterion, not a universal significance threshold.',
            'Only binary-outcome observations; duration, continuous loss and composite-model pilots require their own estimator contracts.']}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--input',required=True);ap.add_argument('--out',required=True)
    ap.add_argument('--catalog',default='catalog/osms-catalog.yaml');ap.add_argument('--bundle',default='recipes/out');ap.add_argument('--require-real',action='store_true');a=ap.parse_args()
    doc=json.loads(Path(a.input).read_text(encoding='utf-8'));r=evaluate(doc,hashlib.sha256(Path(a.catalog).read_bytes()).hexdigest())
    raw=Path(a.bundle,'execution-profiles.json').read_bytes();bundle=json.loads(raw)
    if bundle['source_files_sha256'].get('catalog/osms-catalog.yaml')!=r['source_catalog_sha256']:ap.error('Stale execution profile catalog')
    profiles=bundle['profiles'].get(doc['card_id'],{})
    if not any(doc['output_id'] in p['contract']['outputs'] for p in profiles.values()):ap.error('Unknown card/output binding')
    r['profile_bundle_sha256']=hashlib.sha256(raw).hexdigest()
    if a.require_real and r['evidence_class']!='real_pilot':raise SystemExit('Synthetic examples cannot satisfy the real-pilot gate')
    Path(a.out).write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(len(r['snapshots']),'snapshots;',r['evidence_class'],'; actual review remains required')


if __name__=='__main__':main()
