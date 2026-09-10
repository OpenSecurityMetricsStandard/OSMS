# SPDX-License-Identifier: MIT
"""Independent boundary oracles for the additional execution profiles."""
import copy
import importlib.util
import json
import math
import pathlib
import sys
import tempfile
import unittest
import duckdb
import pandas as pd
import yaml

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'recipes'));sys.path.insert(0,str(ROOT/'reference'))
import soc003
import esql_exact
import xlsx_dialect as xl
import assurance
from portable import ratios


class SOC003Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=json.loads((ROOT/'recipes/fixtures/soc003.json').read_text())
        cls.card=next(c for c in yaml.safe_load((ROOT/'catalog/osms-catalog.yaml').read_text())['cards'] if c['id']=='SOC-003')

    def run_profiles(self,rows):
        df=pd.DataFrame(rows,columns=self.fixture['fields'])
        for f,t in self.fixture['fields'].items():
            if t=='date':df[f]=pd.to_datetime(df[f],utc=True,format='mixed')
        ps,pe='2026-06-01T00:00:00Z','2026-07-01T00:00:00Z'
        results=[soc003.compute(df,ps,pe,'prod')]
        for dialect in ['gsql','pg']:
            with duckdb.connect() as con:
                con.register('incidents',df)
                q=soc003.sql(dialect)
                for k in ['period_start','period_end','scope_id']:q=q.replace(':'+k,'$'+k)
                cur=con.execute(q,{'period_start':ps,'period_end':pe,'scope_id':'prod'})
                results.append(dict(zip([d[0] for d in cur.description],cur.fetchone())))
        for result in results[1:]:
            for key,expected in results[0].items():
                if isinstance(expected,float):self.assertAlmostEqual(result[key],expected,places=8,msg=key)
                else:self.assertEqual(result[key],expected,key)
        return results[0]

    def test_hand_calculated_fixture(self):
        result=self.run_profiles(self.fixture['rows'])
        for key,expected in self.fixture['expect'].items():self.assertAlmostEqual(result[key],expected,msg=key)

    def test_duplicate_values_even_median(self):
        rows=[]
        for i,h in enumerate([1,1,1,100]):
            row=copy.deepcopy(self.fixture['rows'][0]);row.update(incident_id=str(i),resolved_at=(pd.Timestamp('2026-06-10',tz='UTC')+pd.Timedelta(hours=h)).isoformat());rows.append(row)
        result=self.run_profiles(rows)
        self.assertEqual(result['mttr_p50_h'],1);self.assertEqual(result['mttr_p90_h'],100)
        rows[0]['resolved_at']='2026-06-10T02:00:00Z';rows[1]['resolved_at']='2026-06-10T04:00:00Z'
        result=self.run_profiles(rows[:2]);self.assertEqual(result['mttr_p50_h'],3)

    def test_component_failure_does_not_mask_other_output(self):
        for field,value in [('ack_at',None),('ack_at','2026-06-09T00:00:00Z'),('ack_at','2026-06-20T00:00:00Z')]:
            rows=copy.deepcopy(self.fixture['rows']);rows[0][field]=value
            result=self.run_profiles(rows)
            self.assertEqual(result['mtta_invalid_cases'],1);self.assertIsNone(result['mtta_p90_h'])
            self.assertEqual(result['mtta_status'],'invalid_data');self.assertEqual(result['mttr_p90_h'],30)

    def test_identity_and_evidence_fail_closed(self):
        for kind in ['duplicate','missing_id','missing_evidence']:
            rows=copy.deepcopy(self.fixture['rows'])
            if kind=='duplicate':rows.append(dict(rows[0]))
            else:rows[0]['incident_id' if kind=='missing_id' else 'evidence_ref']=' '
            result=self.run_profiles(rows)
            self.assertGreater(result['identity_errors'],0)
            self.assertIsNone(result['mttr_p50_h']);self.assertIsNone(result['open_cases_at_period_end'])

    def test_timezone_and_period_edges(self):
        row=copy.deepcopy(self.fixture['rows'][0]);row['detected_at']='2026-06-10T02:00:00+02:00'
        self.assertEqual(self.run_profiles([row])['mttr_p50_h'],2)
        row['resolved_at']='2026-07-01T00:00:00Z'
        result=self.run_profiles([row]);self.assertEqual(result['closed_cases'],0);self.assertEqual(result['open_cases_at_period_end'],1)
        row['detected_at']='2026-07-01T00:00:00Z'
        self.assertEqual(self.run_profiles([row])['open_cases_at_period_end'],0)

    def test_no_rows_contract(self):
        result=self.run_profiles([])
        self.assertEqual(result['closed_cases'],0);self.assertEqual(result['mttr_status'],'not_applicable');self.assertIsNone(result['mttr_p50_h'])

    def test_excel_real_formulas_positive_and_missing_pair(self):
        spec=soc003.excel_spec(self.card['minimum_data_fields'])
        with tempfile.TemporaryDirectory() as folder:
            for invalid in [False,True]:
                fixture=copy.deepcopy(self.fixture)
                if invalid:fixture['rows'][0]['ack_at']=None
                path=str(pathlib.Path(folder)/('invalid.xlsx' if invalid else 'valid.xlsx'))
                out=xl.build_workbook(spec,fixture,path);result=xl.eval_formulas(path,out)
                self.assertAlmostEqual(result['mttr_p90_h'],30)
                if invalid:self.assertEqual(result['mtta_p90_h'],'#N/A');self.assertEqual(result['mtta_invalid_cases'],1)
                else:
                    for k,v in self.fixture['expect'].items():self.assertAlmostEqual(result[k],v,msg=k)

    def test_case_collisions_scope_and_literal_wildcard_ids(self):
        rows=copy.deepcopy(self.fixture['rows'][:2]);rows[0]['incident_id']='CaseA';rows[1]['incident_id']='casea'
        self.assertEqual(self.run_profiles(rows)['identity_errors'],2)
        rows=copy.deepcopy(self.fixture['rows']);rows[-1]['scope_id']='PROD';rows[-1]['incident_id']=rows[0]['incident_id']
        rows[1]['incident_id']='case*'
        self.assertEqual(self.run_profiles(rows)['identity_errors'],0)
        with tempfile.TemporaryDirectory() as folder:
            path=str(pathlib.Path(folder)/'ids.xlsx');spec=soc003.excel_spec(self.card['minimum_data_fields'])
            out=xl.build_workbook(spec,{'rows':rows,'params':self.fixture['params']},path)
            result=xl.eval_formulas(path,out);self.assertEqual(result['identity_errors'],0);self.assertEqual(result['mttr_p90_h'],30)

    def test_esql_multiset_reducer_and_truncation(self):
        fields=list(esql_exact.queries()['rows'].split('KEEP ')[1].split(' |')[0].split(', '))
        rows=[r for r in self.fixture['rows'] if r['scope_id']=='prod']
        response={'columns':[{'name':f} for f in fields],'values':[[r.get(f) for f in fields] for r in rows]}
        count={'columns':[{'name':'source_rows'}],'values':[[len(rows)]]}
        kwargs=dict(period_start='2026-06-01',period_end='2026-07-01',scope_id='prod',snapshot_hash='a'*64)
        result=esql_exact.reduce_export(count,response,**kwargs)['result'];self.assertEqual(result['mttr_p90_h'],30)
        bad=copy.deepcopy(response);bad['values'].pop()
        with self.assertRaises(ValueError):esql_exact.reduce_export(count,bad,**kwargs)
        bad=copy.deepcopy(response);bad['is_partial']=True
        with self.assertRaises(ValueError):esql_exact.reduce_export(count,bad,**kwargs)


class RatioProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profiles=ratios.generate(yaml.safe_load((ROOT/'catalog/osms-catalog.yaml').read_text())['cards'])

    @staticmethod
    def row(c,a=3.,b=4.):
        return {**{k:c[k] for k in ['card_id','card_version','contract_hash','numerator_name','denominator_name']},
                'scope_id':'prod','period_start':'2026-06-01','period_end':'2026-07-01',
                'numerator':a,'denominator':b,'numerator_evidence_ref':'fixture:num','denominator_evidence_ref':'fixture:den',
                'source_system':'fixture','source_snapshot_hash':'a'*64}

    def test_every_literal_card_has_eight_calculation_profiles(self):
        self.assertEqual(len(self.profiles),207)
        for p in self.profiles.values():
            self.assertEqual(set(p['dialects']),set(ratios.DIALECTS));self.assertEqual(p['contract']['stage'],'calculation_inputs')
            self.assertEqual(p['contract']['source_adapter_status'],'required')

    def test_independent_oracles_for_every_quotient_python_and_sql(self):
        with duckdb.connect() as con:
            for cid,p in self.profiles.items():
                c=p['contract'];ns={};exec(p['dialects']['py'],ns)
                cases=[([self.row(c)],75. if c['scale']==100 else .75,'ok'),
                       ([self.row(c,0,0)],None,'not_applicable'),([],None,'missing_input'),
                       ([self.row(c),self.row(c)],None,'invalid_input'),
                       ([self.row(c,8,4)],None if c['kind']=='proportion' else 200. if c['scale']==100 else 2.,'invalid_input' if c['kind']=='proportion' else 'ok'),
                       ([{**self.row(c),'card_version':'stale'}],None,'invalid_input'),
                       ([{**self.row(c),'denominator_evidence_ref':''}],None,'invalid_input'),
                       ([self.row(c,3,-1)],None,'invalid_input'),([self.row(c,float('nan'),4)],None,'invalid_input'),
                       ([self.row(c,-2,4)],-.5*c['scale'] if c['numerator_min']<0 else None,'ok' if c['numerator_min']<0 else 'invalid_input')]
                for rows,value,status in cases:
                    with self.subTest(card=cid,case=status,rows=len(rows)):
                        expected={'value':value,'evaluation_status':status}
                        self.assertEqual(ns['compute'](rows,'2026-06-01','2026-07-01','prod'),expected)
                        df=pd.DataFrame(rows,columns=ratios.COLUMNS)
                        for f in ['numerator','denominator']:df[f]=df[f].astype('float64')
                        for f in ratios.COLUMNS:
                            if f not in ['numerator','denominator']:df[f]=df[f].astype('string')
                        con.register('metric_inputs',df)
                        q=p['dialects']['gsql']
                        for k in ['period_start','period_end','scope_id']:q=q.replace(':'+k,'$'+k)
                        cur=con.execute(q,{'period_start':'2026-06-01','period_end':'2026-07-01','scope_id':'prod'})
                        got=dict(zip([d[0] for d in cur.description],cur.fetchone()));self.assertEqual(got,expected)

    def test_spreadsheet_domains_and_negative_return(self):
        with tempfile.TemporaryDirectory() as folder:
            for cid,a,b,expected in [('SOC-023',3,4,75),('HRM-004',8,4,2),('SOC-063',8,4,200),('STD-005',-2,4,-.5),('SOC-023',8,4,'#N/A')]:
                p=self.profiles[cid];row=self.row(p['contract'],a,b)
                for f in ['period_start','period_end']:row[f]+='T00:00:00Z'
                spec=p['excel_spec'];fixture={'rows':[row]};path=str(pathlib.Path(folder)/'ratio.xlsx')
                outputs=xl.build_workbook(spec,fixture,path);actual=xl.eval_formulas(path,outputs)['value']
                self.assertEqual(actual,expected)


