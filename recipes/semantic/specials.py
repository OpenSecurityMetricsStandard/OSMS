# SPDX-License-Identifier: MIT
"""Explicit populations, clocks, penalties, normalization and multi-output gates."""
from .model import (plan,field as F,stat as S,op as O,add,mul,sub,div,choose,clip,
                    number as N,text as T,timestamp as TS,aggregate as A)
B={'type':'boolean'}

def extend(result,cards):
    def put(cid,inputs,stats,outputs,**kw):result[cid]=plan(cards[cid],inputs,stats,outputs,**kw)
    def single(cid,inputs,outputs,**kw):put(cid,inputs,{k:A('max',v) for k,v in outputs.items()},{k:S(k) for k in outputs},single=True,**kw)
    def period(expr):return O('and',O('present',expr),O('ge',expr,F('period_start')),O('lt',expr,F('period_end')))
    def count(cond=True):return A('sum',choose(cond,1,0))
    def counts(cid,inputs,conditions,**kw):
        put(cid,inputs,{k:count(cond) for k,cond in conditions.items()},{k:S(k) for k in conditions},empty='ok',output_units={k:'count' for k in conditions},primary_outputs=list(conditions),**kw)

    for cid in ['AI-003','DAT-005']:
        cohort=O('and',F('confirmed'),period(F('confirmed_at')))
        counts(cid,{'confirmed':B,'confirmed_at':TS(True),'regulated_crown_jewel':B,'rca_and_control_update_completed':B},
            {'value':cohort,'regulated_crown_jewel_cases':O('and',cohort,F('regulated_crown_jewel')),
             'rca_and_control_update_completed_cases':O('and',cohort,F('rca_and_control_update_completed'))})
    counts('STD-023',{'owner_known':B,'business_purpose_known':B,'in_cmdb':B},
        {'value':O('or',O('not',F('owner_known')),O('not',F('business_purpose_known')),O('not',F('in_cmdb')))})
    cond=O('and',F('is_admin_interface'),F('publicly_reachable'))
    counts('STD-025',{'is_admin_interface':B,'publicly_reachable':B,'approved_exception':B},
        {'value':cond,'unapproved_exposures':O('and',cond,O('not',F('approved_exception')))})
    counts('STD-026',{'publicly_reachable':B,'approved':B,'contains_sensitive_data':B},
        {'value':O('and',F('publicly_reachable'),O('or',O('not',F('approved')),F('contains_sensitive_data')))})
    cond=O('and',F('critical_service'),F('internet_exposed_asset_or_path'))
    counts('STD-029',{'critical_service':B,'internet_exposed_asset_or_path':B,'approved':B,'controls_complete':B},
        {'value':cond,'unapproved_exposures':O('and',cond,O('not',F('approved'))),'incomplete_control_exposures':O('and',cond,O('not',F('controls_complete')))})
    counts('STD-031',{'changed_or_new':B,'approved':B,'owner_unknown':B},
        {'value':O('and',F('changed_or_new'),O('or',O('not',F('approved')),F('owner_unknown')))})
    counts('STD-032',{'risk_score':N(0,100,nullable=True),'documented_risk_threshold':N(0,100),'owner_known':B,'contract_present':B,'control_status_known':B,'asset_evidence_present':B},
        {'value':O('or',O('ge',F('risk_score'),F('documented_risk_threshold')),O('not',F('owner_known')),O('not',F('contract_present')),O('not',F('control_status_known')),O('not',F('asset_evidence_present')))},
        note='asset_evidence_present describes the assessed asset. The observation itself still requires evidence_ref, including proof of a missing asset document.')
    cond=O('and',F('open_finding'),F('kev_flag'),O('ge',F('asset_criticality'),3))
    age=O('hours',F('period_end'),F('detected_at'))
    counts('STD-014',{'asset_id':T(),'cve_id':T(),'open_finding':B,'kev_flag':B,'asset_criticality':N(1,4,integer=True),'detected_at':TS()},
        {'value':cond,'outside_emergency_window':O('and',cond,O('gt',age,72)),'sla_violated':O('and',cond,O('gt',age,336))},
        identity_fields=['asset_id','cve_id'],row_constraints=[O('ge',age,0)])
    counts('SOC-029',{'severity':T(),'recipient':T(),'reason_code':T(),'escalated_at':TS(),'detected_or_triaged_at':TS()},
        {'value':period(F('escalated_at')),'critical_over_30_minutes':O('and',period(F('escalated_at')),O('eq',F('severity'),'critical'),O('gt',O('minutes',F('escalated_at'),F('detected_or_triaged_at')),30))},
        segments=['severity/recipient/reason_code'],row_constraints=[O('ge',F('escalated_at'),F('detected_or_triaged_at'))])

    # Penalty precedence and time bands are evaluated from facts, not supplied weights.
    severity_weight=choose(F('active_p1_incident'),15,choose(F('actively_exploited_kev'),10,choose(F('confirmed_ioc'),5,0)))
    decay=choose(O('present',F('contained_at')),O('max',0,sub(1,div(O('days',F('period_end'),F('contained_at')),14))),1)
    put('STD-001a',{'active_p1_incident':B,'actively_exploited_kev':B,'confirmed_ioc':B,'contained_at':TS(True)},
        {'raw':A('sum',mul(severity_weight,decay)),'events':A('count',1)},
        {'value':O('min',25,S('raw')),'uncapped_contribution':S('raw'),'events':S('events')},empty='ok',output_units={'events':'count'},
        row_constraints=[O('or',O('not',O('present',F('contained_at'))),O('le',F('contained_at'),F('period_end')))])
    sev=choose(O('eq',F('severity'),'critical'),4,choose(O('eq',F('severity'),'high'),2,choose(O('eq',F('severity'),'medium'),1,.5)))
    age=O('days',F('period_end'),F('exception_created_at'))
    agefactor=choose(O('le',age,30),1,choose(O('le',age,90),1.5,2))
    put('STD-001b',{'severity':T(['critical','high','medium','low']),'exception_created_at':TS()},
        {'raw':A('sum',mul(sev,agefactor)),'exceptions':A('count',1)},
        {'value':O('min',15,S('raw')),'uncapped_contribution':S('raw'),'exceptions':S('exceptions')},empty='ok',output_units={'exceptions':'count'},row_constraints=[O('ge',age,0)])
    age=O('days',F('period_end'),F('first_approval_date'))
    weight=mul(choose(O('eq',F('criticality_tier'),'tier0'),5,choose(O('eq',F('criticality_tier'),'tier1'),3,1)),
        choose(O('le',age,30),1,choose(O('le',age,90),2,3)),
        choose(O('eq',F('extent'),'asset'),1,choose(O('eq',F('extent'),'group_or_service'),2,3)),choose(F('compensation_proven'),1,2))
    put('LOG-015',{'first_approval_date':TS(),'expiry_date':TS(),'criticality_tier':T(['tier0','tier1','tier2_or_lower']),'extent':T(['asset','group_or_service','site_or_tenant']),'compensation_proven':B},
        {'score':A('sum',weight),'expired':count(O('lt',F('expiry_date'),F('period_end'))),'tier0_max':A('max',age,where=O('eq',F('criticality_tier'),'tier0'))},
        {'value':S('score'),'expired_open_exceptions':S('expired'),'tier0_exception_age_max_days':S('tier0_max')},empty='ok',empty_outputs={'tier0_exception_age_max_days':None},output_units={'expired_open_exceptions':'count','tier0_exception_age_max_days':'days'},row_constraints=[O('ge',age,0)])

    def duration(cid,start,end,unit,*,cohort=None,median='quantile',inputs=None,derived=None,
                 stats=None,outputs=None,segments=None,extra_constraints=None):
        typed={start:TS(True),end:TS(True),**(inputs or {})}
        # period_end/start are the mandatory metadata fields, not nullable clocks.
        for key in ('period_start','period_end'):typed.pop(key,None)
        cohort=True if cohort is None else cohort
        value=O(unit,F(end),F(start));valid=O('and',O('present',F(start)),O('present',F(end)),O('ge',F(end),F(start)))
        deriv={**(derived or {}),'duration_value':choose(O('and',cohort,valid),value,None)}
        statistics={'p50':A(median,F('duration_value'),q=.5 if median=='quantile' else None),
                    'p90':A('quantile',F('duration_value'),q=.9),'valid_cases':A('count',F('duration_value')),
                    'invalid_cases':count(O('and',cohort,O('not',valid))),**(stats or {})}
        outs={'p50':S('p50'),'p90':S('p90'),'valid_cases':S('valid_cases'),'invalid_cases':S('invalid_cases'),**(outputs or {})}
        put(cid,typed,statistics,outs,derived=deriv,segments=segments,primary_outputs=['p50','p90']+list(outputs or {}),
            row_constraints=extra_constraints or [],output_units={'p50':unit,'p90':unit,'valid_cases':'count','invalid_cases':'count'},
            note='Invalid duration pairs are counted and excluded from distributions. These diagnostics must feed the separate confidence and reporting gates.')

    duration('AIM-003','received_at','closed_at','minutes',cohort=period(F('closed_at')))
    duration('HRM-005','delivered_at','reported_at','minutes',median='median',cohort=period(F('reported_at')),segments=['simulation','real_report'])
    duration('SOC-012','detected_at','contained_at','hours',cohort=period(F('contained_at')),segments=['severity'])
    duration('SOC-028','detected_or_triaged_at','escalated_at','minutes',cohort=O('and',F('escalation_obligated'),period(F('escalated_at'))),inputs={'escalation_obligated':B},segments=['severity'])
    duration('SOC-031','alert_created_at','acknowledged_at','minutes',cohort=period(F('acknowledged_at')),segments=['severity'])
    duration('STD-017','detected_at','risk_reduced_at','hours',cohort=O('and',period(F('risk_reduced_at')),F('reduction_validated')),inputs={'reduction_validated':B},segments=['risk_tier'])
    duration('SOC-040','incident_detected_at','rca_completed_at','hours',median='median',cohort=O('and',F('rca_obligated'),period(F('rca_completed_at'))),inputs={'rca_obligated':B},segments=['classification'])
    for cid,start in [('SOC-001','first_compromise_at'),('SOC-002','occurred_at')]:
        cohort=O('and',period(F('detected_at')),O('present',F('confirmed_at')),O('le',F('confirmed_at'),F('period_end')))
        w=choose(O('eq',F('severity'),'P1'),4,choose(O('eq',F('severity'),'P2'),2,1))
        duration(cid,start,'detected_at','hours',median='median',cohort=cohort,inputs={'confirmed_at':TS(True),'severity':T(nullable=True)},
            stats={'mean':A('mean',F('duration_value')),'weight_sum':A('sum',choose(O('present',F('duration_value')),w,0)),
                   'weighted_sum':A('sum',mul(F('duration_value'),w))},
            outputs={'mean_h':S('mean'),'severity_weighted_mean_h':div(S('weighted_sum'),S('weight_sum'))})
        result[cid]['row_constraints'].append(O('or',O('not',O('present',F('confirmed_at'))),O('not',O('present',F('detected_at'))),O('ge',F('confirmed_at'),F('detected_at'))))
    for cid,start,unit,seg in [('STD-010','decision_requested_at','days',['all','risk_class']),('STD-077','blocker_created_at','hours',['all']),('CFG-002','first_drift_detected_at','days',['all'])]:
        stats={'p95':A('quantile',F('duration_value'),q=.95)} if cid=='CFG-002' else {}
        outputs={'p95':S('p95')} if cid=='CFG-002' else {}
        duration(cid,start,'period_end',unit,cohort=F('open_at_cutoff'),inputs={'open_at_cutoff':B},stats=stats,outputs=outputs,segments=seg)
    cfg=result['CFG-002'];cfg['inputs'].update({'tier0':B,'drift_severity':T(['critical','high','medium','low'])})
    cfg['statistics']['tier0_critical_max_days']=A('max',F('duration_value'),where=O('and',F('tier0'),O('eq',F('drift_severity'),'critical')))
    cfg['outputs']['tier0_critical_max_days']=S('tier0_critical_max_days')
    cfg['output_contracts']['tier0_critical_max_days']={'unit':'days','nullable':True,'absolute_tolerance':1e-8,'relative_tolerance':1e-12}
    duration('STD-055','age_start_at','period_end','days',cohort=O('or',O('eq',F('acceptance_status'),'open'),O('eq',F('acceptance_status'),'expired')),
        inputs={'acceptance_date':TS(True),'expiry_date':TS(True),'acceptance_status':T(['open','expired','closed'])},
        derived={'age_start_at':choose(O('eq',F('acceptance_status'),'expired'),F('expiry_date'),F('acceptance_date'))})
    # The derived clock is not an independent, caller-supplied value.
    result['STD-055']['inputs'].pop('age_start_at')
    open_decision=O('and',O('not',O('present',F('decision_date'))),O('present',F('decision_request_date')),O('lt',F('decision_request_date'),F('period_end')))
    duration('STD-061','decision_request_date','decision_date','hours',median='median',cohort=period(F('decision_date')),segments=['all','risk_class'],
        stats={'open_cases':count(open_decision),'open_age_max_h':A('max',O('hours',F('period_end'),F('decision_request_date')),where=open_decision)},
        outputs={'open_cases':S('open_cases'),'open_age_max_h':S('open_age_max_h')})
    duration('STD-019','exception_created_at','period_end','days',cohort=F('open_at_cutoff'),inputs={'open_at_cutoff':B,'exception_expires_at':TS(),'residual_risk':T()},segments=['residual_risk'],
        stats={'overdue_cases':count(O('and',F('open_at_cutoff'),O('lt',F('exception_expires_at'),F('period_end')))),
               'overdue_max_days':A('max',O('max',0,O('days',F('period_end'),F('exception_expires_at'))),where=F('open_at_cutoff'))},
        outputs={'overdue_cases':S('overdue_cases'),'overdue_max_days':S('overdue_max_days')})
    latest=O('max',*(O('coalesce',F(k),F('period_start')) for k in ['last_tuning_date','last_test_date','last_threat_intel_review_date','last_validation_date']))
    # Missing lifecycle dates must not turn the period start into a real lifecycle
    # event. Each fallback below uses the earliest present event, guarded by any.
    dates=['last_tuning_date','last_test_date','last_threat_intel_review_date','last_validation_date']
    fallback=O('coalesce',*(F(k) for k in dates))
    latest=O('max',*(O('coalesce',F(k),fallback) for k in dates))
    duration('DET-003','last_lifecycle_at','period_end','days',inputs={**{k:TS(True) for k in dates},'priority_class':T(['P0','P1','P2'])},derived={'last_lifecycle_at':latest},segments=['priority_class'],
        stats={'stale_p0_rules':count(O('and',O('eq',F('priority_class'),'P0'),O('gt',F('duration_value'),30)))},outputs={'stale_p0_rules':S('stale_p0_rules')})
    result['DET-003']['inputs'].pop('last_lifecycle_at')
    duration('DET-008','approved_detection_request_timestamp','production_tested_rule_timestamp','days',cohort=period(F('production_tested_rule_timestamp')),inputs={'emergency_threat_flag':B},
        stats={'emergency_over_72h':count(O('and',F('emergency_threat_flag'),O('ge',mul(F('duration_value'),24),72)))},outputs={'emergency_over_72h':S('emergency_over_72h')})
    duration('APP-005','exploitability_start_timestamp','exposure_end_at','hours',
        inputs={'fix_deploy_timestamp':TS(True),'app_criticality_weight':N(),'exposure_weight':N()},
        derived={'exposure_end_at':O('min',O('coalesce',F('fix_deploy_timestamp'),F('period_end')),F('period_end'))},
        stats={'weighted_hours':A('sum',mul(F('duration_value'),F('app_criticality_weight'),F('exposure_weight')))},
        outputs={'weighted_exposure_hours':S('weighted_hours')},segments=['tier0','internet_facing'])
    result['APP-005']['inputs'].pop('exposure_end_at')
    duration('APP-010','exposure_start_timestamp','exposure_end_at','hours',
        inputs={'revocation_rotation_timestamp':TS(True),'recurrence_flag':B,'recurrence_count_previous_period':N(integer=True)},
        derived={'exposure_end_at':O('min',O('coalesce',F('revocation_rotation_timestamp'),F('period_end')),F('period_end'))},
        stats={'p95':A('quantile',F('duration_value'),q=.95),'max':A('max',F('duration_value')),'recurrence_count':count(F('recurrence_flag')),'previous':A('max',F('recurrence_count_previous_period')),'previous_min':A('min',F('recurrence_count_previous_period'))},
        outputs={'p95':S('p95'),'maximum_h':S('max'),'recurrence_count':S('recurrence_count'),'recurrence_trend':sub(S('recurrence_count'),S('previous'))})
    result['APP-010']['inputs'].pop('exposure_end_at');result['APP-010']['aggregate_constraints']=[O('eq',S('previous'),S('previous_min'))]
    duration('LOG-011','gap_detected_at','period_end','hours',cohort=F('open_at_cutoff'),inputs={'open_at_cutoff':B,'tier0':B},
        stats={'p95':A('quantile',F('duration_value'),q=.95),'maximum':A('max',F('duration_value')),'tier0_maximum':A('max',F('duration_value'),where=F('tier0'))},
        outputs={'blindspot_age_p95':S('p95'),'blindspot_age_max':S('maximum'),'blindspot_age_max_tier0':S('tier0_maximum')})
    deadline=O('hours',O('min',O('coalesce',F('reported_at'),F('period_end')),F('period_end')),F('detected_at'))
    duration('SOC-053','detected_at','reported_at','hours',cohort=O('and',F('reportable_in_period'),O('le',F('reported_at'),F('period_end'))),
        inputs={'reportable_in_period':B,'regulatory_obligation':B,'sla_deadline_hours':N(1e-12),'sla_profile_version':T()},segments=['reporting_obligation_class'],
        stats={'reportable':count(F('reportable_in_period')),'sla_min':A('min',F('sla_deadline_hours')),'sla_max':A('max',F('sla_deadline_hours')),
               'regulatory_breaches':count(O('and',F('reportable_in_period'),F('regulatory_obligation'),O('gt',deadline,F('sla_deadline_hours')))),
               'on_time':count(O('and',F('reportable_in_period'),O('present',F('duration_value')),O('le',F('duration_value'),F('sla_deadline_hours'))))},
        outputs={'sla_rate':mul(100,div(S('on_time'),S('reportable'))),'reportable_cases':S('reportable'),'regulatory_breaches':S('regulatory_breaches'),
                 'overall_band':choose(O('gt',S('regulatory_breaches'),0),2,choose(O('present',S('p90')),choose(O('gt',S('p90'),mul(1.1,S('sla_max'))),2,choose(O('gt',S('p90'),S('sla_max')),1,0)),None))})
    result['SOC-053']['aggregate_constraints']=[O('eq',S('sla_min'),S('sla_max'))]
    riskweight=choose(O('or',F('kev_flag'),O('and',O('eq',F('severity'),'critical'),F('internet_facing'))),4,
        choose(O('or',O('eq',F('severity'),'critical'),O('and',O('eq',F('severity'),'high'),F('internet_facing'))),3,choose(O('eq',F('severity'),'high'),2,1)))
    duration('SOC-026','vulnerability_detected_at','remediated_or_mitigated_at','hours',cohort=O('and',period(F('remediated_or_mitigated_at')),F('treatment_verified')),
        inputs={'severity':T(['critical','high','medium','low']),'internet_facing':B,'kev_flag':B,'treatment_verified':B},
        stats={'risk_weighted_hours':A('sum',mul(O('hours',O('min',choose(F('treatment_verified'),O('coalesce',F('remediated_or_mitigated_at'),F('period_end')),F('period_end')),F('period_end')),F('vulnerability_detected_at')),riskweight))},
        outputs={'risk_weighted_exposure_hours':S('risk_weighted_hours')},segments=['severity/exposure_class'])
    exposure=O('hours',O('min',O('coalesce',F('treatment_started_at'),F('period_end')),F('period_end')),F('risk_identified_at'))
    duration('SOC-078','risk_identified_at','treatment_started_at','hours',cohort=O('and',O('present',F('treatment_started_at')),O('le',F('treatment_started_at'),F('period_end'))),
        inputs={'risk_weight':N(1,4,integer=True),'criticality_class':T(['critical','high','medium','low']),'internet_facing':B,'treatment_sla_hours':N(1e-12),'sla_profile_version':T()},
        stats={'weighted_sum':A('sum',mul(exposure,F('risk_weight'))),'weight_sum':A('sum',F('risk_weight')),
               'overdue_cases':count(O('gt',exposure,F('treatment_sla_hours'))),
               'critical_appetite_breaches':count(O('and',O('eq',F('criticality_class'),'critical'),O('gt',exposure,choose(F('internet_facing'),O('min',72,F('treatment_sla_hours')),F('treatment_sla_hours'))))),
               'red_cases':count(O('gt',exposure,mul(1.5,F('treatment_sla_hours')))),
               'early_escalations':count(O('gt',exposure,mul(1.25,F('treatment_sla_hours'))))},
        outputs={'exposure_weighted':div(S('weighted_sum'),S('weight_sum')),'overdue_cases':S('overdue_cases'),'early_escalations':S('early_escalations'),
                 'overall_band':choose(O('or',O('gt',S('red_cases'),0),O('gt',S('critical_appetite_breaches'),0)),2,choose(O('gt',S('overdue_cases'),0),1,0))},extra_constraints=[O('ge',exposure,0)])
    duration('STD-078','measure_completed_at','benefit_observed_at','days',median='median',cohort=O('and',O('present',F('benefit_observed_at')),O('le',F('benefit_observed_at'),F('period_end'))),
        inputs={'effect_window_days':N(1e-12)},
        stats={'pending':count(O('and',O('or',O('not',O('present',F('benefit_observed_at'))),O('gt',F('benefit_observed_at'),F('period_end'))),O('le',O('days',F('period_end'),F('measure_completed_at')),F('effect_window_days')))),
               'missing_effect_overdue':count(O('and',O('or',O('not',O('present',F('benefit_observed_at'))),O('gt',F('benefit_observed_at'),F('period_end'))),O('gt',O('days',F('period_end'),F('measure_completed_at')),F('effect_window_days')))),
               'observed_late':count(O('gt',F('duration_value'),F('effect_window_days')))},
        outputs={'pending_measures':S('pending'),'missing_effect_overdue':S('missing_effect_overdue'),'observed_late':S('observed_late'),
                 'overall_band':choose(O('gt',S('missing_effect_overdue'),0),2,choose(O('gt',S('observed_late'),0),1,choose(O('gt',S('valid_cases'),0),0,None)))})

    # Multi-part pentest coverage uses its own independent bases and worst band.
    pairs={'scope_coverage_percent':('critical_objects_tested','critical_objects_in_universe'),'remediation_coverage_percent':('high_critical_findings_treated_on_time','high_critical_findings_due')}
    rates={k:mul(100,div(F(a),F(b))) for k,(a,b) in pairs.items()}
    bands={'scope_coverage_percent':choose(O('eq',F('critical_objects_in_universe'),0),None,choose(O('ge',rates['scope_coverage_percent'],95),0,1)),
           'remediation_coverage_percent':choose(O('eq',F('high_critical_findings_due'),0),None,choose(O('ge',rates['remediation_coverage_percent'],100),0,2))}
    worst=choose(O('present',bands['scope_coverage_percent']),choose(O('present',bands['remediation_coverage_percent']),O('max',*bands.values()),bands['scope_coverage_percent']),bands['remediation_coverage_percent'])
    single('VAL-001',{**{f:N(integer=True) for pair in pairs.values() for f in pair},'unmanaged_critical_findings':N(integer=True)},
        {**rates,**{k+'_base':F(b) for k,(a,b) in pairs.items()},**{k+'_band':v for k,v in bands.items()},'overall_band':choose(O('gt',F('unmanaged_critical_findings'),0),2,worst)},
        row_constraints=[O('le',F(a),F(b)) for a,b in pairs.values()],primary_outputs=list(rates),output_units={**{k+'_base':'count' for k in pairs},'overall_band':'0 target, 1 amber, 2 red; null n/a'})

    # Each supplied row is one complete joint annual portfolio loss draw.
    put('STD-002a',{'annual_portfolio_loss':N(),'risk_appetite':N(),'model_profile_version':T(),'joint_scenario_set_hash':T(),'currency':T(['EUR'])},
        {'p50':A('median',F('annual_portfolio_loss')),'mean':A('mean',F('annual_portfolio_loss')),'p90':A('quantile',F('annual_portfolio_loss'),q=.9),
         'exceed':count(O('gt',F('annual_portfolio_loss'),F('risk_appetite'))),'n':A('count',1),'appetite_min':A('min',F('risk_appetite')),'appetite_max':A('max',F('risk_appetite'))},
        {'p50_loss':S('p50'),'mean_loss':S('mean'),'p90_loss':S('p90'),'probability_above_appetite':div(S('exceed'),S('n')),'draw_count':S('n'),'reporting_eligible':choose(O('ge',S('n'),100000),1,0)},
        aggregate_constraints=[O('eq',S('appetite_min'),S('appetite_max'))],output_units={'probability_above_appetite':'probability','draw_count':'count'},
        note='The input is the full joint annual portfolio draw after scenario aggregation. reference/assurance.py supplies the explicit joint-scenario reducer. Model calibration and control-credit evidence are required separately.')

    normalization(result,cards)
    put('STD-003',{'business_service_id':T(),'asset_id':T(),'asset_risk':N(0,100),
                  'service_criticality':N(enum=[1,1.25,1.5,2]),'dependency_factor':N(enum=[1,1.25,1.5]),
                  'mapping_version':T(),'owner_id':T(),'decision_ref':T()},
        {},{'services':None,'service_count':None},identity_fields=['business_service_id','asset_id'],
        output_units={'service_count':'count'},primary_outputs=['services'],empty_outputs={'services':[],'service_count':0},
        note='Full asset-to-service population required before ranking. Shared assets appear once per service. Equal raw priorities share a competition rank; case-sensitive service ID ascending breaks display ties. All-zero complete populations receive zero scores.')
    result['STD-003']['grouping']='service_ranking'
    result['STD-003']['output_contracts']['services']={'type':'array','items':{'business_service_id':'string','service_risk_raw':'number','service_risk':'number','competition_rank':'integer'}}

