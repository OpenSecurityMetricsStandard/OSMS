# SPDX-License-Identifier: MIT
import copy,pathlib,sys,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from framework_mappings import inventory

class FrameworkMappingTests(unittest.TestCase):
    def test_unreviewed_is_not_assessed_and_edition_is_not_invented(self):
        cards=[dict(id='X',card_version='0.9.2',framework_mapping=['NIST CSF 2.0: GV','CIS Controls 7'])]
        result=inventory(cards,[]);self.assertEqual(result['not_assessed_count'],2)
        self.assertEqual(result['mappings'][0]['edition_stated'],'2.0');self.assertIsNone(result['mappings'][1]['edition_stated'])
        self.assertTrue(all(x['relationship']=='not_assessed' and x['conformity_claim'] is False for x in result['mappings']))

    def test_stale_unreasoned_or_false_conformity_review_fails(self):
        cards=[dict(id='X',card_version='0.9.2',framework_mapping=['Test Framework:2022'])]
        row=inventory(cards,[])['mappings'][0]
        review={**row,'framework':'Synthetic framework','edition':'2022','reference':'fixture:1','relationship':'partial_support',
            'rationale':'Synthetic rule checks one of two required observations.','evidence_ref':'fixture:evidence','reviewer':'fixture:reviewer','decision_date':'2026-09-10'}
        self.assertEqual(inventory(cards,[review])['reviewed_count'],1)
        for k,v in [('card_version','earlier'),('rationale',' '),('edition',''),('conformity_claim',True),('decision_date','not-a-date')]:
            bad=copy.deepcopy(review);bad[k]=v
            with self.assertRaises(ValueError):inventory(cards,[bad])

if __name__=='__main__':unittest.main()
