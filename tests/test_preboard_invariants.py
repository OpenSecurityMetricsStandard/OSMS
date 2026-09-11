# SPDX-License-Identifier: MIT
"""Cross-card invariants and independently specified reporting boundaries."""
import copy
import pathlib
import sys
import unittest
import yaml

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'recipes'),str(ROOT/'recipes/ci'),str(ROOT/'tools')]
from semantic import model,registry,cases,check
from semantic_runner import equal
from portable import ratios
from preboard_mutations import audit


class PreboardInvariants(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cards=yaml.safe_load((ROOT/'catalog/osms-catalog.yaml').read_text(encoding='utf-8'))['cards']
        cls.plans=registry.register(cls.cards);cls.examples=cases.examples(cls.plans)

    def test_all_semantic_outputs_have_an_independent_numeric_or_null_oracle(self):
        for cid,p in self.plans.items():
            observed=set().union(*(set(c['expected']) for c in self.examples[cid]))
            self.assertEqual(set(p['outputs']),observed,cid)
            for c in self.examples[cid]:
                actual=model.compute(p,c['rows'],c['params'])
                for k,v in c['expected'].items():
                    self.assertIn(k,actual['outputs'],cid)
                    self.assertTrue(equal(actual['outputs'][k],v,p['output_contracts'][k]),(cid,c['name'],k))

    def test_every_required_prepared_input_is_actually_required(self):
        for cid,p in self.plans.items():
            c=self.examples[cid][0]
            for field,spec in p['inputs'].items():
                if field in model.COMMON or spec.get('nullable'):continue
                rows=copy.deepcopy(c['rows']);rows[0].pop(field)
                a=model.compute(p,rows,c['params'])
                self.assertEqual(a['evaluation_status'],'invalid_input',(cid,field))
                self.assertTrue(all(v is None for v in a['outputs'].values()),(cid,field))

    def test_row_order_and_excluded_scope_do_not_change_any_output(self):
        for cid,p in self.plans.items():
            for c in self.examples[cid]:
                original=model.compute(p,c['rows'],c['params'])
                rows=list(reversed(c['rows']))
                rows.append({**c['rows'][0],'scope_id':'another-scope','record_id':'unrelated'})
                changed=model.compute(p,rows,c['params'])
                self.assertEqual(original,changed,(cid,c['name']))

    def test_half_open_confirmed_case_population_on_python_and_sql(self):
        cid='AI-003';p=self.plans[cid];base=self.examples[cid][0]
        for timestamp,expected in [('2026-05-31T23:59:59Z',0),('2026-06-01T00:00:00Z',1),
                                   ('2026-06-30T23:59:59Z',1),('2026-07-01T00:00:00Z',0)]:
            c=copy.deepcopy(base);c['rows'][0]['confirmed_at']=timestamp
            for run in (model.compute,check.duckdb_compute):
                a=run(p,c['rows'],c['params'])
                self.assertEqual(a['outputs'],{'value':expected,'regulated_crown_jewel_cases':expected,
                                             'rca_and_control_update_completed_cases':expected})

    def test_critical_seeded_implementation_faults_are_detected(self):
        results=audit(self.cards)
        self.assertGreaterEqual(len(results),837)
        self.assertTrue(all(x['detected'] for x in results))

    def test_quotient_contract_changes_when_population_or_gate_changes(self):
        card=next(c for c in self.cards if ratios.contract(c))
        original=ratios.contract(card)['contract_hash']
        for key in ('numerator_denominator','data_confidence','confidence_production_rule',
                    'target_thresholds','scope','minimum_data_fields','direction','decision_chain'):
            changed=copy.deepcopy(card);changed[key]=str(changed[key])+' changed'
            self.assertNotEqual(original,ratios.contract(changed)['contract_hash'],key)

if __name__=='__main__':unittest.main()
