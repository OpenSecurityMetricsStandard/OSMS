"""Independent regression oracles for the 2026-09 audit remediation.

Run from repo root: python -m unittest discover -s tests -v
"""
import copy
import importlib.util
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import duckdb
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


review = module('review', 'tools/review_kpis.py')
drill = module('drill', 'reference/drill_engine.py')


def setUpModule():
    global temporary, bundle, fixtures
    temporary = tempfile.TemporaryDirectory(prefix='osms-regression-')
    subprocess.run([sys.executable, str(ROOT / 'recipes/gen_recipes.py'), '--repo', str(ROOT),
                    '--out', temporary.name, '--emit-candidates'], check=True, capture_output=True)
    bundle = json.loads((Path(temporary.name) / 'recipes.json').read_text())['recipes']
    fixtures = {f['card']: f for f in json.loads((Path(temporary.name) / 'fixtures.json').read_text())}


def tearDownModule():
    temporary.cleanup()


def dataframe(rows, dates=()):
    data = pd.DataFrame(rows)
    for field in dates:
        data[field] = pd.to_datetime(data[field], format='mixed')
    return data


def compute_python(cid, data, period=True):
    namespace = {}
    exec(bundle[cid]['dialects']['py'], namespace)
    fn = namespace.get('compute') or namespace.get('mttd') or namespace.get('sla_compliance_pct')
    return fn(data, pd.Timestamp('2026-06-01'), pd.Timestamp('2026-07-01'), 'prod') if period else fn(data, 'prod')


def compute_sql(cid, data, table='records', dialect='gsql'):
    with duckdb.connect() as con:
        con.register(table, data)
        sql = bundle[cid]['dialects'][dialect]
        params = {}
        for key, value in {'scope_id':'prod', 'period_start':'2026-06-01', 'period_end':'2026-07-01'}.items():
            if ':' + key in sql:
                sql = sql.replace(':' + key, '$' + key)
                params[key] = value
        cur = con.execute(sql, params)
        return dict(zip([d[0] for d in cur.description], cur.fetchone()))


