# SPDX-License-Identifier: MIT
"""Independent SOC-003 integration oracles shared by native test adapters."""
import copy
import json
from pathlib import Path


def cases():
    base=json.loads((Path(__file__).resolve().parents[1]/'fixtures/soc003.json').read_text(encoding='utf-8'))
    base['case_id']='independent_incident_snapshot'
    result=[base]
    empty=copy.deepcopy(base);empty.update(case_id='empty_snapshot',rows=[])
    empty['expect']={k:(0 if k.endswith('_cases') or k in ('closed_cases','identity_errors','open_cases_at_period_end') else None) for k in base['expect']}
    result.append(empty)
    duplicate=copy.deepcopy(base);duplicate['case_id']='duplicate_identity'
    duplicate['rows'].append(copy.deepcopy(base['rows'][0]))
    duplicate['expect'].update(closed_cases=6,identity_errors=2,open_cases_at_period_end=None)
    for family in ('mttr','mtta','mttc'):
        duplicate['expect'][family+'_valid_cases']=6
        for suffix in ('p50_h','p90_h','mean_h_supplementary'):duplicate['expect'][family+'_'+suffix]=None
    result.append(duplicate)
    missing=copy.deepcopy(base);missing['case_id']='missing_acknowledgement'
    missing['rows'][0]['ack_at']=None
    missing['expect'].update(mtta_valid_cases=4,mtta_invalid_cases=1,mtta_p50_h=None,mtta_p90_h=None,mtta_mean_h_supplementary=None)
    result.append(missing)
    decoy=copy.deepcopy(base);decoy['case_id']='foreign_scope_does_not_change_results'
    decoy['rows'].append(dict(base['rows'][0],scope_id='other-scope'))
    result.append(decoy)
    return result
