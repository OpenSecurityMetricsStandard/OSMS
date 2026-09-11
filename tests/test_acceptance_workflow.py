# SPDX-License-Identifier: MIT
"""Synthetic counterexamples for evidence intake, not actual acceptance records."""
import copy
from datetime import date, datetime, timezone
import pathlib
import sys
import unittest
import yaml
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'reference'),str(ROOT/'recipes')]
from desktop_acceptance import case_plan, verify
from portable.ratios import generate
from pilot_evaluation import digest, evaluate as pilot_evaluate
from review_acceptance import evaluate as review_evaluate, GATES


class DesktopAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        card=next(c for c in yaml.safe_load((ROOT/'catalog/osms-catalog.yaml').read_text())['cards'] if c['id']=='AI-001')
        profile=generate([card])['AI-001']
        cls.bundle={'profiles':{'AI-001':{'canonical_quotient_v1':profile}},'source_files_sha256':{'fixture':'a'*64}}
        plan=case_plan(cls.bundle);now=datetime.now(timezone.utc).isoformat()
        cls.report={'engine':'excel','engine_version':'synthetic-checker-fixture','execution_kind':'native_desktop',
            'stage':'typed_calculation_profiles','aborted':False,'started_at':now,'completed_at':now,
            'profile_bundle_sha256':'b'*64,'source_files_sha256':cls.bundle['source_files_sha256'],
            'cases':[dict(card_id=k[0],profile_id=k[1],case_id=k[2],fixture_sha256=p['fixture_sha256'],outputs=list(p['expected']),
                          actual=copy.deepcopy(p['expected']),status='pass',failed_outputs=[]) for k,p in plan.items()],
            'passed':len(plan),'failed':0}

    def test_complete_synthetic_report_is_structurally_consistent_only(self):
        r=verify(self.report,self.bundle,'b'*64,'excel')
        self.assertTrue(r['ok']);self.assertFalse(r['board_approval']);self.assertEqual(r['required_cases'],18)

    def test_missing_duplicate_stale_wrong_output_and_emulated_reports_fail(self):
        for fault in ('missing','duplicate','stale','output','emulated','fixture','aborted','counter','status'):
            r=copy.deepcopy(self.report)
            if fault=='missing':r['cases'].pop();r['passed']-=1
            elif fault=='duplicate':r['cases'].append(copy.deepcopy(r['cases'][0]));r['passed']+=1
            elif fault=='stale':r['profile_bundle_sha256']='old'
            elif fault=='output':r['cases'][0]['actual']['value']=74
            elif fault=='emulated':r['engine']='formulas'
            elif fault=='fixture':r['cases'][0]['fixture_sha256']='old'
            elif fault=='aborted':r['aborted']=True
            elif fault=='counter':r['passed']=0
            elif fault=='status':r['cases'][0]['actual']['evaluation_status']='invalid_input'
            with self.subTest(fault=fault):self.assertFalse(verify(r,self.bundle,'b'*64,'excel')['ok'])


class PilotEvidence(unittest.TestCase):
    def row(self,n,group,outcome):
        return dict(record_id=str(n),cohort_id=group,campaign_id=group,event_at='2026-08-01T00:00:00Z',known_at='2026-08-02T00:00:00Z',
            outcome=outcome,outcome_at='2026-08-03T00:00:00Z' if outcome is not None else None)

    def document(self,first,second):
        snapshots=[]
        for day,rows in [(10,first),(11,second)]:
            snapshots.append(dict(as_of=f'2026-09-{day}T00:00:00Z',source_receipt_ref='synthetic:receipt',rows=rows,
                receipt=dict(complete=True,record_count=len(rows),rows_sha256=digest(rows))))
        return dict(pilot_id='synthetic:test',scope_id='fixture',card_id='fixture',output_id='rate',source_catalog_sha256='a'*64,
            definition_ref='synthetic:definition',normalization_ref='not used: binary outcomes',weight_profile_ref='not used: equal observations',
            source_evidence_ref='synthetic:source',verifier_record_ref='synthetic:checker-test',sampling_rationale='Synthetic finite census.',
            evidence_class='synthetic_example',population_kind='census',minimum_observed_denominator=30,outcome_maturity_days=14,late_arrival_days=0,snapshots=snapshots)

    def test_same_percentage_different_basis_and_no_census_interval(self):
        for n,statement in [(1,'below_declared_minimum'),(1000,'meets_declared_minimum_only')]:
            rows=[self.row(i,'a',True) for i in range(n)];r=pilot_evaluate(self.document(rows,rows),'a'*64)
            with self.subTest(n=n):
                total=r['snapshots'][0]['total'];self.assertEqual(total['rate'],1);self.assertEqual(total['evidence_statement'],statement);self.assertIsNone(total['interval_95'])
                self.assertFalse(r['automatic_finding_closure'])

    def test_case_mix_exposes_apparent_improvement(self):
        base=[self.row(i,'easy',i<9) for i in range(10)]+[self.row(10+i,'hard',i<1) for i in range(10)]
        expanded=base+[self.row(20+i,'easy',i<72) for i in range(80)]
        r=pilot_evaluate(self.document(base,expanded),'a'*64)['snapshots'][1]['comparison']
        self.assertAlmostEqual(r['raw_rate_change'],.32);self.assertAlmostEqual(r['standardized_rate_change'],0);self.assertAlmostEqual(r['eligible_mix_total_variation'],.4)

    def test_pending_and_late_observations_remain_visible(self):
        first=[self.row(1,'a',True),self.row(2,'a',None)];second=copy.deepcopy(first);second[1].update(outcome=False,outcome_at='2026-09-11T00:00:00Z')
        r=pilot_evaluate(self.document(first,second),'a'*64)
        self.assertEqual(r['snapshots'][0]['total']['mature_pending_outcomes'],1)
        self.assertEqual(r['snapshots'][0]['total']['late_arrivals'],2)
        self.assertEqual(r['snapshots'][1]['total']['pending'],0)

    def test_receipt_future_data_silent_attrition_and_unjustified_intervals_fail(self):
        rows=[self.row(1,'a',True),self.row(2,'b',False)]
        for fault in ('receipt','future','attrition','sampling','stale','correction'):
            d=self.document(copy.deepcopy(rows),copy.deepcopy(rows))
            if fault=='receipt':d['snapshots'][1]['receipt']['complete']=False
            elif fault=='future':d['snapshots'][1]['rows'][0]['known_at']='2027-01-01T00:00:00Z'
            elif fault=='attrition':d['snapshots'][1]['rows'].pop()
            elif fault=='sampling':d['population_kind']='binomial_sample'
            elif fault=='stale':d['source_catalog_sha256']='old'
            elif fault=='correction':d['snapshots'][1]['rows'][0]['outcome']=False
            if fault!='receipt':
                s=d['snapshots'][1];s['receipt'].update(record_count=len(s['rows']),rows_sha256=digest(s['rows']))
            with self.subTest(fault=fault),self.assertRaises(ValueError):pilot_evaluate(d,'a'*64)

    def test_binomial_interval_only_with_explicit_sampling_justification(self):
        rows=[self.row(1,'a',True)];d=self.document(rows,rows);d.update(population_kind='binomial_sample',independent_bernoulli_justified=True)
        ci=pilot_evaluate(d,'a'*64)['snapshots'][0]['total']['interval_95'];self.assertLess(ci[0],.21);self.assertAlmostEqual(ci[1],1)