class RecipeRegressionTests(unittest.TestCase):
    def test_mttd_detection_cohort_confirmation_and_weights(self):
        rows = [
            dict(occurred_at='2026-05-31 23:00', detected_at='2026-06-01 01:00', confirmed_at='2026-06-02', severity='P1', scope_id='prod'),
            dict(occurred_at='2026-06-10 00:00', detected_at='2026-06-10 10:00', confirmed_at='2026-06-11', severity='P2', scope_id='prod'),
            dict(occurred_at='2026-06-30', detected_at='2026-07-02', confirmed_at='2026-07-03', severity='P1', scope_id='prod'),
            dict(occurred_at='2026-06-15', detected_at='2026-06-16', confirmed_at='2026-07-02', severity='P1', scope_id='prod'),
            dict(occurred_at='2026-06-15', detected_at='2026-06-16', confirmed_at=None, severity='P1', scope_id='prod'),
        ]
        data = dataframe(rows, ['occurred_at','detected_at','confirmed_at'])
        expected = {'valid_cases':2, 'p50_h':6, 'p90_h':10, 'mean_h_supplementary':6, 'severity_weighted_avg':28/6}
        for result in [compute_python('SOC-002',data), compute_sql('SOC-002',data,'incidents'), compute_sql('SOC-002',data,'incidents','pg')]:
            for key, value in expected.items():
                with self.subTest(output=key):
                    self.assertAlmostEqual(result[key], value)

    def test_mttd_even_median_and_duplicate_durations(self):
        for hours, median, p90 in [([2,10,20,30],15,30), ([1,1,1,100],1,100)]:
            data = dataframe([dict(occurred_at=pd.Timestamp('2026-06-01'), detected_at=pd.Timestamp('2026-06-01')+pd.Timedelta(hours=h), confirmed_at=pd.Timestamp('2026-06-20'), severity='P3', scope_id='prod') for h in hours], ['occurred_at','detected_at','confirmed_at'])
            for result in [compute_python('SOC-002',data), compute_sql('SOC-002',data,'incidents','pg')]:
                self.assertEqual(result['p50_h'],median)
                self.assertEqual(result['p90_h'],p90)

    def test_mitigation_or_remediation_and_missing_dates(self):
        base = dict(record_id='r1',severity='critical',internet_facing=True,scope_id='prod',due_at='2026-06-20',remediated_at=None,mitigated_at='2026-06-19',validation_status='validated')
        for changes, expected in [({},100), ({'mitigated_at':None},0), ({'mitigated_at':'2026-06-21'},0), ({'validation_status':'open'},0), ({'remediated_at':'2026-06-18','mitigated_at':None},100), ({'mitigated_at':'2026-06-20'},100)]:
            with self.subTest(changes=changes):
                data = dataframe([{**base,**changes}],['due_at','remediated_at','mitigated_at'])
                self.assertEqual(compute_python('STD-016',data),expected)
                self.assertEqual(compute_sql('STD-016',data,'findings')['sla_compliance_pct'],expected)
                self.assertEqual(compute_sql('STD-016',data,'findings','pg')['sla_compliance_pct'],expected)

    def test_composite_missing_nonfinite_negative_duplicate_unknown(self):
        for cid in ['STD-069','STD-068','STD-075']:
            original = fixtures[cid]['rows']
            cases = []
            for field,value in [('subscore_value',None),('subscore_value',float('inf')),('subscore_value',float('nan')),('weight',None),('weight',-1),('weight',float('inf'))]:
                rows = copy.deepcopy(original);rows[0][field]=value;cases.append(rows)
            rows=copy.deepcopy(original);rows[0]['subscore_id']=rows[1]['subscore_id'];cases.append(rows)
            rows=copy.deepcopy(original);rows[0]['subscore_id']='unknown';cases.append(rows)
            cases += [copy.deepcopy(original[:-1]), copy.deepcopy(original)+[copy.deepcopy(original[0])]]
            for index, rows in enumerate(cases):
                with self.subTest(card=cid,case=index):
                    # Source timestamps are normalized to a common timezone before recipes run.
                    for row in rows:
                        for field in ['period_start','period_end']:row[field]=row[field].replace('Z','')
                    data=dataframe(rows,['period_start','period_end'])
                    self.assertIsNone(compute_python(cid,data))
                    self.assertIsNone(next(iter(compute_sql(cid,data).values())))
            nullable = pd.DataFrame(copy.deepcopy(original))
            for field in ['period_start','period_end']:
                nullable[field] = pd.to_datetime(nullable[field],utc=True).dt.tz_localize(None)
            nullable['subscore_value'] = nullable['subscore_value'].astype('Float64')
            nullable.loc[0,'subscore_value'] = pd.NA
            self.assertIsNone(compute_python(cid,nullable))

    def test_dsps_duplicate_missing_negative_and_nan_penalties(self):
        original=fixtures['STD-001']['rows']
        cases=[]
        rows=copy.deepcopy(original);rows[-1]['child_card_id']='STD-001a';cases.append(rows)
        for value in [-1,16,None,float('nan'),float('inf')]:
            rows=copy.deepcopy(original);rows[-1]['penalty_value']=value;cases.append(rows)
        rows=copy.deepcopy(original);rows[0]['posture_score']=None;cases.append(rows)
        rows=copy.deepcopy(original);rows[0]['child_card_id']='UNKNOWN';cases.append(rows)
        for index,rows in enumerate(cases):
            with self.subTest(case=index):
                data=pd.DataFrame(rows)
                self.assertIsNone(compute_python('STD-001',data,False))
                self.assertIsNone(compute_sql('STD-001',data)['value'])

    def test_unmapped_recipes_never_emit_plausible_values(self):
        for cid in ['AI-001','STD-074','AIM-003']:
            with self.subTest(card=cid):
                self.assertEqual(bundle[cid]['evaluation_status'],'mapping_required')
                self.assertIn('templates',bundle[cid])
                with self.assertRaises(NotImplementedError):compute_python(cid,pd.DataFrame([{'scope_id':'prod'}]),False)
                self.assertEqual(compute_sql(cid,pd.DataFrame([{'scope_id':'prod'}])),{'value':None,'evaluation_status':'mapping_required'})


