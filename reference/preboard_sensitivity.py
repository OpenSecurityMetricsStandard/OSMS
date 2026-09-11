#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independent sensitivity examples; local risk appetite remains a decision."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
import yaml
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'recipes'),str(ROOT/'recipes/ci')]
from semantic.registry import register
from semantic.cases import examples
from semantic.model import compute
from semantic.check import duckdb_compute
from semantic_runner import equal
from assurance import normalize


def run():
    plans=register(yaml.safe_load((ROOT/'catalog/osms-catalog.yaml').read_text(encoding='utf-8'))['cards'])
    fixtures=examples(plans);results=[]
    def verify(cid,label,c,expected):
        for engine,fn in (('python',compute),('duckdb',duckdb_compute)):
            actual=fn(plans[cid],c['rows'],c['params'])
            if actual['evaluation_status']!='ok' or not all(k in actual['outputs'] and equal(actual['outputs'][k],v,plans[cid]['output_contracts'][k]) for k,v in expected.items()):
                raise AssertionError((cid,label,engine,expected,actual))
            results.append({'card_id':cid,'case_id':label,'engine':engine,'expected':expected,'actual':actual['outputs'],'status':'pass'})
    base=fixtures['STD-006'][0]
    # Independent weighted-mean counterfactuals, keeping the full case population.
    # Use explicit data instead of relying on the default fixture's scores.
    base=copy.deepcopy(base)
    base['rows']=[dict(base['rows'][0],record_id=str(i),effectiveness_score=s,criticality_weight=w) for i,(s,w) in enumerate(((80,2),(60,1),(70,1)))]
    verify('STD-006','baseline_unequal_weights',base,{'value':72.5})
    c=copy.deepcopy(base);c['rows'][0]['effectiveness_score']=90
    verify('STD-006','increase_critical_control_by_10',c,{'value':77.5})
    c=copy.deepcopy(base);c['rows'][1]['criticality_weight']=2
    verify('STD-006','increase_weaker_control_weight',c,{'value':70})
    c=copy.deepcopy(fixtures['STD-003'][0])
    for row in c['rows']:row.update(asset_risk=0)
    ids=sorted({r['business_service_id'] for r in c['rows']})
    verify('STD-003','all_zero_full_population_ties',c,{'services':[{'business_service_id':k,'service_risk_raw':0,'service_risk':0,'competition_rank':1} for k in ids],'service_count':len(ids)})
    # 24h target and 48h red are explicit illustrative anchors, not new defaults.
    profile=dict(profile_id='sensitivity-example',profile_version='1',card_id='SOC-003',card_version=plans['STD-006']['card_version'],
                 output_id='mttr_p90_h',unit='hours',evidence_ref='synthetic:anchors',direction='lower',target=24,red=48)
    for raw,expected in ((23.999,100),(24,100),(24.001,99.99583333333334),(36,50),(47.999,0.004166666666656956),(48,0),(48.001,0)):
        out=normalize(raw,profile)['posture_score']
        if abs(out-expected)>1e-9:raise AssertionError((raw,out,expected))
        results.append({'card_id':'SOC-003','case_id':'explicit_illustrative_anchors/'+str(raw),'engine':'python','expected':expected,'actual':out,'status':'pass'})
    return {'evidence_class':'synthetic_sensitivity','production_calibration':False,
            'source_catalog_sha256':hashlib.sha256((ROOT/'catalog/osms-catalog.yaml').read_bytes()).hexdigest(),'cases':results,'passed':len(results)}

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',required=True);a=ap.parse_args()
    r=run();Path(a.out).write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8');print(r['passed'],'sensitivity checks passed')
