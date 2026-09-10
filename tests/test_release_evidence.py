# SPDX-License-Identifier: MIT
import importlib.util,pathlib,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('release_evidence',ROOT/'tools/verify_release_evidence.py')
M=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(M)

class ReleaseEvidenceTests(unittest.TestCase):
    def rows(self):return [{'id':i,'path':p,'head_sha':'a'*40,'status':'completed','conclusion':'success','run_attempt':1} for i,p in enumerate(sorted(M.REQUIRED),1)]
    def test_only_exact_commit_passes(self):
        self.assertTrue(M.evaluate(self.rows(),'a'*40)['ok']);self.assertFalse(M.evaluate(self.rows(),'b'*40)['ok'])
    def test_failure_missing_and_running_block(self):
        self.assertFalse(M.evaluate(self.rows()[:1],'a'*40)['ok'])
        for status,conclusion in [('completed','failure'),('completed','cancelled'),('completed','skipped'),('in_progress',None)]:
            rows=self.rows();rows[0].update(status=status,conclusion=conclusion)
            self.assertFalse(M.evaluate(rows,'a'*40)['ok'])
    def test_latest_attempt_is_required(self):
        rows=self.rows();rows.append({**rows[0],'run_attempt':2,'status':'in_progress','conclusion':None})
        self.assertFalse(M.evaluate(rows,'a'*40)['ok'])

if __name__=='__main__':unittest.main()
