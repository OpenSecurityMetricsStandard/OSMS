# SPDX-License-Identifier: MIT
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import yaml
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'recipes'),str(ROOT/'recipes/ci'),str(ROOT/'tools')]
import soc003
from incident_cases import cases as incident_cases
from semantic_runner import equal
from portable.ratios import generate
from portable.cases import cases
from semantic.export import generate as semantic_generate
from semantic.cases import boundaries
from kusto_runner import inline
from desktop_runner import dax_request
from build_board_packet import inspect_card
from verify_website_contract import verify
from partitions import partition

class PreboardAdapters(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cards=yaml.safe_load((ROOT/'catalog/osms-catalog.yaml').read_text(encoding='utf-8'))['cards']
        cls.ratios=generate(cls.cards);cls.semantic=semantic_generate(cls.cards)

    def test_incident_oracles_and_native_request_bindings(self):
        card=next(c for c in self.cards if c['id']=='SOC-003')
        profile={'contract':{'input_table':'incidents'},'dialects':soc003.snippets(card['minimum_data_fields'])}
        for case in incident_cases():
            df=pd.DataFrame(case['rows'],columns=case['fields'])
            actual=soc003.compute(df,**case['params'])
            for k,v in case['expect'].items():self.assertTrue(equal(actual[k],v), (case['case_id'],k,actual[k],v))
            self.assertIn('let incidents=datatable(',inline(profile,case,False))
            request=dax_request(profile,case,False)
            self.assertEqual([t['name'] for t in request['tables']],['Incidents','Scope','ReportingPeriod'])
            self.assertIn('EVALUATE',request['query'])

    def test_native_queries_bind_every_case_including_invalid_inputs(self):
        for cid,p in self.ratios.items():
            for case in cases(p['contract']):
                self.assertIn('datatable(',inline(p,case,False),cid)
                self.assertIn('EVALUATE',dax_request(p,case,False)['query'],cid)
        for cid,p in self.semantic.items():
            for fixture in p['fixtures']:
                for case in boundaries(p['plan'],fixture):
                    self.assertIn('datatable(',inline(p,case,True),cid)
                    self.assertIn('EVALUATE',dax_request(p,case,True)['query'],cid)

    def test_fractional_rank_and_absent_output_cannot_pass(self):
        spec={'type':'array','items':{'competition_rank':'integer'}}
        self.assertFalse(equal([{'competition_rank':1.0000000001}],[{'competition_rank':1}],spec))
        self.assertFalse(equal({}, {'required_output':None}))

    def test_all_spreadsheet_partitions_cover_every_card_once(self):
        for profiles in (self.ratios,self.semantic):
            groups=[partition(list(profiles),str(i)+'/4') for i in range(4)]
            flattened=[cid for group in groups for cid in group]
            self.assertEqual(sorted(flattened),sorted(profiles))
            self.assertEqual(len(flattened),len(set(flattened)))
        with self.assertRaises(ValueError):partition(['A'],'1/2')

    def test_review_dossier_rejects_missing_oracle_or_unbound_input(self):
        card=next(c for c in self.cards if c['id']=='STD-006');p=copy.deepcopy(self.semantic['STD-006'])
        self.assertEqual(inspect_card(card,'prepared_observations_v1',p),[])
        p['fixtures'][0]['expected'].pop('value')
        self.assertIn('outputs_without_independent_oracle',inspect_card(card,'prepared_observations_v1',p))
        p=copy.deepcopy(self.semantic['STD-006']);p['plan']['derived']['bad']={'field':'unknown_input'}
        self.assertIn('unbound_derived_input:bad',inspect_card(card,'prepared_observations_v1',p))

    def test_website_comparison_detects_field_loss_duplicates_and_wrong_version(self):
        catalog=copy.deepcopy(self.cards);schema=json.loads((ROOT/'schema/osms-card.schema.json').read_text())
        profiles={'source_files_sha256':{'catalog/osms-catalog.yaml':hashlib.sha256((ROOT/'catalog/osms-catalog.yaml').read_bytes()).hexdigest()}}
        deployment=dict(source_commit='a'*40,catalog_url='fixture:catalog',schema_url='fixture:schema',profiles_url='fixture:profiles',deployment_evidence_ref='fixture:deployment')
        with tempfile.TemporaryDirectory() as d:
            Path(d,'catalog.json').write_text(json.dumps(catalog));Path(d,'execution-profiles.json').write_text(json.dumps(profiles))
            self.assertEqual(verify(catalog,schema,profiles,deployment,'a'*40,d)['errors'],[])
            changed=copy.deepcopy(catalog);changed[0].pop('data_confidence')
            self.assertTrue(any('data_confidence' in e for e in verify(changed,schema,profiles,deployment,'a'*40,d)['errors']))
            self.assertIn('duplicate_card_identity',verify(catalog+[catalog[0]],schema,profiles,deployment,'a'*40,d)['errors'])
            self.assertIn('deployment_commit_mismatch',verify(catalog,schema,profiles,deployment,'b'*40,d)['errors'])

if __name__=='__main__':unittest.main()
