# SPDX-License-Identifier: MIT
"""Independent companion-output expectations for the published example inputs.

These literal values are hand calculations, never outputs captured from a runner.
Counts describe the explicitly listed fixture records. Empty distributions are
None; a missing distribution is not a measured zero.
"""

SUPPLEMENT = {
    'STD-011': dict(completeness=100, freshness=80, source_authority=90,
                    consistency=60, reconciliation_quality=100),
    'STD-012': dict(weight_sum=4), 'STD-080': dict(weight_sum=4),
    'SOC-050': dict(response_count=2), 'STD-038': dict(accounts=1),
    'LOG-009': dict(expected_events=200), 'TPR-002': dict(stale_evidence_count=1),
    'SOC-006': dict(simulated_rate_base=4, real_rate_base=2),
    'TPR-004': dict(all_contracts_rate_base=4, new_contracts_rate_base=2),
    'TPR-005': dict(supplier_rate_base=4, service_provider_rate_base=2),
    'TPR-007': dict(critical_services_rate_base=4, dora_rate_base=2),
    'TPR-008': dict(critical_supplier_rate_base=4, control_plane_supplier_rate_base=2),
    'SOC-080': dict(precision_base=4, recall_base=6),
    'TPR-012': dict(current_concentration=2), 'STD-074': dict(case_count=2),
    'LOG-016': dict(cost_base=120, usage_base=8), 'SOC-020': dict(incident_base=4),
    'AI-003': dict(regulated_crown_jewel_cases=1, rca_and_control_update_completed_cases=1),
    'DAT-005': dict(regulated_crown_jewel_cases=1, rca_and_control_update_completed_cases=1),
    # 10 + 15 * (1 - 6.5/14); critical 30d = 4, high 61d = 2*1.5.
    'STD-001a': dict(events=2, uncapped_contribution=18.035714285714285),
    'STD-001b': dict(exceptions=2, uncapped_contribution=7),
    'SOC-001': dict(mean_h=16, severity_weighted_mean_h=16),
    'SOC-002': dict(mean_h=16, severity_weighted_mean_h=16),
    'CFG-002': dict(p95=30, tier0_critical_max_days=30),
    'STD-061': dict(open_cases=0, open_age_max_h=None),
    'STD-019': dict(overdue_cases=2, overdue_max_days=16),
    'DET-003': dict(stale_p0_rules=0), 'DET-008': dict(emergency_over_72h=1),
    'APP-005': dict(weighted_exposure_hours=32),
    'APP-010': dict(p95=30, maximum_h=30, recurrence_count=2, recurrence_trend=1),
    'LOG-011': dict(blindspot_age_p95=30, blindspot_age_max=30, blindspot_age_max_tier0=30),
    'SOC-053': dict(sla_rate=0, reportable_cases=2, regulatory_breaches=2, overall_band=2),
    'SOC-026': dict(risk_weighted_exposure_hours=128),
    'SOC-078': dict(exposure_weighted=16, overdue_cases=2, early_escalations=2, overall_band=2),
    'STD-078': dict(pending_measures=0, missing_effect_overdue=0, observed_late=2, overall_band=1),
    'VAL-001': dict(scope_coverage_percent_base=20, remediation_coverage_percent_base=10,
                    scope_coverage_percent_band=0, remediation_coverage_percent_band=2),
    'HRM-001': dict(training_currency_posture=75, simulation_failure_rate_posture=75,
                    phishing_report_rate_posture=75, risky_action_rate_posture=75),
    'STD-001': dict(unclipped_score=60, ce=75, em=75, dr=75, re=75, gov=75, dc=75,
                    std_006_posture=75, std_014_posture=75, std_015_posture=75,
                    std_013_posture=75, std_029_posture=75, soc_002_posture=75,
                    soc_003_posture=75, soc_004_posture=75, soc_009_posture=75,
                    std_008_posture=75, std_007_posture=75, std_053_posture=75,
                    std_054_posture=75, std_011_posture=75),
}
for _card in ('AIM-012','STD-030','STD-043','STD-045','STD-056','STD-035',
              'STD-036','STD-040','STD-041','STD-042','STD-070','STD-013','STD-015'):
    SUPPLEMENT[_card] = {'case_count': 1}


def supplement(examples):
    for card_id, expected in SUPPLEMENT.items():
        overlap = set(examples[card_id][0]['expected']) & set(expected)
        if overlap:
            raise ValueError('Duplicate independently maintained oracle: '+card_id+str(overlap))
        examples[card_id][0]['expected'].update(expected)