class AssuranceTests(unittest.TestCase):
    def confidence_input(self):return {k:{'passed':95,'eligible':100,'evidence_ref':'fixture:'+k,'check_definition_version':'1','mandatory_failures':[]} for k in assurance.CONFIDENCE_WEIGHTS}
    def test_confidence_numeric_and_noncompensable(self):
        dims=self.confidence_input();args=('1','prod','2026-06-01','2026-07-01')
        result=assurance.confidence(dims,*args,reported_card_id='SOC-003',reported_card_version='0.9.1');self.assertEqual(result['score'],95);self.assertTrue(result['management_green_eligible'])
        dims['reconciliation_quality']['mandatory_failures']=['source_total_mismatch']
        result=assurance.confidence(dims,*args,reported_card_id='SOC-003',reported_card_version='0.9.1');self.assertEqual(result['score'],95);self.assertFalse(result['operational_green_eligible'])
        dims['freshness'].update(passed=0,eligible=0)
        self.assertIsNone(assurance.confidence(dims,*args,reported_card_id='SOC-003',reported_card_version='0.9.1')['score'])
        del dims['consistency']
        with self.assertRaises(ValueError):assurance.confidence(dims,*args,reported_card_id='SOC-003',reported_card_version='0.9.1')
    def test_normalization_direction_band_and_zero_width(self):
        p=dict(profile_id='fixture',profile_version='1',card_id='SOC-003',card_version='0.9.1',output_id='mttr_p90_h',unit='hours',evidence_ref='fixture:anchors',direction='lower',target=24,red=48)
        for raw,expected in [(12,100),(24,100),(36,50),(48,0),(60,0)]:self.assertEqual(assurance.normalize(raw,p)['posture_score'],expected)
        with self.assertRaises(ValueError):assurance.normalize(24,{**p,'red':24})
        p.update(direction='band',red_low=75,target_low=90,target_high=110,red_high=125)
        for raw,expected in [(75,0),(82.5,50),(90,100),(110,100),(117.5,50),(125,0)]:self.assertEqual(assurance.normalize(raw,p)['posture_score'],expected)
    def test_sample_size_and_selection(self):
        args=dict(sampling_design='independent_probability_sample',selection_note='random sample from declared frame')
        small=assurance.wilson_interval(1,1,**args);large=assurance.wilson_interval(1000,1000,**args)
        self.assertAlmostEqual(small['lower'],.20654931437723745)
        self.assertGreater(large['lower'],.996)
        self.assertIsNone(assurance.wilson_interval(1,1,sampling_design='convenience_sample',selection_note='volunteers')['lower'])
    def test_joint_risk_preserves_dependencies(self):
        p={k:'fixture' for k in ['profile_id','profile_version','horizon','currency','dependence_model','generator_version','input_snapshot_hash','control_credit_policy','evidence_ref']}
        aligned=[{'draw_id':str(i),'losses':{'a':a,'b':b}} for i,(a,b) in enumerate([(0,0),(0,0),(100,100),(100,100)])]
        offset=[{'draw_id':str(i),'losses':{'a':a,'b':b}} for i,(a,b) in enumerate([(0,100),(0,100),(100,0),(100,0)])]
        a=assurance.portfolio_risk(aligned,['a','b'],p,150);b=assurance.portfolio_risk(offset,['a','b'],p,150)
        self.assertEqual(a['mean'],100);self.assertEqual(b['mean'],100)
        self.assertEqual(a['p90'],200);self.assertEqual(b['p90'],100);self.assertEqual(a['probability_exceeding_appetite'],.5);self.assertEqual(b['probability_exceeding_appetite'],0)
        aligned[0]['losses'].pop('b')
        with self.assertRaises(ValueError):assurance.portfolio_risk(aligned,['a','b'],p,150)


