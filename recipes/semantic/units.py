# SPDX-License-Identifier: MIT
"""Per-output units; a diagnostic never inherits an unrelated card display unit."""
ALIASES={
 'Score points (0-100)':'score_points','Score points (deduction)':'score_points',
 'Percent (%)':'percent','Percentage points (pp)':'percentage_points',
 'Count per day':'count/day','Analyst hours (h)':'hours',
 'Index':'index_points','Index value':'index_points','Index points (baseline = 100)':'index_points',
 'Currency amount (EUR)':'EUR','Euro (€) per incident':'EUR/incident',
 'Currency unit (EUR)':'EUR','Euro (€) and loss distribution':'EUR/year',
 'Index points (open scale, >= 0)':'index_points',
 'Index points (weighted risk sum, >=0; no fixed cap)':'index_points',
 'Risk-weighted value (unbounded weighted sum)':'risk_points',
 'Count or risk-weighted value':'risk_weighted_count',
 'Risk-weighted hours (unbounded sum)':'risk_weighted_hours',
 'Points (risk-weighted backlog score, unbounded sum)':'risk_points',
 'Risk-weighted count (sum of criticality weights of over-privileged roles; >= 0)':'risk_weighted_count',
 'Risk points (sum of finding contributions; 0-100 per finding, total unbounded above)':'risk_points',
 'Risk points (sum of weighted individual contributions, >= 0, unbounded above)':'risk_points',
 'Percent improvement over versioned baseline (%)':'percent',
 'CSAT 1–5':'csat_points','NPS -100–100':'nps_points',
}
OVERRIDES={
 'STD-003a':{'risk_index':'score_points'},
 'SOC-080':{'precision':'percent','recall':'percent'},
 'STD-004':{'burn_down':'risk_points','plan_deviation_percent':'percent'},
 'SOC-064':{'coefficient_of_variation':'ratio'},
 'TPR-012':{'current_concentration':'weighted_dependence_share'},
 'LOG-016':{'value':'reporting_currency/telemetry_unit','cost_base':'reporting_currency'},
 'SOC-050':{'value':'survey_points'},
 'LOG-015':{'value':'risk_points'},
 'CFG-002':{'p95':'days'},
 'DET-003':{'stale_p0_rules':'count'},'DET-008':{'emergency_over_72h':'count'},
 'APP-005':{'weighted_exposure_hours':'risk_weighted_hours'},
 'APP-010':{'p95':'hours','recurrence_trend':'ratio'},
 'LOG-011':{'blindspot_age_p95':'days','blindspot_age_max':'days','blindspot_age_max_tier0':'days'},
 'SOC-053':{'sla_rate':'percent'},
 'SOC-026':{'risk_weighted_exposure_hours':'risk_weighted_hours'},
 'SOC-078':{'exposure_weighted':'risk_weighted_hours'},
 'SOC-035':{'downtime_weighted':'risk_weighted_minutes'},
}

def apply(plans):
    for cid,p in plans.items():
        for key,c in p['output_contracts'].items():
            if c.get('type')=='array':continue
            unit=ALIASES.get(c.get('unit'),c.get('unit'))
            unit=OVERRIDES.get(cid,{}).get(key,unit)
            if key.endswith('_h'):unit='hours'
            if key.endswith('_days'):unit='days'
            if key=='weight_sum':unit='weight_units'
            if key.endswith('_band'):unit='rating_code'
            if key in ('operational_eligible','management_eligible','reporting_eligible'):unit='eligibility_flag'
            c['unit']=unit;c['type']='integer' if unit in ('count','rating_code','eligibility_flag') else 'number'
            if c['type']=='integer':c.update(absolute_tolerance=0,relative_tolerance=0)
            if unit=='rating_code':c['enum']=[0,1,2]
            if unit=='eligibility_flag':c['enum']=[0,1]
            if unit=='survey_points':c['unit_selector']={'input':'survey_variant','csat_1_5':'csat_points','nps_0_10':'nps_points'}
            if unit=='risk_weighted_minutes':c['absolute_tolerance']=1e-7