class BoardAcceptance(unittest.TestCase):
    def setUp(self):
        self.matrix={'bundle_sha256':'b','catalog_sha256':'c','cards':[dict(card_id='fixture:card',source_card_sha256='card',priority='P0',independent_reviewers_required=2,required_case_ids=['four_values'])]}
        ref='https://github.com/OpenSecurityMetricsStandard/OSMS/issues/999999999';today=date.today().isoformat()
        self.record=dict(source_commit='a'*40,bundle_sha256='b',catalog_sha256='c',charter_sha256='h',packet_manifest_sha256='p',
            members=[dict(member_id=str(i),name='Synthetic fixture '+str(i),declaration_ref=ref,conflicts_declared=True,
                expertise=['measurement','security_operations_risk','data_engineering','assurance']) for i in range(3)],
            adoption=dict(participants=['0','1','2'],recused_members=[],disposition='accepted',date=today,record_ref=ref,
                mandatory_gates=list(GATES),single_failed_gate_blocks=True,rationale='Synthetic truth-table fixture',dissent=[],
                checkpoints=[dict(date=today,purpose='Fixture',schedule_rationale='Synthetic only')]),
            assignments=[dict(card_id='fixture:card',reviewer_ids=['0','1'],scope='Population and estimator')],
            reviews=[dict(card_id='fixture:card',member_id=str(i),source_card_sha256='card',independent_of_implementation=True,
                population_assessment='Fixture only',decision_assessment='Fixture only',calculation_assessment='Four values checked',
                rationale='Synthetic fixture only',date=today,record_ref=ref,disposition='accepted',case_ids=['four_values']) for i in range(2)],
            gates={k:dict(status='pass',record_ref=ref,rationale='Synthetic fixture only') for k in GATES})

    def result(self,record):return review_evaluate(record,self.matrix,'h','p')

    def test_all_gates_required_individually(self):
        self.assertTrue(self.result(self.record)['ready_for_formal_promotion'])
        self.assertFalse(self.result(self.record)['actual_board_approval_claim'])
        for gate in GATES:
            r=copy.deepcopy(self.record);r['gates'][gate]['status']='fail'
            with self.subTest(gate=gate):self.assertFalse(self.result(r)['ready_for_formal_promotion'])

    def test_recusal_stale_hash_missing_review_and_deferral_block(self):
        for fault in ('recusal','independence','stale','review','deferred','assignment','case','adoption'):
            r=copy.deepcopy(self.record)
            if fault=='recusal':r['adoption']['recused_members']=['0']
            elif fault=='independence':r['reviews'][0]['independent_of_implementation']=False
            elif fault=='stale':r['reviews'][0]['source_card_sha256']='old'
            elif fault=='review':r['reviews'].pop()
            elif fault=='deferred':r['reviews'][0].update(disposition='deferred',followup_owner='1',followup_criterion='Retest',followup_due=date.today().isoformat())
            elif fault=='assignment':r['assignments']=[]
            elif fault=='case':r['reviews'][0]['case_ids']=['unknown']
            elif fault=='adoption':r['adoption']=None
            with self.subTest(fault=fault):self.assertFalse(self.result(r)['ready_for_formal_promotion'])


if __name__=='__main__':unittest.main()