class ReviewRegressionTests(unittest.TestCase):
    def test_real_ids_comments_and_final_decisions(self):
        issues=[dict(number=1,title='STD-001a and SOC-002',body='',state='open',user={'login':'maintainer'},labels=['finding','severity:major','cat:formula','decision:pending'],comments_data=[dict(user={'login':'reviewer'},body='Checked')]),
                dict(number=2,title='HRM-004',body='',state='OPEN',user={'login':'reviewer'},labels=['finding','severity:critical','cat:formula','decision:accepted']),
                dict(number=3,title='STD-999',body='',state='closed',user={'login':'bot[bot]','type':'Bot'},labels=['finding','decision:breaking'])]
        result=review.evaluate({'issues':issues,'comments_complete':True},{'STD-001a','SOC-002','HRM-004'},{'STD-001a'},['maintainer'])
        self.assertEqual(result['K-01'],1)
        self.assertEqual(result['K-05']['touched'],3)
        self.assertEqual(result['K-04']['percent'],100)
        self.assertEqual(result['K-07']['decided'],1)
        self.assertEqual(result['K-08'],1)
        self.assertIsNone(result['K-09'])

    def test_conflicting_decisions_are_unresolved(self):
        for ls in [['decision:pending'],['decision:breaking'],['decision:accepted','decision:rejected'],['decision:accepted','decision:pending']]:
            self.assertIsNone(review.final_decision({'labels':ls}))

    def test_triage_needs_both_labels_and_excludes_weekend(self):
        issue={'created_at':'2026-09-04T12:00:00Z','events':[
            {'id':1,'created_at':'2026-09-04T13:00:00Z','event':'labeled','label':{'name':'severity:major'}},
            {'id':2,'created_at':'2026-09-07T12:00:00Z','event':'labeled','label':{'name':'cat:formula'}}]}
        self.assertEqual(review.triage_time(issue),1)
        self.assertEqual(review.triage_time(issue,{'2026-09-07'}),0.5)
        issue['events'].insert(1,{'id':3,'created_at':'2026-09-04T14:00:00Z','event':'unlabeled','label':{'name':'severity:major'}})
        self.assertIsNone(review.triage_time(issue))

    def test_card_catalog_list_and_empty_p0(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'cards.yaml';p.write_text('- id: HRM-004\n  priority: P1\n')
            self.assertEqual(review.load_catalog_ids(p),({'HRM-004'},set()))

    def test_no_artificial_first_100_limit(self):
        issues=[{'state':'open','created_at':'2026-09-04T12:00:00Z','labels':[], 'events':[
            {'id':1,'created_at':'2026-09-04T13:00:00Z','event':'labeled','label':{'name':'cat:formula'}},
            {'id':2,'created_at':'2026-09-04T14:00:00Z','event':'labeled','label':{'name':'severity:major'}}]} for _ in range(121)]
        result=review.evaluate({'issues':issues,'events_complete':True},{'AI-001'},set())
        self.assertEqual(result['K-06']['triaged'],121)


class ReferenceRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.catalog=drill.Catalog(ROOT/'catalog/osms-catalog.yaml')
    def setUp(self):
        self.db=drill.build_demo_db(ROOT/'reference/star_schema.sql',ROOT/'reference/seed_reference_data.sql')
        self.engine=drill.DrillEngine(self.db,self.catalog)
    def tearDown(self):self.db.close()
    def reconcile(self,cid):return self.engine.reconcile(cid,'SCOPE-GLOBAL','2026-07-31')

    def test_correct_delta_cost_and_penalty_cap(self):
        self.assertEqual(self.reconcile('STD-074')['recomputed'],-1)
        self.assertEqual(self.reconcile('STD-005')['recomputed'],0.3)
        self.db.execute('UPDATE fact_evidence_item SET numeric_value=20 WHERE value_id=6')
        self.assertEqual(self.reconcile('STD-001a')['recomputed'],25)

    def test_count_tolerance_is_exact(self):
        self.db.execute('UPDATE fact_kpi_value SET value_numeric=4.4 WHERE value_id=4')
        self.assertFalse(self.reconcile('AI-003')['ok'])

    def test_weight_child_and_cached_contribution_tampering(self):
        for sql in ['UPDATE fact_kpi_component SET weight=weight+0.1 WHERE parent_value_id=9',
                    'UPDATE fact_kpi_component SET component_value=component_value+1 WHERE parent_value_id=9',
                    'UPDATE fact_kpi_component SET contribution=contribution+1 WHERE parent_value_id=9',
                    'UPDATE fact_kpi_value SET value_numeric=value_numeric+1 WHERE value_id=8']:
            with self.subTest(sql=sql):
                self.db.execute('SAVEPOINT mutate');self.db.execute(sql)
                self.assertFalse(self.reconcile('STD-001')['ok'])
                self.db.execute('ROLLBACK TO mutate')

    def test_evidence_reference_and_scope_tampering(self):
        for change in ["evidence_ref=NULL","scope_id='other'","period_start='2026-06-01'","source_key=NULL"]:
            self.db.execute('SAVEPOINT mutate')
            self.db.execute('UPDATE fact_evidence_item SET '+change+' WHERE value_id=1')
            self.assertFalse(self.reconcile('AI-001')['ok'])
            self.db.execute('ROLLBACK TO mutate')

    def test_unknown_axis_fails(self):
        with self.assertRaisesRegex(ValueError,'Unsupported drill axis'):
            self.engine.drill('AI-001','SCOPE-GLOBAL','2026-07-31','imaginary-axis')

    def test_history_uses_catalog_version_even_when_not_current(self):
        self.db.execute("UPDATE dim_card SET is_current=0 WHERE card_id='AI-001'")
        self.assertTrue(self.reconcile('AI-001')['ok'])
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM vw_kpi_current WHERE value_id=1').fetchone()[0],0)

    def test_confidence_null_board_gate_and_invalid_green(self):
        for change in ["data_confidence=NULL, rag='green', validity_status='valid'",
                       "data_confidence=84, rag='green', validity_status='valid', reporting_context='board'",
                       "data_confidence=90, rag='green', validity_status='provisional'",
                       "is_na=1, value_numeric=NULL, rag='green'",
                       'denominator=-1']:
            with self.subTest(change=change), self.assertRaises(sqlite3.IntegrityError):
                self.db.execute('UPDATE fact_kpi_value SET '+change+' WHERE value_id=1')
        self.db.execute("UPDATE fact_kpi_value SET data_confidence=85,rag='green',validity_status='valid',reporting_context='board' WHERE value_id=1")

    def test_views_keep_missing_evidence_and_recompute_weighted_average(self):
        self.assertEqual(self.db.execute('SELECT recon_status FROM vw_recon_component WHERE value_id=8').fetchone()[0],'ARITHMETIC_OK')
        self.db.execute('DELETE FROM fact_evidence_item WHERE value_id=1')
        self.assertEqual(self.db.execute('SELECT recon_status FROM vw_recon_ratio_count WHERE value_id=1').fetchone()[0],'MISSING_EVIDENCE')
        self.db.execute('DELETE FROM fact_kpi_component WHERE parent_value_id=8')
        self.assertEqual(self.db.execute('SELECT recon_status FROM vw_recon_component WHERE value_id=8').fetchone()[0],'MISSING_COMPONENTS')

    def test_ranking_never_claims_self_sorted_rows_are_independent_proof(self):
        result=self.engine.reconcile('STD-003','SCOPE-GLOBAL','2026-07-31')
        self.assertEqual(result['stored'],0)
        self.assertFalse(result['ok'])
        self.assertEqual(result['assurance'],'not_implemented')



class BoundaryRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.rag=staticmethod(module('thresholds','reference/thresholds.py').assess)

    def test_capacity_boundaries_without_gaps_or_overlap(self):
        for value,expected in [(74.99,'red'),(75,'amber'),(89.99,'amber'),(90,'green'),(110,'green'),(110.01,'amber'),(125,'amber'),(125.01,'red')]:
            with self.subTest(value=value):self.assertEqual(self.rag('SOC-063',value,confidence=90)['rag'],expected)

    def test_exactly_thirty_days_is_red(self):
        for cid in ['STD-019','STD-055']:
            for value,expected in [(0,'green'),(0.1,'amber'),(29.99,'amber'),(30,'red')]:
                self.assertEqual(self.rag(cid,value,confidence=90,critical_override=False)['rag'],expected)
            self.assertEqual(self.rag(cid,1,confidence=90,critical_override=True)['rag'],'red')

    def test_plan_equality_and_small_shortfalls(self):
        for value,expected in [(100,'green'),(99,'amber'),(90,'amber'),(75,'amber'),(74.9,'red')]:
            self.assertEqual(self.rag('STD-012',value,confidence=90,baseline=100)['rag'],expected)
        self.assertEqual(self.rag('STD-012',0,confidence=90,baseline=0)['validity_status'],'not_applicable')

    def test_growth_zero_baseline_and_override(self):
        for value,expected in [(99,'green'),(100,'amber'),(101,'amber'),(120,'amber'),(150,'amber'),(150.1,'red')]:
            self.assertEqual(self.rag('STD-015',value,confidence=90,baseline=100,critical_override=False)['rag'],expected)
        self.assertEqual(self.rag('STD-015',0,confidence=90,baseline=0,critical_override=False)['rag'],'amber')
        self.assertEqual(self.rag('STD-015',1,confidence=90,baseline=0,critical_override=False)['rag'],'red')
        self.assertEqual(self.rag('STD-015',1,confidence=90,baseline=100,critical_override=True)['rag'],'red')

    def test_green_requires_known_context_confidence(self):
        for confidence in [None,float('nan'),float('inf'),84]:
            result=self.rag('SOC-063',100,confidence=confidence,context='board')
            self.assertIsNone(result['rag'])
            self.assertEqual(result['validity_status'],'provisional')
        self.assertEqual(self.rag('STD-005',-0.1,confidence=90)['rag'],'red')


class CatalogValidatorRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.formula=module('formula_audit','tools/formula_audit.py')
        cls.cards=yaml.safe_load((ROOT/'catalog/osms-catalog.yaml').read_text())['cards']

    def test_cycle_zero_denominator_and_wrong_composite_total(self):
        for cid,field,value,expected in [
            ('STD-001','formula','p(STD-001)','cyclic formula dependency'),
            ('HRM-004','formula','reported_simulations / 0','literal zero denominator'),
            ('STD-069','calculation_example',None,'composite example result')]:
            cards=copy.deepcopy(self.cards)
            card=next(c for c in cards if c['id']==cid)
            card[field]=value if value is not None else card[field].replace('= 75 →','= 999 →')
            with tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp)/'mutant.yaml';path.write_text(yaml.safe_dump({'cards':cards}))
                findings=self.formula.audit(path)
            self.assertTrue(any(expected in message for _,message in findings),(cid,findings))


