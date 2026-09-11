# SPDX-License-Identifier: MIT
import copy
import pathlib
import sys
import unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'reference'),str(ROOT/'tools')]
from source_to_decision import examples,snapshot,make_receipt
from framework_mappings import validate_identifiers

class PreboardEvidence(unittest.TestCase):
    def test_source_to_decision_and_replay(self):
        r=examples()
        self.assertEqual(r['detection']['lineage']['numerator_ids'],['0','1','2'])
        self.assertEqual(len(r['detection']['lineage']['excluded_ids']),3)
        self.assertFalse(r['mandatory_failure_example']['management_green_eligible'])
        self.assertTrue(r['control_effectiveness']['replay']['ok'])

    def test_source_count_hash_and_identity_are_independently_required(self):
        rows=[{'id':'1','value':10}];receipt=make_receipt(rows)
        for r,p in [(rows,dict(receipt,record_count=2)),(rows,dict(receipt,complete=False)),
                    ([dict(rows[0],value=11)],receipt), (rows+rows,make_receipt(rows+rows))]:
            with self.assertRaises(ValueError):snapshot(r,p)

    def test_old_and_duplicate_framework_categories_fail(self):
        for ref in ('NIST CSF 2.0 ID.IM/RS.IM','NIST CSF 2.0 PR.AC','NIST CSF 2.0 RC.RP/RC.RP'):
            with self.assertRaises(ValueError):validate_identifiers(ref)
        self.assertEqual(validate_identifiers('NIST CSF 2.0 PR.AA')['status'],'category_ids_checked')
        self.assertEqual(validate_identifiers('NIST CSF 2.0: GV')['status'],'function_level_only')

if __name__=='__main__':unittest.main()
