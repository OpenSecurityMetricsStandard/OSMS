# SPDX-License-Identifier: MIT
"""Explicit card bindings. No free-text formula inference at execution time."""
from .model import (plan,field as F,stat as S,op as O,add,mul,sub,div,choose,clip,
                    number as N,text as T,timestamp as TS,aggregate as A,weighted)

B={'type':'boolean'}
REFERENCE_PARAMETER_VERSION='osms-reference/0.9.2'

def register(cards):
    cards={c['id']:c for c in cards};result={}
    def put(cid,inputs,stats,outputs,**kw):
        result[cid]=plan(cards[cid],inputs,stats,outputs,**kw)
    def single(cid,inputs,outputs,**kw):
        put(cid,inputs,{k:A('max',v) for k,v in outputs.items()},{k:S(k) for k in outputs},single=True,**kw)
    def linear(cid,terms,invert=(),**kw):
        expr=add(*(mul(w,sub(100,F(f)) if f in invert else F(f)) for f,w in terms.items()))
        single(cid,{f:N(0,100) for f in terms},{'value':expr},**kw)
    def ratio(cid,num,den,*,outputs=None,extra=None,segments=None,proportion=True,**kw):
        inputs={num:N(),den:N(),**(extra or {})}
        constraints=[O('le',F(num),F(den))] if proportion else []
        single(cid,inputs,{'value':mul(100,div(F(num),F(den))),**(outputs or {})},row_constraints=constraints,segments=segments,**kw)

    # Explicit single-observation score definitions. Normative fixed weights are
    # in the immutable plan; unapproved local weighting cannot enter as a field.
    linear('STD-075',{'plan_quality':.25,'dependency_status':.20,'resource_availability':.15,'evidence_progress':.25,'risk_to_delivery':.15})
    linear('STD-068',{'network_isolation':.25,'identity_separation':.20,'admin_separation':.20,'monitoring':.15,'restore_access_control':.20})
    linear('STD-069',{'exercise_frequency':.25,'scenario_realism':.25,'stakeholder_participation':.25,'lessons_learned_closure':.25})
    linear('SOC-047',{'active_memberships':.25,'contributions':.25,'received_actionable_intel':.30,'sla_to_process_shared_intel':.20})
    linear('SOC-051',{'communication_timeliness_score':.4,'error_rate':.3,'stakeholder_feedback':.2,'template_usage':.1},invert=['error_rate'])
    linear('SOC-009',{'effective_coverage':.35,'detection_success':.30,'containment_success':.20,'telemetry_quality':.15})
    linear('SOC-010',{'true_positive_rate':.5,'scenario_detection_rate':.3,'normalized_false_positive_burden':.2},invert=['normalized_false_positive_burden'])
    linear('SOC-033',{'sla_compliance':.35,'normalized_mttr':.25,'reopen_rate':.20,'resource_efficiency':.20},invert=['normalized_mttr','reopen_rate'])
    linear('SOC-056',{'detection_success':.3,'false_positive_burden':.2,'coverage':.2,'availability':.15,'response_capability':.15},invert=['false_positive_burden'])
    linear('SOC-059',{'threat_to_detection_time_score':.4,'policy_playbook_update_rate':.25,'coverage_of_priority_threats':.25,'exercise_validation':.1})
    linear('SOC-066',{'governance':.20,'detection':.20,'response':.20,'people':.15,'technology':.15,'improvement':.10})
    linear('SOC-067',{'sla_triage_compliance':.35,'classification_accuracy':.30,'false_positive_burden':.20,'automation_assist_rate':.15},invert=['false_positive_burden'])
    linear('SOC-073',{'threat_report_freshness':.30,'relevance_to_asset_base':.30,'stakeholder_distribution':.20,'action_conversion_rate':.20})
    linear('SOC-042',{'phishing_sim_click_reduction':.30,'reporting_rate_increase':.30,'policy_violation_reduction':.20,'test_score_improvement':.20})

    put('STD-052',{f:N(0,100) for f in ('permission_reach_score','network_exposure_score','data_access_score')},
        {'value':A('max',weighted({'permission_reach_score':.4,'network_exposure_score':.3,'data_access_score':.3}))},{'value':S('value')},note='One selected critical workload per record; report the maximum, not the average.')
    crypto={'count_inventoried_crypto_assets':N(integer=True),'count_crypto_assets_in_scope':N(integer=True),
            'count_pqc_assessed_crypto_assets':N(integer=True),'count_crypto_assets_with_migration_plan':N(integer=True),
            'count_migration_obligated_crypto_assets':N(integer=True)}
    q1=mul(100,div(F('count_inventoried_crypto_assets'),F('count_crypto_assets_in_scope')))
    q2=mul(100,div(F('count_pqc_assessed_crypto_assets'),F('count_inventoried_crypto_assets')))
    q3=mul(100,div(F('count_crypto_assets_with_migration_plan'),F('count_migration_obligated_crypto_assets')))
    single('CRY-001',crypto,{'value':add(mul(.4,q1),mul(.3,q2),mul(.3,q3)), 'inventorying':q1,'assessment':q2,'migration':q3},
        row_constraints=[O('le',F(a),F(b)) for a,b in [('count_inventoried_crypto_assets','count_crypto_assets_in_scope'),('count_pqc_assessed_crypto_assets','count_inventoried_crypto_assets'),('count_crypto_assets_with_migration_plan','count_migration_obligated_crypto_assets')]])
    single('STD-003a',{'std032_risk_posture':N(0,100),'std062_assurance_posture':N(0,100),'std070_risk_posture':N(0,100),'open_critical_risks':N(integer=True)},
        {'risk_index':add(mul(.4,F('std032_risk_posture')),mul(.3,sub(100,F('std062_assurance_posture'))),mul(.3,F('std070_risk_posture'))),'open_critical_risks':F('open_critical_risks')},output_units={'open_critical_risks':'count'},note='Risk count is deduplicated by risk ID, not supplier ID. Posture inputs require the referenced normalization evidence.')

    # Confidence dimensions derive from pass/eligible counts, not unexplained scores.
    dqweights={'completeness':.25,'freshness':.25,'source_authority':.20,'consistency':.15,'reconciliation_quality':.15}
    inputs={'mandatory_failures':N(integer=True),'check_register_version':T(),'reported_card_id':T(cards),'reported_card_version':T(sorted({c['card_version'] for c in cards.values()}))}
    dq={}
    for name in dqweights:
        inputs[name+'_passed']=N(integer=True);inputs[name+'_eligible']=N(integer=True)
        inputs[name+'_evidence_ref']=T();dq[name]=mul(100,div(F(name+'_passed'),F(name+'_eligible')))
    score=add(*(mul(w,dq[k]) for k,w in dqweights.items()))
    single('STD-011',inputs,{'value':score,**dq,'operational_eligible':choose(O('and',O('eq',F('mandatory_failures'),0),O('ge',score,70)),1,0),
        'management_eligible':choose(O('and',O('eq',F('mandatory_failures'),0),O('ge',score,85)),1,0)},
        row_constraints=[O('le',F(n+'_passed'),F(n+'_eligible')) for n in dqweights])
    put('LOG-005',{'weight':N(0,1),'filled_occurrences':N(integer=True),'expected_occurrences':N(1,integer=True),'weight_version':T(),'source_class':T()},
        {'value':A('sum',mul(F('weight'),100,div(F('filled_occurrences'),F('expected_occurrences')))), 'weights':A('sum',F('weight'))},{'value':S('value')},
        row_constraints=[O('le',F('filled_occurrences'),F('expected_occurrences'))],aggregate_constraints=[O('le',O('abs',sub(S('weights'),1)),1e-12)])

    # Prepared observation summands preserve the card's product and aggregation.
    sums={
      'AIM-012':({'autonomous_investigations_per_class':N(integer=True),'baseline_analyst_minutes_per_class':N(),'baseline_version':T()},div(mul(F('autonomous_investigations_per_class'),F('baseline_analyst_minutes_per_class')),60),'sum'),
      'STD-030':({**{f:N(1,4,integer=True) for f in ['usage_volume','data_sensitivity','access_risk']},'governance_gap':N(enum=[0,.5,1])},mul(*(F(f) for f in ['usage_volume','data_sensitivity','access_risk','governance_gap'])),'sum'),
      'STD-043':({f:N(0,1) for f in ['exposure','data_sensitivity','vulnerability','control_gap','business_criticality']},mul(100,*(F(f) for f in ['exposure','data_sensitivity','vulnerability','control_gap','business_criticality'])),'mean'),
      'STD-045':({**{f:N(enum=[.25,.5,1]) for f in ['privilege','scope_factor','policy_risk']},'external_access':N(enum=[.5,1])},mul(100,*(F(f) for f in ['privilege','scope_factor','external_access','policy_risk'])),'sum'),
      'STD-056':({'residual_risk':N(0,100),'age_factor':N(0,1),'compensating_control_gap':N(0,1)},mul(F('residual_risk'),F('age_factor'),F('compensating_control_gap')),'sum'),
      'STD-035':({'dormancy_days':N(),'privilege_weight':N(1,4,integer=True),'external_access_weight':N(enum=[1,1.5,2]),'mfa_gap':N(enum=[.25,.5,1])},mul(*(F(f) for f in ['dormancy_days','privilege_weight','external_access_weight','mfa_gap'])),'sum'),
      'STD-036':({'count_deviating_assignments':N(integer=True),'risk_weight':N(),'classification_version':T()},mul(F('count_deviating_assignments'),F('risk_weight')),'sum'),
      'STD-040':({f:N(0,1) for f in ['access_level','data_sensitivity','dormancy','mfa_gap','owner_confidence_gap']},mul(100,*(F(f) for f in ['access_level','data_sensitivity','dormancy','mfa_gap','owner_confidence_gap'])),'mean'),
      'STD-041':({'weight_privilege_exposure':N(),'legacy_auth_allowed_or_active':B},choose(F('legacy_auth_allowed_or_active'),F('weight_privilege_exposure'),0),'sum'),
      'STD-042':({'criticality_weight':N(1,4),'matches_toxic_combination_rules':B},choose(F('matches_toxic_combination_rules'),F('criticality_weight'),0),'sum'),
      'STD-070':({'service_criticality':N(0,10),'dependency_strength':N(0,1),'sla_gap':N(0,1),'test_gap':N(0,1)},mul(F('service_criticality'),F('dependency_strength'),F('sla_gap'),F('test_gap')),'sum'),
      'STD-013':({'open_hours':N(),'asset_criticality':N(1,4,integer=True),'exposure':N(enum=[.25,.5,1]),'exploit_likelihood':N(0,1),'severity':N(0,1),'control_gap':N(enum=[.5,1])},mul(*(F(f) for f in ['open_hours','asset_criticality','exposure','exploit_likelihood','severity','control_gap'])),'sum'),
      'STD-015':({'epss_score':N(0,1),'asset_criticality':N(1,4,integer=True),'exposure':N(enum=[.25,.5,1])},mul(F('epss_score'),F('asset_criticality'),F('exposure')),'sum'),
    }
    for cid,(inputs,expr,method) in sums.items():
        inputs={**inputs,'factor_profile_version':T(),'factor_profile_evidence_ref':T()}
        put(cid,inputs,{'value':A(method,expr),'case_count':A('count',1)},{'value':S('value'),'case_count':S('case_count')},empty='ok' if method=='sum' else 'not_applicable',output_units={'case_count':'count'})
    put('STD-046',{'used_permissions_90d':N(integer=True),'granted_permissions':N(integer=True),'violates_least_privilege':B,'criticality_weight':N(1,4)},
        {'value':A('sum',choose(O('or',F('violates_least_privilege'),O('le',div(F('used_permissions_90d'),F('granted_permissions')),.2)),F('criticality_weight'),0))},{'value':S('value')},empty='ok',row_constraints=[O('le',F('used_permissions_90d'),F('granted_permissions'))])
    put('STD-047',{'runtime_exposure':N(0,1),'workload_criticality':N(0,1),'kev_flag':B,'epss_score':N(0,1)},
        {'value':A('sum',mul(100,F('runtime_exposure'),F('workload_criticality'),choose(F('kev_flag'),1,F('epss_score'))))},{'value':S('value')},empty='ok')
    single('STD-071',{f:N() for f in ['untested_services_w','failed_restore_tests_w','rto_rpo_unknown_w','stale_runbooks_w']},
        {'value':weighted({'untested_services_w':.3,'failed_restore_tests_w':.3,'rto_rpo_unknown_w':.2,'stale_runbooks_w':.2})})
    put('SOC-035',{'service_downtime_minutes':N(),'service_criticality_weight':N(1,4)},
        {'downtime_total':A('sum',F('service_downtime_minutes')),'downtime_weighted':A('sum',mul(F('service_downtime_minutes'),F('service_criticality_weight')))},
        {k:S(k) for k in ['downtime_total','downtime_weighted']},empty='ok',output_units={'downtime_total':'minutes','downtime_weighted':'weighted minutes'})

    for cid,value,weight,scale,domain in [
        ('STD-006','effectiveness_score','criticality_weight',1,N(0,100)),
        ('STD-006a','control_effectiveness','tier1_weight',1,N(0,100)),
        ('STD-008','recovery_confidence_score','service_criticality',1,N(0,100)),
        ('STD-012','measure_completion','expected_risk_reduction_weight',100,N(0,1))]:
        put(cid,{value:domain,weight:N(),'weight_profile_version':T()},
            {'weighted_sum':A('sum',mul(F(value),F(weight))),'weight_sum':A('sum',F(weight))},
            {'value':mul(scale,div(S('weighted_sum'),S('weight_sum'))),'weight_sum':S('weight_sum')})
    put('STD-080',{'kr_actual_value':N(),'kr_target_value':N(1e-12),'weight_objective_priority':N()},
        {'weighted_sum':A('sum',mul(O('min',div(F('kr_actual_value'),F('kr_target_value')),1),100,F('weight_objective_priority'))),'weight_sum':A('sum',F('weight_objective_priority'))},
        {'value':div(S('weighted_sum'),S('weight_sum')),'weight_sum':S('weight_sum')})
    put('STD-064',{f:N(0,100) for f in ['test_success','runbook_freshness','dependency_coverage']},
        {'value':A('mean',weighted({'test_success':.4,'runbook_freshness':.35,'dependency_coverage':.25}))},{'value':S('value')})
    put('SOC-050',{'survey_score':N(0,10,integer=True),'weight':N(),'survey_variant':T(['csat_1_5','nps_0_10']),'survey_scale_version':T()},
        {'weighted_sum':A('sum',mul(F('survey_score'),F('weight'))),'weight_sum':A('sum',F('weight')),'n':A('count',1),
         'csat_rows':A('sum',choose(O('eq',F('survey_variant'),'csat_1_5'),1,0)),
         'promoters':A('sum',choose(O('ge',F('survey_score'),9),1,0)),'detractors':A('sum',choose(O('le',F('survey_score'),6),1,0))},
        {'csat_score':choose(O('eq',S('csat_rows'),S('n')),div(S('weighted_sum'),S('weight_sum')),None),
         'nps':choose(O('eq',S('csat_rows'),0),mul(100,div(sub(S('promoters'),S('detractors')),S('n'))),None),
         'value':choose(O('eq',S('csat_rows'),S('n')),div(S('weighted_sum'),S('weight_sum')),mul(100,div(sub(S('promoters'),S('detractors')),S('n')))),
         'response_count':S('n')},
        row_constraints=[choose(O('eq',F('survey_variant'),'csat_1_5'),O('and',O('ge',F('survey_score'),1),O('le',F('survey_score'),5)),True)],
        aggregate_constraints=[O('or',O('eq',S('csat_rows'),0),O('eq',S('csat_rows'),S('n')))],
        segments=['business_service/severity'],output_units={'response_count':'count','csat_score':'CSAT 1–5','nps':'NPS -100–100'},note='Select one declared variant for a reporting population. CSAT uses native 1–5 responses and explicit response weights. NPS uses unweighted native 0–10 responses; promoters 9–10, detractors 0–6. Mixing variants is invalid.')

    # Ratios with multiple inputs, companion outputs or required segments.
    ratio('MET-007','metrics_attested_by_accountable_owner_within_freshness_sla','active_metrics_in_catalog_reporting_scope',segments=['board_p0_3months','all_active_12months'])
    single('AIM-005',{'missed_true_positives':N(integer=True),'detected_true_positives':N(integer=True)},
        {'value':mul(100,div(F('missed_true_positives'),add(F('detected_true_positives'),F('missed_true_positives'))))})
    single('AIM-006',{'alerts_received':N(integer=True),'alerts_forwarded_to_analyst':N(integer=True)},
        {'value':mul(100,div(sub(F('alerts_received'),F('alerts_forwarded_to_analyst')),F('alerts_received')))},row_constraints=[O('le',F('alerts_forwarded_to_analyst'),F('alerts_received'))])
    single('STD-024',{'count_new_external_assets_or_services':N(integer=True),'count_days_reporting_period':N(1e-12)},
        {'value':div(F('count_new_external_assets_or_services'),F('count_days_reporting_period'))})
    certs=['expiring_lt_30d','weak_algorithms','unknown_owner','hostname_mismatch']
    single('STD-027',{**{f:N(integer=True) for f in certs},'certificates_in_scope':N(integer=True)},
        {'value':mul(100,div(weighted(dict(zip(certs,[.3,.3,.2,.2]))),F('certificates_in_scope')))},row_constraints=[O('le',F(f),F('certificates_in_scope')) for f in certs])
    ratio('DET-006','exact_initial_final_severity_matches','incidents_with_final_severity_review')
    controls={'mfa_or_compensating_control':20,'vaulting':20,'monitoring':20,'approval':15,'periodic_test':15,'owner_present':10}
    put('STD-038',{k:B for k in controls}, {'points':A('sum',add(*(choose(F(k),w,0) for k,w in controls.items()))),'accounts':A('count',1)},
        {'value':div(S('points'),S('accounts')),'accounts':S('accounts')},output_units={'accounts':'count'})
    single('RES-004',{'required_recovery_capacity':N(),'available_tested_recovery_capacity':N()},
        {'value':mul(100,div(O('max',sub(F('required_recovery_capacity'),F('available_tested_recovery_capacity')),0),F('required_recovery_capacity')))})
    put('CFG-003',{'expired':B,'expires_within_30_days':B,'approved':B},
        {'num':A('sum',choose(O('or',F('expired'),F('expires_within_30_days'),O('not',F('approved'))),1,0)),'den':A('count',1)},
        {'value':mul(100,div(S('num'),S('den'))),'absolute_base':S('den')},output_units={'absolute_base':'count'})
    put('LOG-009',{'expected_events':N(integer=True),'searchable_normalized_events':N(integer=True),'expectation_rule_version':T()},
        {'missing':A('sum',O('max',sub(F('expected_events'),F('searchable_normalized_events')),0)),'expected':A('sum',F('expected_events'))},
        {'value':mul(100,div(S('missing'),S('expected'))),'expected_events':S('expected')},segments=['all','p0'],output_units={'expected_events':'count'})
    ratio('SOC-048','count_confirmed_incidents_first_report_user','count_confirmed_incidents_total')
    ratio('SOC-025','reopened_incidents_incomplete_resolution','resolved_incidents',extra={'outcome_window_complete':B},note='Only mature resolution cohorts with the complete 30-day reopen observation window can be published.')
    result['SOC-025']['row_constraints'].append(O('eq',F('outcome_window_complete'),True))
    ratio('SOC-030','incidents_resolved_within_sla','incidents_opened_or_due_in_period')
    ratio('TPR-001','suppliers_with_complete_inventory','suppliers_total',segments=['critical','high_risk'])
    ratio('TPR-002','controls_with_fresh_accepted_evidence','required_controls',extra={'stale_evidence_count':N(integer=True)},outputs={'stale_evidence_count':F('stale_evidence_count')},segments=['all','critical_providers'],output_units={'stale_evidence_count':'count'})
    ratio('TPR-006','unmanaged_concentrations_above_appetite','identified_concentrations',segments=['fourth_party','cloud_platform','region','msp'])
    for cid,pairs in {
        'SOC-006':{'simulated_rate':('blocked_or_detected_simulated','total_simulated'),'real_rate':('blocked_or_detected_confirmed_real','total_confirmed_real')},
        'TPR-004':{'all_contracts_rate':('critical_contracts_complete_clauses','critical_contracts_total'),'new_contracts_rate':('new_critical_contracts_complete_before_signature','new_critical_contracts_total')},
        'TPR-005':{'supplier_rate':('critical_suppliers_tested_sla','critical_suppliers_total'),'service_provider_rate':('critical_service_providers_tested_sla','critical_service_providers_total')},
        'TPR-007':{'critical_services_rate':('critical_services_tested_exit_plan','critical_services_requiring_exit_plan'),'dora_rate':('dora_services_tested_exit_plan','dora_services_requiring_exit_plan')},
        'TPR-008':{'critical_supplier_rate':('critical_suppliers_regular_feed','critical_suppliers_feed_required'),'control_plane_supplier_rate':('control_plane_suppliers_regular_feed','control_plane_suppliers_feed_required')},
        'SOC-080':{'precision':('prioritized_high_and_true','prioritized_high'),'recall':('prioritized_high_and_true','true_total')},
    }.items():
        single(cid,{f:N(integer=True) for pair in pairs.values() for f in pair},
            {**{k:mul(100,div(F(a),F(b))) for k,(a,b) in pairs.items()},**{k+'_base':F(b) for k,(a,b) in pairs.items()}},
            row_constraints=[O('le',F(a),F(b)) for a,b in pairs.values()],output_units={k+'_base':'count' for k in pairs})

    single('AIM-007',{'mttr_baseline':N(),'mttr_current':N(),'baseline_version':T()},
        {'value':mul(100,div(sub(F('mttr_baseline'),F('mttr_current')),F('mttr_baseline')))},segments=['severity'])
    single('STD-004',{'baseline_risk_score':N(),'current_residual_risk_score':N(),'plan_value_period':N(nullable=True),'baseline_version':T()},
        {'burn_down':sub(F('baseline_risk_score'),F('current_residual_risk_score')),
         'plan_deviation_percent':choose(O('gt',F('plan_value_period'),0),mul(100,div(sub(F('plan_value_period'),sub(F('baseline_risk_score'),F('current_residual_risk_score'))),F('plan_value_period'))),None)})
    cdi={'overdue_vulns_wsum':.30,'expired_exceptions_wsum':.25,'untested_recovery_wsum':.20,'stale_controls_wsum':.15,'unmanaged_assets_wsum':.10}
    single('STD-009',{**{f:N() for f in cdi},'baseline_wsum':N(),'baseline_ref':T()}, {'value':mul(100,div(weighted(cdi),F('baseline_wsum')))})
    single('SOC-022',{f:N() for f in ['false_positive_alerts','total_alerts','low_value_alerts','alerts_per_analyst','target_alerts_per_analyst']},
        {'value':add(mul(50,div(F('false_positive_alerts'),F('total_alerts'))),mul(30,div(F('low_value_alerts'),F('total_alerts'))),mul(20,div(F('alerts_per_analyst'),F('target_alerts_per_analyst'))))},
        row_constraints=[O('le',F(f),F('total_alerts')) for f in ['false_positive_alerts','low_value_alerts']])
    put('SOC-034',{'actual_effort_share':N(0,1),'expected_effort_share':N(0,1),'risk_profile_version':T()},
        {'distance':A('sum',O('abs',sub(F('actual_effort_share'),F('expected_effort_share')))),'actual_sum':A('sum',F('actual_effort_share')),'expected_sum':A('sum',F('expected_effort_share'))},
        {'value':clip(mul(100,sub(1,mul(.5,S('distance')))))},aggregate_constraints=[O('le',O('abs',sub(S(k),1)),1e-12) for k in ['actual_sum','expected_sum']])
    put('SOC-064',{'weighted_cases_per_analyst':N(),'target_cv':N(),'worst_cv':N(),'normalization_version':T()},
        {'mean':A('mean',F('weighted_cases_per_analyst')),'sd':A('stddev_population',F('weighted_cases_per_analyst')),'target':A('max',F('target_cv')),'target_min':A('min',F('target_cv')),'worst':A('max',F('worst_cv')),'worst_min':A('min',F('worst_cv'))},
        {'coefficient_of_variation':div(S('sd'),S('mean')),'value':sub(100,clip(mul(100,div(sub(div(S('sd'),S('mean')),S('target')),sub(S('worst'),S('target'))))))},
        row_constraints=[O('gt',F('worst_cv'),F('target_cv'))],aggregate_constraints=[O('eq',S('target'),S('target_min')),O('eq',S('worst'),S('worst_min'))],note='Population standard deviation over the complete analyst population. Zero mean produces n/a; no artificial balanced score.')
    put('TPR-012',{'criticality_weight':N(1,3,integer=True),'dependence_share_largest_provider':N(0,1),'baseline_concentration_value':N(),'baseline_version':T()},
        {'current':A('sum',mul(F('criticality_weight'),F('dependence_share_largest_provider'))),'baseline':A('max',F('baseline_concentration_value')),'baseline_min':A('min',F('baseline_concentration_value'))},
        {'value':mul(100,div(S('current'),S('baseline'))),'current_concentration':S('current')},aggregate_constraints=[O('eq',S('baseline'),S('baseline_min'))])
    put('STD-074',{'actual_risk_reduction':N(-100,100),'expected_risk_reduction':N(-100,100),'baseline_version':T()},
        {'value':A('mean',sub(F('actual_risk_reduction'),F('expected_risk_reduction'))),'case_count':A('count',1)},
        {'value':S('value'),'case_count':S('case_count')},output_units={'case_count':'count'})
    single('SOC-032',{**{f:N() for f in ['manual_baseline_cost_per_case','automated_cost_per_case','automated_cases','automation_operating_cost']},'baseline_version':T()},
        {'value':sub(mul(sub(F('manual_baseline_cost_per_case'),F('automated_cost_per_case')),F('automated_cases')),F('automation_operating_cost'))})
    single('LOG-016',{'monthly_telemetry_platform_and_storage_cost':N(),'validated_usage_units':N(integer=True),'currency':T(),'cost_profile_version':T()},
        {'value':div(F('monthly_telemetry_platform_and_storage_cost'),F('validated_usage_units')),'cost_base':F('monthly_telemetry_platform_and_storage_cost'),'usage_base':F('validated_usage_units')},output_units={'usage_base':'count'})
    single('SOC-020',{**{f:N() for f in ['labor_cost','tool_cost_allocated','third_party_cost','downtime_cost_allocated']},'confirmed_incidents':N(integer=True),'currency':T(),'cost_profile_version':T()},
        {'value':div(add(*(F(f) for f in ['labor_cost','tool_cost_allocated','third_party_cost','downtime_cost_allocated'])),F('confirmed_incidents')),'incident_base':F('confirmed_incidents')},output_units={'incident_base':'count'})
    coverage=mul(O('max',sub(O('min',F('policy_limit_eur'),F('p90_loss_exposure_eur')),F('deductible_eur')),0),F('exclusion_does_not_apply'))
    single('RES-007',{'policy_limit_eur':N(),'p90_loss_exposure_eur':N(),'deductible_eur':N(),'exclusion_does_not_apply':N(0,1,integer=True),'scenario_id':T(),'loss_profile_version':T()},
        {'uncovered_exposure_eur':O('max',sub(F('p90_loss_exposure_eur'),coverage),0),'creditable_coverage_eur':coverage})

    from .specials import extend
    extend(result,cards)
    for p in result.values():
        # These are reference implementations. A local parameter version must be
        # explicitly registered in a new bound contract; arbitrary version labels
        # cannot silently reuse the reference implementation's test evidence.
        for key,schema in p['inputs'].items():
            if key!='card_version' and key.endswith('_version') and 'enum' not in schema:
                schema['enum']=[REFERENCE_PARAMETER_VERSION]
        p['parameter_profile_notice']='Reference method versions are explicitly allowlisted. Application-specific parameter versions require a newly bound contract and fresh verification. Version recognition alone does not attest parameter approval or source authenticity.'
        for key,output in p['output_contracts'].items():
            if key.endswith(('_cases','_count','_measures')) or key in ('events','exceptions','accounts','regulatory_breaches','early_escalations','observed_late','missing_effect_overdue'):
                output.update(unit='count',absolute_tolerance=0,relative_tolerance=0)
            elif output.get('unit')=='minutes':output['absolute_tolerance']=1e-7
    # Recompute hashes after all explicit supplemental constraints have been added.
    rehash(result)
    return result

def rehash(plans):
    import hashlib,json
    for p in plans.values():
        p.pop('contract_hash',None)
        p['contract_hash']=hashlib.sha256(json.dumps(p,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
