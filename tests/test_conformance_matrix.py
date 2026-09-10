# SPDX-License-Identifier: MIT
import hashlib,importlib.util,json,pathlib,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('collect_reports',ROOT/'recipes/ci/collect_profile_reports.py')
M=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(M)

class MatrixEvidenceTests(unittest.TestCase):
    def test_identical_report_names_preserve_each_engine_version_and_failure(self):
        with tempfile.TemporaryDirectory() as d:
            root=pathlib.Path(d);bundle=root/'bundle';reports=root/'artifacts';bundle.mkdir()
            source=b'{"fixture":true}';(bundle/'execution-profiles.json').write_bytes(source)
            (bundle/'execution-coverage.json').write_text(json.dumps({'matrix':[{'card_id':'fixture:card','dialect':'spl','full_card_native_conformance':'not_established'}]}))
            for version,status in [('9.4','fail'),('10.2','pass')]:
                p=reports/version;p.mkdir(parents=True)
                report={'profile_bundle_sha256':hashlib.sha256(source).hexdigest(),'engine':'spl','engine_version':version,'stage':'prepared_observations',
                    'cases':[{'card_id':'fixture:card','case_id':'independent_fixture','outputs':['value'],'status':status}]}
                (p/'profile-report-spl.json').write_text(json.dumps(report))
            stale=reports/'stale';stale.mkdir();report['profile_bundle_sha256']='0'*64;(stale/'profile-report-spl.json').write_text(json.dumps(report))
            result=M.collect(bundle,reports)
            self.assertEqual(len(result['accepted_reports']),2);self.assertEqual(len(result['rejected_reports']),1)
            evidence=result['matrix'][0]['execution_evidence']
            self.assertEqual({x['engine_version']:x['status'] for x in evidence},{'9.4':'fail','10.2':'pass'})
            self.assertEqual(len({x['report'] for x in evidence}),2)
            self.assertEqual(result['matrix'][0]['full_card_native_conformance'],'not_established')

if __name__=='__main__':unittest.main()
