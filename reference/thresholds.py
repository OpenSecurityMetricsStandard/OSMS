#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Candidate boundary profiles for six audit findings; not board-approved policy.

Inputs are already scoped, version-compatible measurements in card units.
The caller must supply provenance, period and confidence production evidence.
This module evaluates boundaries only and never claims that evidence is genuine.
"""
import math

PROFILE_VERSION = 'rag-boundaries-0.1-draft'


def assess(card_id, value, *, confidence, context='operational', baseline=None,
           critical_override=None, evidence_complete=None):
    def result(rag, status='valid', reason=None):
        return {'rag':rag, 'validity_status':status, 'reason':reason,
                'profile_version':PROFILE_VERSION, 'card_id':card_id}
    def finite(x):
        return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)
    if context not in ('operational','board'):
        raise ValueError('Unknown reporting context')
    if not finite(value):
        return result(None,'invalid','missing_or_nonfinite_value')
    if card_id == 'SOC-063':
        if value < 0:
            return result(None,'invalid','negative_capacity_ratio')
        rag = 'green' if 90 <= value <= 110 else 'amber' if 75 <= value <= 125 else 'red'
    elif card_id in ('STD-019','STD-055'):
        if value < 0 or not isinstance(critical_override,bool):
            return result(None,'invalid','require_nonnegative_overdue_days_and_critical_flag')
        rag = 'red' if critical_override or value >= 30 else 'amber' if value > 0 else 'green'
    elif card_id == 'STD-012':
        if not finite(baseline) or baseline <= 0:
            return result(None,'not_applicable','relative_plan_comparison_requires_positive_plan')
        deviation = (baseline - value) / baseline * 100
        rag = 'green' if deviation <= 0 else 'amber' if deviation <= 25 else 'red'
    elif card_id == 'STD-015':
        if value < 0 or not isinstance(critical_override,bool):
            return result(None,'invalid','require_nonnegative_exposure_and_SLA_override_flag')
        if critical_override:
            rag = 'red'
        elif not finite(baseline) or baseline < 0:
            return result(None,'provisional','missing_comparable_baseline')
        elif baseline == 0:
            rag = 'amber' if value == 0 else 'red'
        else:
            change = (value - baseline) / baseline * 100
            rag = 'green' if change < 0 else 'amber' if change <= 50 else 'red'
    elif card_id == 'STD-005':
        if value <= 0:
            rag = 'red'
        elif not finite(baseline) or evidence_complete is not True:
            return result(None,'provisional','require_comparable_baseline_and_verified_top5_investments')
        else:
            rag = 'green' if value >= baseline else 'amber'
    else:
        raise NotImplementedError(f'No boundary profile for {card_id}')
    gate = 85 if context == 'board' else 70
    if not finite(confidence) or not 0 <= confidence <= 100:
        return result(None,'provisional','confidence_unknown_or_invalid')
    if confidence < gate:
        return result(None if rag == 'green' else rag,'provisional','confidence_below_context_gate')
    return result(rag)
