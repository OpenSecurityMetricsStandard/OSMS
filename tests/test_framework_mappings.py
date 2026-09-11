# SPDX-License-Identifier: MIT
import copy
from datetime import date, timedelta
import pathlib
import sys
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from framework_mappings import assessment_hash, cited_elements, digest, inventory, repository_inventory, validate_identifiers


class FrameworkMappingTests(unittest.TestCase):
    def setUp(self):
        self.cards=[dict(id='X',card_version='0.9.2',definition='A fixture measures one observation.',
                         formula='passed / total',framework_mapping=['NIST CSF 2.0 PR.AA'])]
        self.source={'framework':'NIST CSF','edition':'2.0','url':'https://example.test/fixture',
                     'element_ids':['PR.AA','PR.DS']}
        self.sources={'fixture':self.source}
        row=inventory(self.cards,[])['mappings'][0]
        self.assessment={k:row[k] for k in ('mapping_id','card_id','card_version','source_card_sha256','source_reference_sha256')}
        self.assessment.update(assessment_status='assessed',approval_status='pending',reviewer=None,
            framework='NIST CSF',edition='2.0',edition_basis='explicit_source_edition',reference='NIST CSF 2.0 PR.AA',
            source_id='fixture',source_metadata_sha256=digest(self.source),source_locator='fixture scope',
            relationship='supports_measurement_of',cited_elements=['PR.AA'],supported_elements=['PR.AA'],unsupported_elements=[],
            rationale='Synthetic observation of access review only.',scope_limit='Other access requirements remain unproven.',
            assessment_date=date.today().isoformat(),conformity_claim=False)
        self.review={k:self.assessment[k] for k in ('mapping_id','card_id','card_version','source_card_sha256','source_reference_sha256')}
        self.review.update(assessment_sha256=assessment_hash(self.assessment),reviewer='fixture-reviewer-not-a-real-person',
            decision_date=date.today().isoformat(),review_record_ref='https://github.com/OpenSecurityMetricsStandard/OSMS/issues/999999999',
            decision='approve',rationale='Synthetic review fixture; not a real OSMS approval.')

    def run_inventory(self,assessment=None,reviews=None,cards=None,sources=None):
        return inventory(cards or self.cards,reviews or [],[assessment or self.assessment],sources or self.sources)

    def test_stated_edition_does_not_confuse_control_numbers(self):
        cards=[dict(id='X',card_version='1',framework_mapping=['CIS Controls 7','NIST CSF 2.0: GV','CISA ZTMM 2.0'])]
        r=inventory(cards,[])
        self.assertEqual([x['edition_stated'] for x in r['mappings']],[None,'2.0','2.0'])
        self.assertEqual(r['not_assessed_count'],3)

    def test_assessment_is_not_approval(self):
        r=self.run_inventory()
        self.assertEqual((r['assessed_count'],r['reviewed_count'],r['approved_count']),(1,0,0))
        self.assertEqual(r['mappings'][0]['approval_status'],'pending')
        self.assertIsNone(r['mappings'][0]['reviewer'])

    def test_card_definition_or_formula_change_without_version_bump_invalidates(self):
        for field in ('definition','formula','card_version','id'):
            cards=copy.deepcopy(self.cards);cards[0][field]='changed'
            with self.subTest(field=field),self.assertRaises(ValueError):self.run_inventory(cards=cards)

    def test_source_change_invalidates_assessment(self):
        sources=copy.deepcopy(self.sources);sources['fixture']['url']='https://example.test/changed'
        with self.assertRaises(ValueError):self.run_inventory(sources=sources)

    def test_assessment_change_invalidates_approval(self):
        self.assertEqual(self.run_inventory(reviews=[self.review])['approved_count'],1)
        changed=copy.deepcopy(self.assessment);changed['rationale']='Different relationship interpretation.'
        with self.assertRaises(ValueError):self.run_inventory(changed,[self.review])

    def test_false_approval_source_or_edition_fails(self):
        for field,value in [('approval_status','approved'),('reviewer','Invented reviewer'),('conformity_claim',True),
                            ('edition','2026'),('framework','Unrelated framework'),('source_id','unknown'),
                            ('source_reference','NIST CSF 2.0 PR.DS'),('reference','NIST CSF 2.0 PR.DS'),('source_card_sha256','0'*64),
                            ('assessment_date',(date.today()+timedelta(days=1)).isoformat()),
                            ('scope_limit',''),('source_locator',''),('rationale','')]:
            a=copy.deepcopy(self.assessment);a[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):self.run_inventory(a)

    def test_contradictory_or_unknown_elements_fail(self):
        for changes in [dict(supported_elements=['ZZ.XX']),dict(supported_elements=[]),
                        dict(supported_elements=['PR.AA','PR.AA']),dict(unsupported_elements=['PR.AA']),
                        dict(relationship='supports_measurement_of',unsupported_elements=['PR.DS']),
                        dict(relationship='no_claim'),dict(cited_elements=[]),dict(supported_elements=['PR.DS'])]:
            a={**self.assessment,**changes}
            with self.subTest(changes=changes),self.assertRaises(ValueError):self.run_inventory(a)

    def test_blocked_record_cannot_be_approved(self):
        a={**self.assessment,'assessment_status':'blocked','relationship':'not_assessed',
           'blocker':'fixture_source_missing','next_action':'Supply the fixture source.'}
        self.assertEqual(self.run_inventory(a)['not_assessed_count'],1)
        review={**self.review,'assessment_sha256':assessment_hash(a)}
        with self.assertRaises(ValueError):self.run_inventory(a,[review])

    def test_selected_edition_requires_explanation(self):
        a={**self.assessment,'edition_basis':'selected_review_baseline'}
        with self.assertRaises(ValueError):self.run_inventory(a)
        a['edition_selection_rationale']='Explicit fixture baseline selection.'
        self.assertEqual(self.run_inventory(a)['assessed_count'],1)

    def test_real_review_record_reference_required(self):
        for field,value in [('reviewer',''),('review_record_ref','fixture:not-evidence'),
                            ('decision','auto-approve'),('conformity_claim',True),('assessment_sha256','stale')]:
            review={**self.review,field:value}
            with self.subTest(field=field),self.assertRaises(ValueError):self.run_inventory(reviews=[review])

    def test_duplicate_assessments_and_reviews_rejected(self):
        with self.assertRaises(ValueError):inventory(self.cards,[],[self.assessment]*2,self.sources)
        with self.assertRaises(ValueError):self.run_inventory(reviews=[self.review]*2)

    def test_rejection_is_not_approval(self):
        r=self.run_inventory(reviews=[{**self.review,'decision':'reject'}])
        self.assertEqual((r['reviewed_count'],r['approved_count']),(1,0))
        self.assertEqual(r['mappings'][0]['approval_status'],'rejected')

    def test_full_identifier_validation_does_not_ignore_invalid_suffix(self):
        self.assertEqual(validate_identifiers('NIST CSF 2.0 PR.AA-05')['element_ids'],['PR.AA-05'])
        for ref in ('PR.AA-99','PR.AA-05x','PR.X','XX','PR.AA/PR.AA','RS.IM','PR.AC'):
            with self.subTest(ref=ref),self.assertRaises(ValueError):validate_identifiers('NIST CSF 2.0 '+ref)

    def test_compound_ai_and_algorithm_citations_are_not_silently_reduced(self):
        self.assertEqual(cited_elements('NIST AI RMF','NIST AI RMF: Govern, Map, Measure'),
                         ['GOVERN','MAP','MEASURE'])
        self.assertEqual(cited_elements('OWASP SAMM','OWASP SAMM Verification'),['Verification'])
        self.assertEqual(cited_elements('NIST PQC','NIST PQC FIPS 203/204/205'),['FIPS-203','FIPS-204','FIPS-205'])
        for tail in ('Measure, Magage','Govern, Govern','Measure.X','Unknown'):
            with self.subTest(tail=tail),self.assertRaises(ValueError):cited_elements('NIST AI RMF','NIST AI RMF: '+tail)

    def test_replacement_proposal_must_exist_and_stay_outside_original_citation(self):
        for proposed in (['PR.XX'],['PR.AA'],['PR.DS','PR.DS'],'PR.DS'):
            with self.subTest(proposed=proposed),self.assertRaises(ValueError):
                self.run_inventory({**self.assessment,'proposed_elements_outside_citation':proposed})
        a={**self.assessment,'proposed_elements_outside_citation':['PR.DS']}
        self.assertEqual(self.run_inventory(a)['mappings'][0]['supported_elements'],['PR.AA'])

    def test_repository_counterexamples_and_approval_state(self):
        r=repository_inventory()
        self.assertEqual(r['mapping_count'],1149)
        self.assertEqual(r['triaged_count'],r['mapping_count'])
        self.assertTrue(all(e['reviewer'] and e['review_record_ref'] for e in r['mappings'] if e['approval_status']=='approved'))
        rows={(x['card_id'],x['source_reference']):x for x in r['mappings']}
        for cid,ref in [('STD-034','NIST CSF 2.0: DE, RS'),('STD-049','CIS Controls v8.1: 1, 2, 3, 4'),
                        ('SOC-002','NIST CSF 2.0: RS, RC')]:
            with self.subTest(card=cid):self.assertEqual(rows[cid,ref]['relationship'],'no_claim')
        iso=rows['MET-001','ISO/IEC 27004:2016']
        self.assertEqual(iso['relationship'],'informative_topic_association')
        self.assertEqual(iso['supported_elements'],['public_abstract_scope'])
        scoped=rows['LOG-008','NIST SP 800-53 AU-9/AU-10/AU-11']
        self.assertEqual(scoped['supported_elements'],['AU-9'])
        self.assertEqual(scoped['unsupported_elements'],['AU-10','AU-11'])
        self.assertEqual(scoped['relationship'],'partial_support')
        trace=rows['AIM-008','NIST AI RMF: Govern, Map, Measure']
        self.assertEqual(trace['unsupported_elements'],['GOVERN','MAP'])
        self.assertEqual(trace['supported_elements'],['MEASURE.2.8','MEASURE.2.9'])
        attack=rows['AIM-011','NIST AI RMF: Manage']
        self.assertEqual(attack['relationship'],'no_claim')
        self.assertEqual(attack['proposed_elements_outside_citation'],['MEASURE.2.7'])
        samm=rows['APP-004','OWASP SAMM Verification']
        self.assertEqual(samm['edition'],'2.2.0')
        self.assertEqual(samm['cited_elements'],['Verification'])
        self.assertEqual(samm['supported_elements'],['Verification.Security-Testing'])
        pqc=rows['CRY-001','NIST PQC FIPS 203/204/205']
        self.assertEqual(pqc['unsupported_elements'],['FIPS-203','FIPS-204','FIPS-205'])

if __name__=='__main__':unittest.main()