class ReleaseAndExportRegressionTests(unittest.TestCase):
    def test_full_card_export_and_schema(self):
        import jsonschema
        cards=yaml.safe_load((ROOT/'catalog/osms-catalog.yaml').read_text())['cards']
        exported={c['id']:c for c in json.loads((Path(temporary.name)/'catalog.json').read_text())}
        schema=json.loads((ROOT/'schema/osms-card.schema.json').read_text())
        validator=jsonschema.Draft202012Validator(schema)
        self.assertEqual(len(exported),327)
        for card in cards:
            self.assertFalse(list(validator.iter_errors(card)),card['id'])
            for field,value in card.items():self.assertEqual(exported[card['id']][field],value)
        invalid=copy.deepcopy(cards[0]);invalid['accountable_owner']='   '
        self.assertTrue(list(validator.iter_errors(invalid)))

    def test_candidate_release_guard(self):
        guard=module('release_guard','tools/release_guard.py')
        catalog={'version':'0.9.1','release_phase':'working_draft'}
        guard.validate('v0.9.1-draft',catalog)
        for tag in ['v0.9.1','v0.9.10','v0.9.2-draft']:
            with self.assertRaises(ValueError):guard.validate(tag,catalog)

    def test_seed_versions_match_catalog(self):
        catalog=drill.Catalog(ROOT/'catalog/osms-catalog.yaml')
        con=drill.build_demo_db(ROOT/'reference/star_schema.sql',ROOT/'reference/seed_reference_data.sql')
        try:
            self.assertEqual(dict(con.execute('SELECT card_id,card_version FROM dim_card')),
                             {cid:card.raw['card_version'] for cid,card in catalog.cards.items()})
        finally:con.close()

    def test_general_ratio_is_unscaled_and_can_exceed_one(self):
        catalog=drill.Catalog(ROOT/'catalog/osms-catalog.yaml')
        con=drill.build_demo_db(ROOT/'reference/star_schema.sql',ROOT/'reference/seed_reference_data.sql')
        try:
            key=con.execute("SELECT card_key FROM dim_card WHERE card_id='HRM-004'").fetchone()[0]
            con.execute('UPDATE fact_kpi_value SET card_key=?,value_numeric=?,numerator=17,denominator=3 WHERE value_id=1',(key,17/3))
            con.execute('UPDATE fact_evidence_item SET card_key=?,in_denominator=NOT in_numerator WHERE value_id=1',(key,))
            result=drill.DrillEngine(con,catalog).reconcile('HRM-004','SCOPE-GLOBAL','2026-07-31')
            self.assertTrue(result['ok'])
            self.assertEqual(result['recomputed'],17/3)
        finally:con.close()


class ExcelRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.xl=module('xlsx_dialect','recipes/xlsx_dialect.py')
        cls.specs=json.loads((Path(temporary.name)/'excel_candidates.json').read_text())['candidates']

    def evaluate(self,cid,rows):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'case.xlsx'
            outputs=self.xl.build_workbook(self.specs[cid]['spec'],{'rows':rows},path)
            return self.xl.eval_formulas(str(path),outputs)

    def test_mitigation_and_blank_dates(self):
        base=dict(record_id='r1',severity='critical',internet_facing=True,scope_id='prod',due_at='2026-06-20T00:00:00Z',remediated_at=None,mitigated_at=None,validation_status='validated')
        self.assertEqual(self.evaluate('STD-016',[base])['sla_compliance_pct'],0)
        self.assertEqual(self.evaluate('STD-016',[{**base,'mitigated_at':'2026-06-19T00:00:00Z'}])['sla_compliance_pct'],100)
        self.assertEqual(self.evaluate('STD-016',[{**base,'mitigated_at':'2026-06-21T00:00:00Z'}])['sla_compliance_pct'],0)

    def test_missing_composite_and_duplicate_penalties(self):
        rows=copy.deepcopy(fixtures['STD-069']['rows']);rows[0]['subscore_value']=None
        self.assertEqual(str(self.evaluate('STD-069',rows)['value']),'#N/A')
        rows=copy.deepcopy(fixtures['STD-001']['rows']);rows[-1]['child_card_id']='STD-001a'
        self.assertEqual(str(self.evaluate('STD-001',rows)['value']),'#N/A')


if __name__=='__main__':unittest.main()