class ProfileBindingTests(unittest.TestCase):
    def dsps_inputs(self):
        context={'scope_id':'prod','period_start':'2026-06-01','period_end':'2026-07-01','profile_version':'1'}
        profiles={};rows=[]
        for cid,w in assurance.DSPS_WEIGHTS.items():
            p={'profile_id':cid,'profile_version':'1','card_id':cid,'card_version':'0.9.2','output_id':'fixture_output','unit':'score','evidence_ref':'fixture:anchors','direction':'higher','red':0,'target':100}
            profiles[cid]=p;rows.append({**context,'component_id':cid,'raw_value':80,'posture_score':80,'output_id':'fixture_output','card_version':'0.9.2','normalization_hash':assurance.fingerprint(p),'weight':w,'evidence_ref':'fixture:child'})
        penalties=[{**context,'card_id':'STD-001a','card_version':'0.9.1','value':10,'evidence_ref':'fixture:tsp'}, {**context,'card_id':'STD-001b','card_version':'0.9.1','value':5,'evidence_ref':'fixture:edp'}]
        return rows,penalties,profiles,context,{'STD-001a':'0.9.1','STD-001b':'0.9.1'}
    def test_dsps_rebuilds_then_deducts(self):
        args=self.dsps_inputs();r=assurance.dsps(*args)
        self.assertEqual(r['before_penalties'],80);self.assertEqual(r['value'],65)
        for kind in ['raw','period','weight','version','normalization','duplicate_penalty']:
            rows,penalties,profiles,context,versions=self.dsps_inputs()
            if kind=='raw':rows[0]['raw_value']=70
            elif kind=='period':rows[0]['period_end']='2026-08-01'
            elif kind=='weight':rows[0]['weight']=.99
            elif kind=='version':penalties[0]['card_version']='stale'
            elif kind=='normalization':profiles[rows[0]['component_id']]['target']=200
            else:penalties[1]['card_id']='STD-001a'
            with self.assertRaises(ValueError,msg=kind):assurance.dsps(rows,penalties,profiles,context,versions)
    def test_ranking_raw_inputs_tie_and_max_zero(self):
        context=dict(scope_id='prod',period_end='2026-07-01',card_version='0.9.1',profile_version='1')
        profiles={'a':dict(criticality_multiplier=2,dependency_multiplier=1,evidence_ref='fixture:a'),'b':dict(criticality_multiplier=1,dependency_multiplier=1,evidence_ref='fixture:b')}
        rows=[{**context,'service_id':'a','asset_id':'x','asset_risk_value':40,'evidence_ref':'fixture:x'}, {**context,'service_id':'b','asset_id':'y','asset_risk_value':80,'evidence_ref':'fixture:y'}]
        result=assurance.rank_services(rows,profiles,context)['ranking']
        self.assertEqual([r['service_id'] for r in result],['a','b']);self.assertEqual([r['rank'] for r in result],[1,1]);self.assertEqual([r['display_score'] for r in result],[100,100])
        rows[1]['asset_risk_value']=40
        self.assertEqual(assurance.rank_services(rows,profiles,context)['ranking'][1]['display_score'],50)
        rows[0]['asset_risk_value']=rows[1]['asset_risk_value']=0
        self.assertEqual([r['display_score'] for r in assurance.rank_services(rows,profiles,context)['ranking']],[0,0])
        with self.assertRaises(ValueError):assurance.rank_services(rows+[rows[0]],profiles,context)

