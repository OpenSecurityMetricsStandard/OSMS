# SPDX-License-Identifier: MIT
import copy,json,pathlib,sqlite3,sys,tempfile,unittest
import yaml
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'recipes'),str(ROOT/'reference')]
from semantic.registry import register
from semantic.cases import examples
from semantic.model import compute
from semantic.esql import reduce_export
from semantic.excel import spec
from semantic.check import duckdb_compute
import execution_store as store
import assurance

class SemanticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plans=register(yaml.safe_load((ROOT/'catalog/osms-catalog.yaml').read_text())['cards']);cls.examples=examples(cls.plans)

    def result(self,cid,rows):return compute(self.plans[cid],rows,self.examples[cid][0]['params'])

    def test_all_119_cards_have_explicit_independent_examples_and_bounded_excel_formulas(self):
        self.assertEqual(len(self.plans),119);self.assertEqual(set(self.examples),set(self.plans))
        for cid,p in self.plans.items():
            s=spec(p)
            for _,formula in s['helpers']:
                self.assertLessEqual(len(formula),8192,cid)

    def test_multipart_na_does_not_become_green(self):
        for inputs,expected in [
            ({'critical_objects_tested':0,'critical_objects_in_universe':0,'high_critical_findings_treated_on_time':0,'high_critical_findings_due':0,'unmanaged_critical_findings':0},None),
            ({'critical_objects_tested':0,'critical_objects_in_universe':0,'high_critical_findings_treated_on_time':0,'high_critical_findings_due':0,'unmanaged_critical_findings':1},2),
            ({'critical_objects_tested':18,'critical_objects_in_universe':20,'high_critical_findings_treated_on_time':0,'high_critical_findings_due':0,'unmanaged_critical_findings':0},1)]:
            rows=copy.deepcopy(self.examples['VAL-001'][0]['rows']);rows[0].update(inputs)
            self.assertEqual(self.result('VAL-001',rows)['outputs']['overall_band'],expected)
            self.assertEqual(duckdb_compute(self.plans['VAL-001'],rows,self.examples['VAL-001'][0]['params'])['outputs']['overall_band'],expected)

    def test_survey_native_nps_classification_and_variant_mixing(self):
        base=self.examples['SOC-050'][0]['rows'][0]
        rows=[{**base,'record_id':str(i),'survey_variant':'nps_0_10','survey_score':v,'weight':1000 if i==0 else 1} for i,v in enumerate([10,9,8,1])]
        self.assertEqual(self.result('SOC-050',rows)['outputs']['nps'],25)
        rows[0]['survey_variant']='csat_1_5';rows[0]['survey_score']=5
        self.assertEqual(self.result('SOC-050',rows)['evaluation_status'],'invalid_input')

    def test_pending_effect_and_regulatory_case_override(self):
        row=copy.deepcopy(self.examples['STD-078'][0]['rows'][0]);row.update(benefit_observed_at=None,effect_window_days=90)
        result=self.result('STD-078',[row])['outputs'];self.assertEqual(result['pending_measures'],1);self.assertIsNone(result['overall_band'])
        row['effect_window_days']=1;self.assertEqual(self.result('STD-078',[row])['outputs']['overall_band'],2)
        row=copy.deepcopy(self.examples['SOC-053'][0]['rows'][0]);row.update(reported_at=None,regulatory_obligation=True,sla_deadline_hours=24)
        self.assertEqual(self.result('SOC-053',[row])['outputs']['overall_band'],2)

    def test_even_median_nearest_rank_and_confirmation_cutoff(self):
        import datetime as dt
        base=self.examples['SOC-002'][0]['rows'][0]
        end=dt.datetime(2026,6,20,tzinfo=dt.timezone.utc)
        rows=[{**base,'record_id':str(i),'detected_at':end.isoformat(),'occurred_at':(end-dt.timedelta(hours=h)).isoformat()} for i,h in enumerate([2,10,20,30])]
        self.assertEqual(self.result('SOC-002',rows)['outputs']['p50'],15)
        rows[3]['confirmed_at']='2026-07-02T00:00:00Z'
        self.assertEqual(self.result('SOC-002',rows)['outputs']['p50'],10)
        base=self.examples['CFG-002'][0]['rows'][0];cutoff=dt.datetime(2026,7,1,tzinfo=dt.timezone.utc)
        rows=[{**base,'record_id':str(i),'first_drift_detected_at':(cutoff-dt.timedelta(days=n)).isoformat()} for i,n in enumerate([1,2,4,6,9,12,15,18,22,26])]
        result=self.result('CFG-002',rows)['outputs']
        self.assertEqual((result['p50'],result['p90'],result['p95']),(9,22,26))

    def test_reference_version_and_factor_domain_cannot_be_relabelled(self):
        for cid,field,value in [('STD-006','weight_profile_version','unknown'),('STD-013','severity',4),('STD-035','mfa_gap',.75),('STD-001','std_014_direction','higher')]:
            c=copy.deepcopy(self.examples[cid][0]);c['rows'][0][field]=value
            self.assertEqual(self.result(cid,c['rows'])['evaluation_status'],'invalid_input')
            self.assertEqual(duckdb_compute(self.plans[cid],c['rows'],c['params'])['evaluation_status'],'invalid_input')

    def test_output_units_and_tolerance_boundaries_are_explicit(self):
        from ci.semantic_runner import equal
        for cid,key,value,unit in [('SOC-053','sla_rate',75,'percent'),('SOC-002','p50',15,'hours'),('SOC-032','value',1000,'EUR'),('SOC-064','coefficient_of_variation',.4,'ratio')]:
            contract=self.plans[cid]['output_contracts'][key]
            self.assertEqual(contract['unit'],unit)
            self.assertTrue(equal(value+5e-9,value,contract))
            self.assertFalse(equal(value+5e-7,value,contract))
        count=self.plans['AI-003']['output_contracts']['value']
        self.assertFalse(equal(4.4,4,count));self.assertFalse(equal(4+1e-12,4,count))
        self.assertFalse(equal(2+1e-12,2,self.plans['VAL-001']['output_contracts']['overall_band']))

    def test_risk_median_and_minimum_reporting_basis(self):
        result=self.result('STD-002a',self.examples['STD-002a'][0]['rows'])['outputs']
        self.assertEqual(result['p50_loss'],55)
        self.assertEqual(result['reporting_eligible'],0)

    def test_independent_sql_normalization_and_target_band(self):
        import duckdb
        numeric=['raw_value','red','target','red_low','target_low','target_high','red_high']
        strings=['direction','profile_id','profile_version','card_id','card_version','output_id','unit','evidence_ref']
        query=(ROOT/'reference/normalization.sql').read_text()
        for direction,raw,expected in [('higher',25,25),('lower',25,75),('band',50,100),('band',10,50),('band',90,50)]:
            profile=dict(direction=direction,red=100 if direction=='lower' else 0,target=0 if direction=='lower' else 100,
                red_low=0,target_low=20,target_high=80,red_high=100,profile_id='fixture:normalization',profile_version='1',
                card_id='fixture:card',card_version='0.9.2',output_id='value',unit='score',evidence_ref='fixture:anchors')
            row={**profile,'raw_value':raw}
            with duckdb.connect() as con:
                con.execute('CREATE TABLE normalization_input ('+','.join(k+' DOUBLE' for k in numeric)+','+','.join(k+' VARCHAR' for k in strings)+')')
                con.execute('INSERT INTO normalization_input VALUES ('+','.join('?' for _ in numeric+strings)+')',[row[k] for k in numeric+strings])
                self.assertEqual(con.execute(query).fetchone(),(expected,'ok'))
                self.assertEqual(assurance.normalize(raw,profile)['posture_score'],expected)
                con.execute('UPDATE normalization_input SET target=red,target_low=red_low')
                self.assertEqual(con.execute(query).fetchone(),(None,'invalid_profile'))

    def test_engine_export_rejects_truncated_or_warned_data(self):
        p=self.plans['SOC-002'];fixture=self.examples['SOC-002'][0];cols=list(p['inputs']);rows=fixture['rows']
        count={'columns':[{'name':'source_rows'}],'values':[[len(rows)]]}
        response={'columns':[{'name':k} for k in cols],'values':[[r.get(k) for k in cols] for r in rows]}
        result=reduce_export(p,count,response,fixture['params'],snapshot_hash='b'*64)
        self.assertEqual(result['result']['outputs']['p50'],16)
        unverified=reduce_export(p,count,response,{**fixture['params'],'population_complete':False},snapshot_hash='b'*64)
        self.assertEqual(unverified['result']['evaluation_status'],'population_unverified')
        self.assertEqual(unverified['export_record_count'],len(rows))
        self.assertIsNone(unverified['result']['outputs']['p50'])
        for mutation in ['truncate','warn','duplicate_column']:
            bad=copy.deepcopy(response)
            if mutation=='truncate':bad['values'].pop()
            elif mutation=='warn':bad['warnings']=['partial shard']
            else:bad['columns'][0]['name']=bad['columns'][1]['name']
            with self.assertRaises(ValueError):reduce_export(p,count,bad,fixture['params'],snapshot_hash='b'*64)

