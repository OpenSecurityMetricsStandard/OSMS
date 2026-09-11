# SPDX-License-Identifier: MIT
"""Hand specified arithmetic examples, independent of the calculation IR.

Expected results are never obtained from a renderer or from model.compute.
The common metadata is synthetic evidence for testing only.
"""
import copy
import datetime as dt
from .model import COMMON
from .render import PARAMS

def metadata(p,index=0):
    return {'card_id':p['card_id'],'card_version':p['card_version'],'contract_hash':p['contract_hash'],
            **{k:PARAMS[k] for k in ('scope_id','segment_id','period_start','period_end')},
            'record_id':f'record:{index}','evidence_ref':f'fixture:{index}',
            'source_system':'synthetic','source_snapshot_hash':'a'*64}

def defaults(p):
    r={}
    for name,s in p['inputs'].items():
        if name in COMMON:continue
        r[name]=s['enum'][0] if 'enum' in s else True if s['type']=='boolean' else '2026-06-15T00:00:00Z' if s['type']=='timestamp' else max(s.get('minimum',0),min(s.get('maximum',1),1)) if s['type']=='number' else 'fixture:reference/1'
    return r

def examples(plans):
    result={}
    def put(cid,rows,expected,status=None):
        if isinstance(rows,dict):rows=[rows]
        p=plans[cid]
        result[cid]=[{'name':'independent_arithmetic','rows':[{**defaults(p),**metadata(p,i),**r} for i,r in enumerate(rows)],
                      'params':dict(PARAMS),'expected':expected,**({'status':status} if status else {})}]
    # Unequal score components make exchanged or omitted weights observable.
    for cid,values,value in [
        ('STD-075',[20,40,60,80,100],57),('STD-068',[20,40,60,80,100],57),
        ('STD-069',[20,40,60,80],50),('SOC-047',[20,40,60,80],49),
        ('SOC-051',[20,40,60,80],46),('SOC-009',[20,40,60,80],43),
        ('SOC-010',[20,40,60],30),('SOC-033',[20,40,60,80],46),
        ('SOC-056',[20,40,60,80,100],57),('SOC-059',[20,40,60,80],41),
        ('SOC-066',[10,20,30,40,50,60],31.5),('SOC-067',[20,40,60,80],39),
        ('SOC-073',[20,40,60,80],46),('SOC-042',[20,40,60,80],46),
        ('STD-052',[20,40,80],44),('STD-064',[20,40,80],42),('STD-071',[10,20,30,40],23)]:
        names=[k for k,s in plans[cid]['inputs'].items() if k not in COMMON and s['type']=='number']
        put(cid,dict(zip(names,values)),{'value':value})
    put('CRY-001',dict(count_inventoried_crypto_assets=80,count_crypto_assets_in_scope=100,count_pqc_assessed_crypto_assets=40,count_crypto_assets_with_migration_plan=9,count_migration_obligated_crypto_assets=10),dict(value=74,inventorying=80,assessment=50,migration=90))
    put('STD-003a',dict(std032_risk_posture=80,std062_assurance_posture=70,std070_risk_posture=20,open_critical_risks=3),dict(risk_index=47,open_critical_risks=3))
    dq={'mandatory_failures':0}
    for prefix,passed in zip(['completeness','freshness','source_authority','consistency','reconciliation_quality'],[10,8,9,6,10]):dq.update({prefix+'_passed':passed,prefix+'_eligible':10})
    put('STD-011',dq,dict(value=87,operational_eligible=1,management_eligible=1))
    put('LOG-005',[dict(weight=.25,filled_occurrences=8,expected_occurrences=10),dict(weight=.75,filled_occurrences=4,expected_occurrences=10)],dict(value=50))
    for cid,rows,expected in [
        ('AIM-012',dict(autonomous_investigations_per_class=6,baseline_analyst_minutes_per_class=25),2.5),
        ('STD-030',dict(usage_volume=2,data_sensitivity=3,access_risk=4,governance_gap=.5),12),
        ('STD-043',dict(exposure=.5,data_sensitivity=.4,vulnerability=.3,control_gap=.2,business_criticality=.1),.12),
        ('STD-045',dict(privilege=.5,scope_factor=.25,external_access=1,policy_risk=.5),6.25),
        ('STD-056',dict(residual_risk=80,age_factor=.5,compensating_control_gap=.25),10),
        ('STD-035',dict(dormancy_days=20,privilege_weight=3,external_access_weight=1.5,mfa_gap=.5),45),
        ('STD-036',dict(count_deviating_assignments=7,risk_weight=3),21),
        ('STD-040',dict(access_level=.5,data_sensitivity=.4,dormancy=.3,mfa_gap=.2,owner_confidence_gap=.1),.12),
        ('STD-041',dict(weight_privilege_exposure=4,legacy_auth_allowed_or_active=True),4),
        ('STD-042',dict(criticality_weight=3,matches_toxic_combination_rules=True),3),
        ('STD-070',dict(service_criticality=8,dependency_strength=.5,sla_gap=.25,test_gap=1),1),
        ('STD-013',dict(open_hours=20,asset_criticality=4,exposure=.5,exploit_likelihood=.2,severity=.8,control_gap=.5),3.2),
        ('STD-015',dict(epss_score=.2,asset_criticality=4,exposure=.5),.4),
        ('STD-046',dict(used_permissions_90d=2,granted_permissions=10,violates_least_privilege=False,criticality_weight=3),3),
        ('STD-047',dict(runtime_exposure=.5,workload_criticality=.8,kev_flag=False,epss_score=.2),8)]:put(cid,rows,{'value':expected})
    put('SOC-035',[dict(service_downtime_minutes=30,service_criticality_weight=4),dict(service_downtime_minutes=10,service_criticality_weight=2)],dict(downtime_total=40,downtime_weighted=140))
    for cid,v,w in [('STD-006','effectiveness_score','criticality_weight'),('STD-006a','control_effectiveness','tier1_weight'),('STD-008','recovery_confidence_score','service_criticality')]:
        put(cid,[{v:80,w:2},{v:60,w:1},{v:70,w:1}],dict(value=72.5,weight_sum=4))
    put('STD-012',[dict(measure_completion=.5,expected_risk_reduction_weight=3),dict(measure_completion=1,expected_risk_reduction_weight=1)],dict(value=62.5))
    put('STD-080',[dict(kr_actual_value=20,kr_target_value=10,weight_objective_priority=1),dict(kr_actual_value=5,kr_target_value=10,weight_objective_priority=3)],dict(value=62.5))
    put('SOC-050',[dict(survey_score=5,weight=2,survey_variant='csat_1_5'),dict(survey_score=2,weight=1,survey_variant='csat_1_5')],dict(value=4,csat_score=4,nps=None))
    for cid,a,b in [('MET-007','metrics_attested_by_accountable_owner_within_freshness_sla','active_metrics_in_catalog_reporting_scope'),('DET-006','exact_initial_final_severity_matches','incidents_with_final_severity_review'),('SOC-048','count_confirmed_incidents_first_report_user','count_confirmed_incidents_total'),('SOC-025','reopened_incidents_incomplete_resolution','resolved_incidents'),('SOC-030','incidents_resolved_within_sla','incidents_opened_or_due_in_period'),('TPR-001','suppliers_with_complete_inventory','suppliers_total'),('TPR-002','controls_with_fresh_accepted_evidence','required_controls'),('TPR-006','unmanaged_concentrations_above_appetite','identified_concentrations')]:put(cid,{a:3,b:4},dict(value=75))
    put('AIM-005',dict(missed_true_positives=1,detected_true_positives=3),dict(value=25))
    put('AIM-006',dict(alerts_received=10,alerts_forwarded_to_analyst=3),dict(value=70))
    put('STD-024',dict(count_new_external_assets_or_services=12,count_days_reporting_period=30),dict(value=.4))
    put('STD-027',dict(expiring_lt_30d=2,weak_algorithms=4,unknown_owner=6,hostname_mismatch=8,certificates_in_scope=10),dict(value=46))
    put('STD-038',dict(mfa_or_compensating_control=True,vaulting=False,monitoring=True,approval=False,periodic_test=True,owner_present=False),dict(value=55))
    put('RES-004',dict(required_recovery_capacity=10,available_tested_recovery_capacity=7),dict(value=30))
    put('CFG-003',[dict(expired=True,expires_within_30_days=True,approved=False),dict(expired=False,expires_within_30_days=False,approved=True)],dict(value=50,absolute_base=2))
    put('LOG-009',[dict(expected_events=100,searchable_normalized_events=120),dict(expected_events=100,searchable_normalized_events=60)],dict(value=20))
    pairs={
      'SOC-006':(('blocked_or_detected_simulated','total_simulated','simulated_rate'),('blocked_or_detected_confirmed_real','total_confirmed_real','real_rate')),
      'TPR-004':(('critical_contracts_complete_clauses','critical_contracts_total','all_contracts_rate'),('new_critical_contracts_complete_before_signature','new_critical_contracts_total','new_contracts_rate')),
      'TPR-005':(('critical_suppliers_tested_sla','critical_suppliers_total','supplier_rate'),('critical_service_providers_tested_sla','critical_service_providers_total','service_provider_rate')),
      'TPR-007':(('critical_services_tested_exit_plan','critical_services_requiring_exit_plan','critical_services_rate'),('dora_services_tested_exit_plan','dora_services_requiring_exit_plan','dora_rate')),
      'TPR-008':(('critical_suppliers_regular_feed','critical_suppliers_feed_required','critical_supplier_rate'),('control_plane_suppliers_regular_feed','control_plane_suppliers_feed_required','control_plane_supplier_rate'))}
    for cid,parts in pairs.items():
        a,b,k=parts[0];c,d,j=parts[1];put(cid,{a:3,b:4,c:1,d:2},{k:75,j:50})
    put('SOC-080',dict(prioritized_high_and_true=3,prioritized_high=4,true_total=6),dict(precision=75,recall=50))
    put('AIM-007',dict(mttr_baseline=10,mttr_current=12),dict(value=-20))
    put('STD-004',dict(baseline_risk_score=100,current_residual_risk_score=70,plan_value_period=40),dict(burn_down=30,plan_deviation_percent=25))
    put('STD-009',dict(overdue_vulns_wsum=10,expired_exceptions_wsum=20,untested_recovery_wsum=30,stale_controls_wsum=40,unmanaged_assets_wsum=50,baseline_wsum=20),dict(value=125))
    put('SOC-022',dict(false_positive_alerts=20,total_alerts=100,low_value_alerts=40,alerts_per_analyst=60,target_alerts_per_analyst=30),dict(value=62))
    put('SOC-034',[dict(actual_effort_share=.8,expected_effort_share=.4),dict(actual_effort_share=.2,expected_effort_share=.6)],dict(value=60))
    put('SOC-064',[dict(weighted_cases_per_analyst=2,target_cv=0,worst_cv=1),dict(weighted_cases_per_analyst=6,target_cv=0,worst_cv=1)],dict(coefficient_of_variation=.5,value=50))
    put('TPR-012',[dict(criticality_weight=3,dependence_share_largest_provider=.5,baseline_concentration_value=2),dict(criticality_weight=1,dependence_share_largest_provider=.5,baseline_concentration_value=2)],dict(value=100))
    put('STD-074',[dict(actual_risk_reduction=20,expected_risk_reduction=30),dict(actual_risk_reduction=40,expected_risk_reduction=20)],dict(value=5))
    put('SOC-032',dict(manual_baseline_cost_per_case=20,automated_cost_per_case=5,automated_cases=10,automation_operating_cost=40),dict(value=110))
    put('LOG-016',dict(monthly_telemetry_platform_and_storage_cost=120,validated_usage_units=8),dict(value=15))
    put('SOC-020',dict(labor_cost=100,tool_cost_allocated=20,third_party_cost=10,downtime_cost_allocated=30,confirmed_incidents=4),dict(value=40))
    put('RES-007',dict(policy_limit_eur=100,p90_loss_exposure_eur=120,deductible_eur=20,exclusion_does_not_apply=1),dict(uncovered_exposure_eur=40,creditable_coverage_eur=80))
    special_examples(plans,put)
    # Additional independent oracles required for confidence and normalization.
    base=copy.deepcopy(result['STD-011'][0])
    for name,passed,mandatory,score,operational,management in [
        ('complete_checks',10,0,100,1,1),('operational_boundary',7,0,70,1,0),
        ('below_management',8,0,80,1,0),('mandatory_failure_overrides_score',10,1,100,0,0)]:
        c=copy.deepcopy(base);c['name']=name;c['rows'][0]['mandatory_failures']=mandatory
        for field in c['rows'][0]:
            if field.endswith('_passed'):c['rows'][0][field]=passed
            elif field.endswith('_eligible'):c['rows'][0][field]=10
        c['expected']=dict(value=score,operational_eligible=operational,management_eligible=management);result['STD-011'].append(c)
    for cid,postures,expected in [('STD-001',[5,10,15,20,25,30,35,40,45,50,55,60,65,70],26.925),('HRM-001',[10,20,30,40],22.5)]:
        c=copy.deepcopy(result[cid][0]);c['name']='unequal_normalized_leaves';row=c['rows'][0]
        prefixes=[f[:-4] for f in plans[cid]['inputs'] if f.endswith('_raw')]
        for prefix,value in zip(prefixes,postures):row[prefix+'_raw']=value if row[prefix+'_direction']=='higher' else 100-value
        if cid=='STD-001':row.update(tsp=3,edp=2)
        c['expected']={'value':expected};result[cid].append(c)
    missing=set(plans)-set(result)
    if missing:raise ValueError('Missing independent examples: '+str(sorted(missing)))
    from .output_oracles import supplement
    supplement(result)
    return result