def normalization(result,cards):
    def normalized(prefix):
        return clip(choose(O('eq',F(prefix+'_direction'),'higher'),
            mul(100,div(sub(F(prefix+'_raw'),F(prefix+'_worst')),sub(F(prefix+'_target'),F(prefix+'_worst')))),
            mul(100,div(sub(F(prefix+'_worst'),F(prefix+'_raw')),sub(F(prefix+'_worst'),F(prefix+'_target'))))))
    def inputs_for(prefixes):
        inputs={};constraints=[]
        for prefix in prefixes:
            inputs.update({prefix+'_raw':N(-1e15),prefix+'_target':N(-1e15),prefix+'_worst':N(-1e15),prefix+'_direction':T(['higher','lower']),
                           prefix+'_normalization_version':T(),prefix+'_evidence_ref':T()})
            constraints.append(choose(O('eq',F(prefix+'_direction'),'higher'),O('gt',F(prefix+'_target'),F(prefix+'_worst')),O('lt',F(prefix+'_target'),F(prefix+'_worst'))))
        return inputs,constraints
    def put(cid,inputs,outs,constraints):
        result[cid]=plan(cards[cid],inputs,{k:A('max',v) for k,v in outs.items()},{k:S(k) for k in outs},single=True,row_constraints=constraints)
    names={'phishing_report_rate':.35,'simulation_failure_rate':.25,'training_currency':.20,'risky_action_rate':.20}
    inputs,constraints=inputs_for(names)
    for prefix in names:inputs[prefix+'_direction']=T(['lower' if prefix in ('simulation_failure_rate','risky_action_rate') else 'higher'])
    put('HRM-001',inputs,{'value':add(*(mul(w,normalized(k)) for k,w in names.items())),**{k+'_posture':normalized(k) for k in names}},constraints)
    pillars={'ce':{'STD-006':1},'em':{'STD-014':.4,'STD-015':.3,'STD-013':.2,'STD-029':.1},
             'dr':{'SOC-002':.3,'SOC-003':.3,'SOC-004':.25,'SOC-009':.15},'re':{'STD-008':1},
             'gov':{'STD-007':.4,'STD-053':.35,'STD-054':.25},'dc':{'STD-011':1}}
    children={cid:cid.lower().replace('-','_') for kids in pillars.values() for cid in kids}
    inputs,constraints=inputs_for(children.values())
    for cid,prefix in children.items():
        inputs[prefix+'_card_version']=T([cards[cid]['card_version']])
        direction=cards[cid].get('direction','')
        if direction.startswith('higher_is_better'):inputs[prefix+'_direction']=T(['higher'])
        elif direction.startswith(('lower_is_better','zero_is_target')):inputs[prefix+'_direction']=T(['lower'])
    inputs.update({'tsp':N(0,25),'edp':N(0,15),'tsp_version':T([cards['STD-001a']['card_version']]),'edp_version':T([cards['STD-001b']['card_version']]),'tsp_evidence_ref':T(),'edp_evidence_ref':T()})
    values={p:add(*(mul(w,normalized(children[cid])) for cid,w in kids.items())) for p,kids in pillars.items()}
    raw=sub(sub(add(*(mul(w,values[k]) for k,w in {'ce':.25,'em':.20,'dr':.20,'re':.15,'gov':.10,'dc':.10}.items())),F('tsp')),F('edp'))
    put('STD-001',inputs,{'value':clip(raw),'unclipped_score':raw,**values,**{prefix+'_posture':normalized(prefix) for prefix in children.values()}},constraints)