class HistoricalEvidenceTests(unittest.TestCase):
    setUpClass=classmethod(SemanticTests.setUpClass.__func__)
    def capture(self,cid='STD-006'):
        con=sqlite3.connect(':memory:');f=self.examples[cid][0]
        receipt=store.capture(con,'historical:1',self.plans[cid],f['rows'],f['params'])
        return con,receipt['manifest_sha256']

    def test_weighted_average_and_independent_archive_restore(self):
        con,receipt=self.capture();self.assertEqual(store.replay(con,'historical:1',receipt)['result']['outputs']['value'],72.5)
        with tempfile.TemporaryDirectory() as folder:
            store.export_report(con,'historical:1',receipt,folder)
            self.assertEqual(store.restore(folder,receipt)['result']['outputs']['value'],72.5)
            pathlib.Path(folder,'unlisted.txt').write_text('unlisted')
            with self.assertRaisesRegex(store.EvidenceError,'UNLISTED'):store.restore(folder,receipt)

    def test_tampered_inputs_detected_even_when_sum_is_preserved(self):
        for field,value in [('criticality_weight',1),('scope_id','other'),('card_version','unknown'),('source_system','other'),('evidence_ref',''),('weight_profile_version','unknown')]:
            con,receipt=self.capture();rows=json.loads(con.execute("SELECT content FROM execution_file WHERE name='observations.json'").fetchone()[0]);rows[0][field]=value
            con.execute("UPDATE execution_file SET content=? WHERE name='observations.json'",(store.encoded(rows),))
            with self.assertRaisesRegex(store.EvidenceError,'HASH_MISMATCH'):store.replay(con,'historical:1',receipt)
        con,receipt=self.capture();rows=json.loads(con.execute("SELECT content FROM execution_file WHERE name='observations.json'").fetchone()[0])
        rows[0].update(criticality_weight=1,effectiveness_score=100);rows[1]['criticality_weight']=2
        params=self.examples['STD-006'][0]['params']
        self.assertEqual(compute(self.plans['STD-006'],rows,params)['outputs']['value'],72.5)
        con.execute("UPDATE execution_file SET content=? WHERE name='observations.json'",(store.encoded(rows),))
        with self.assertRaisesRegex(store.EvidenceError,'HASH_MISMATCH'):store.replay(con,'historical:1',receipt)

    def test_missing_evidence_result_tamper_and_unknown_scope(self):
        con,receipt=self.capture();con.execute("DELETE FROM execution_file WHERE name='observations.json'")
        with self.assertRaisesRegex(store.EvidenceError,'MISSING_EVIDENCE'):store.replay(con,'historical:1',receipt)
        con,receipt=self.capture();result=json.loads(con.execute("SELECT content FROM execution_file WHERE name='result.json'").fetchone()[0]);result['outputs']['value']=99
        con.execute("UPDATE execution_file SET content=? WHERE name='result.json'",(store.encoded(result),))
        with self.assertRaisesRegex(store.EvidenceError,'HASH_MISMATCH'):store.replay(con,'historical:1',receipt)
        self.assertEqual(store.find_reports(con,'STD-006',self.plans['STD-006']['card_version'],'unknown','2026-07-01T00:00:00Z'),[])

    def test_current_catalog_changes_do_not_change_historical_receipt(self):
        con,receipt=self.capture();plan=copy.deepcopy(self.plans['STD-006']);plan['card_version']='later'
        self.assertEqual(store.replay(con,'historical:1',receipt)['result']['outputs']['value'],72.5)
        f=self.examples['STD-006'][0]
        with self.assertRaises(sqlite3.IntegrityError):store.capture(con,'historical:1',self.plans['STD-006'],f['rows'],f['params'])

if __name__=='__main__':unittest.main()