class LineageContractTests(unittest.TestCase):
    def test_all_catalog_axes_have_explicit_sql_mappings(self):
        import drill_engine
        catalog=drill_engine.Catalog(ROOT/'catalog/osms-catalog.yaml')
        axes={a for c in catalog.cards.values() for a in c.axes}
        self.assertEqual(len(axes),50)
        self.assertTrue(all(c.axes or c.has_parts for c in catalog.cards.values()))
        self.assertIn("reporting-obligation class",catalog["SOC-053"].axes)
        self.assertIn("risk class/weight",catalog["SOC-078"].axes)
        self.assertTrue(axes<=set(drill_engine.AXIS_SQL))
        self.assertIn('detection source',catalog['SOC-002'].axes)
        # Check query execution over the schema, not only membership in a dict.
        import sqlite3
        con=sqlite3.connect(':memory:');con.executescript((ROOT/'reference/star_schema.sql').read_text())
        for axis in axes:
            expr,joins=drill_engine.AXIS_SQL[axis]
            con.execute('SELECT '+expr+' FROM fact_evidence_item e '+joins+' LIMIT 0')
        self.assertNotEqual(drill_engine.AXIS_SQL['criticality'],drill_engine.AXIS_SQL['severity'])

class PublicationContractTests(unittest.TestCase):
    def test_names_and_calculation_types_match_preserved_formulas(self):
        cards={c['id']:c for c in yaml.safe_load((ROOT/'catalog/osms-catalog.yaml').read_text())['cards']}
        self.assertEqual(cards['SOC-023']['name'],'False Positive Share of Reviewed Alerts')
        self.assertEqual(cards['SOC-023']['formula'],'(false_positive_alerts / total_alerts_reviewed) * 100')
        self.assertIn('Share',cards['AIM-011']['name']);self.assertIn('/ total_ai_inputs',cards['AIM-011']['formula'])
        self.assertIn('Tolerance Hit Rate',cards['SOC-072']['name']);self.assertEqual(cards['STD-024']['calculation_type'],'Ratio')
        self.assertTrue(all(c['lifecycle']=='draft' for c in cards.values()))
        self.assertIn('dq-checks/1',cards['STD-011']['confidence_production_rule'])
        self.assertFalse(any('Part I' in str(c) for c in cards.values()))

    def test_native_fixture_queries_preserve_parameters_and_case_selection(self):
        spec=importlib.util.spec_from_file_location('profile_runner',ROOT/'recipes/ci/profile_runner.py');runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
        card=next(c for c in yaml.safe_load((ROOT/'catalog/osms-catalog.yaml').read_text())['cards'] if c['id']=='SOC-023')
        p=ratios.generate([card])['SOC-023']
        from portable.cases import cases
        for case in cases(p['contract']):
            for engine in ['spl','esql']:
                q=runner.inline_query(p,case,engine)
                self.assertNotIn('$period_',q);self.assertNotIn('?scope_id',q)
                self.assertNotIn('FROM metric_inputs',q);self.assertNotIn('index=osms',q)
                self.assertIn('evaluation_status',q)
        self.assertIn('where card_id="SOC-023" AND scope_id="prod"',runner.inline_query(p,cases(p['contract'])[0],'spl'))

if __name__=='__main__':unittest.main()