def special_examples(plans,put):
    for cid in ['AI-003','DAT-005']:put(cid,{},dict(value=1))
    put('STD-023',dict(owner_known=False,business_purpose_known=False,in_cmdb=False),dict(value=1))
    put('STD-025',dict(is_admin_interface=True,publicly_reachable=True,approved_exception=False),dict(value=1,unapproved_exposures=1))
    put('STD-026',dict(publicly_reachable=True,approved=True,contains_sensitive_data=True),dict(value=1))
    put('STD-029',dict(critical_service=True,internet_exposed_asset_or_path=True,approved=False,controls_complete=False),dict(value=1,unapproved_exposures=1,incomplete_control_exposures=1))
    put('STD-031',dict(changed_or_new=True,approved=True,owner_unknown=True),dict(value=1))
    put('STD-032',dict(risk_score=20,documented_risk_threshold=80,owner_known=True,contract_present=False,control_status_known=True,asset_evidence_present=True),dict(value=1))
    put('STD-014',dict(open_finding=True,kev_flag=True,asset_criticality=3,detected_at='2026-06-15T00:00:00Z'),dict(value=1,outside_emergency_window=1,sla_violated=1))
    put('SOC-029',dict(severity='critical',escalated_at='2026-06-15T01:00:00Z',detected_or_triaged_at='2026-06-15T00:00:00Z'),dict(value=1,critical_over_30_minutes=1))
    put('STD-001a',[dict(active_p1_incident=False,actively_exploited_kev=True,confirmed_ioc=True,contained_at=None),dict(active_p1_incident=True,actively_exploited_kev=True,confirmed_ioc=True,contained_at='2026-06-24T12:00:00Z')],dict(value=18.035714285714285))
    put('STD-001b',[dict(severity='critical',exception_created_at='2026-06-01'),dict(severity='high',exception_created_at='2026-05-01')],dict(value=7))
    put('LOG-015',dict(first_approval_date='2026-05-01',expiry_date='2026-06-30',criticality_tier='tier0',extent='group_or_service',compensation_proven=False),dict(value=40,expired_open_exceptions=1,tier0_exception_age_max_days=61))
    # Explicit raw clocks, with 2/30-unit distributions. Median vs nearest rank
    # therefore differs; changing the estimator cannot pass unnoticed.
    clocks={
      'AIM-003':('received_at','closed_at','minutes',False), 'HRM-005':('delivered_at','reported_at','minutes',True),
      'SOC-012':('detected_at','contained_at','hours',False),'SOC-028':('detected_or_triaged_at','escalated_at','minutes',False),
      'SOC-031':('alert_created_at','acknowledged_at','minutes',False),'STD-017':('detected_at','risk_reduced_at','hours',False),
      'SOC-040':('incident_detected_at','rca_completed_at','hours',True),'SOC-001':('first_compromise_at','detected_at','hours',True),
      'SOC-002':('occurred_at','detected_at','hours',True),'STD-010':('decision_requested_at','period_end','days',False),
      'STD-077':('blocker_created_at','period_end','hours',False),'CFG-002':('first_drift_detected_at','period_end','days',False),
      'STD-055':('acceptance_date','period_end','days',False),'STD-061':('decision_request_date','decision_date','hours',True),
      'STD-019':('exception_created_at','period_end','days',False),'DET-003':('last_tuning_date','period_end','days',False),
      'DET-008':('approved_detection_request_timestamp','production_tested_rule_timestamp','days',False),
      'APP-005':('exploitability_start_timestamp','fix_deploy_timestamp','hours',False),
      'APP-010':('exposure_start_timestamp','revocation_rotation_timestamp','hours',False),
      'LOG-011':('gap_detected_at','period_end','hours',False),'SOC-053':('detected_at','reported_at','hours',False),
      'SOC-026':('vulnerability_detected_at','remediated_or_mitigated_at','hours',False),
      'SOC-078':('risk_identified_at','treatment_started_at','hours',False),'STD-078':('measure_completed_at','benefit_observed_at','days',True)}
    for cid,(start,end,unit,median) in clocks.items():
        cutoff=dt.datetime(2026,7,1,tzinfo=dt.timezone.utc) if end=='period_end' else dt.datetime(2026,6,20,tzinfo=dt.timezone.utc)
        rows=[]
        for n in [2,30]:
            row={start:(cutoff-dt.timedelta(**{unit:n})).isoformat(),end:cutoff.isoformat()}
            if cid in ['SOC-001','SOC-002']:row['confirmed_at']='2026-06-21T00:00:00Z'
            if cid=='DET-003':row.update(last_test_date=None,last_threat_intel_review_date=None,last_validation_date=None)
            rows.append(row)
        put(cid,rows,dict(p50=16 if median else 2,p90=30,valid_cases=2,invalid_cases=0))
    put('VAL-001',dict(critical_objects_tested=19,critical_objects_in_universe=20,high_critical_findings_treated_on_time=9,high_critical_findings_due=10,unmanaged_critical_findings=0),dict(scope_coverage_percent=95,remediation_coverage_percent=90,overall_band=2))
    put('STD-002a',[dict(annual_portfolio_loss=x,risk_appetite=100) for x in [0,10,100,1000]],dict(p50_loss=55,mean_loss=277.5,p90_loss=1000,probability_above_appetite=.25,draw_count=4,reporting_eligible=0))
    for cid in ['HRM-001','STD-001']:
        row={}
        for f in plans[cid]['inputs']:
            if f.endswith('_raw'):
                prefix=f[:-4];direction=plans[cid]['inputs'][prefix+'_direction']['enum'][0]
                row.update({f:75 if direction=='higher' else 25,prefix+'_target':100 if direction=='higher' else 0,prefix+'_worst':0 if direction=='higher' else 100,prefix+'_direction':direction})
        if cid=='STD-001':row.update(tsp=10,edp=5)
        put(cid,row,dict(value=60 if cid=='STD-001' else 75))
    put('STD-003',[
        dict(business_service_id='A',asset_id='a1',asset_risk=100,service_criticality=2,dependency_factor=1.5),
        dict(business_service_id='A',asset_id='a2',asset_risk=50,service_criticality=2,dependency_factor=1.5),
        dict(business_service_id='B',asset_id='b1',asset_risk=100,service_criticality=1.25,dependency_factor=1),
        dict(business_service_id='B',asset_id='b2',asset_risk=100,service_criticality=1.25,dependency_factor=1)],
        dict(services=[dict(business_service_id='A',service_risk_raw=450,service_risk=100,competition_rank=1),dict(business_service_id='B',service_risk_raw=250,service_risk=55.55555555555556,competition_rank=2)],service_count=2))

def boundaries(p,positive):
    """Cross-card counterexamples to identity, evidence and population integrity."""
    out=[copy.deepcopy(positive)]
    def invalid(name,change,status='invalid_input'):
        c=copy.deepcopy(positive);c['name']=positive['name']+'/'+name;change(c)
        c['expected']={k:None for k in p['outputs']};c['status']=status;out.append(c)
    for key,value in [('evidence_ref',''),('record_id',''),('card_version','unknown-version'),('contract_hash','0'*64)]:
        invalid('reject_'+key,lambda c,k=key,v=value:c['rows'][0].update({k:v}))
    invalid('duplicate_identity',lambda c:c['rows'].append(dict(c['rows'][0])))
    invalid('population_unverified',lambda c:c['params'].update(population_complete=False),'population_unverified')
    invalid('inverted_period',lambda c:c['params'].update(period_start='2026-07-02'))
    for typ in ['number','boolean']:
        field=next((k for k,s in p['inputs'].items() if s['type']==typ and k not in COMMON),None)
        if field:
            value=p['inputs'][field].get('minimum',0)-1 if typ=='number' else None
            invalid('reject_'+typ+'_domain',lambda c,k=field,v=value:c['rows'][0].update({k:v}))
    enum=next((k for k,s in p['inputs'].items() if 'enum' in s and s['type']=='string'),None)
    if enum:invalid('reject_unknown_enum',lambda c:c['rows'][0].update({enum:'unsupported-value'}))
    for key,value in [('period_end','2026-08-01T00:00:00Z'),('scope_id','PROD'),('segment_id','out_of_scope')]:
        c=copy.deepcopy(positive);c['name']=positive['name']+'/exclude_other_'+key
        c['rows'].append({**c['rows'][0],key:value});out.append(c)
    return out
