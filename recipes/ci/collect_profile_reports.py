#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Attach matching runtime evidence without promoting absent/stale engine runs."""
import argparse
import hashlib
import json
from pathlib import Path

DIALECT={'python':'py','duckdb':'gsql','postgresql':'pg','formulas':'xlsx','libreoffice':'xlsx','spl':'spl','esql':'esql'}


def collect(folder, report_folder=None):
    folder=Path(folder);bundle=folder/'execution-profiles.json'
    digest=hashlib.sha256(bundle.read_bytes()).hexdigest()
    coverage=json.loads((folder/'execution-coverage.json').read_text());by_key={(r['card_id'],r['dialect']):r for r in coverage['matrix']}
    rejected=[];reports=[]
    report_root=Path(report_folder) if report_folder else folder
    for file in sorted(report_root.rglob('profile-report-*.json')):
        report_name=file.relative_to(report_root).as_posix()
        report=json.loads(file.read_text());engine=report.get('engine')
        if report.get('profile_bundle_sha256')!=digest:
            rejected.append({'report':report_name,'reason':'source_bundle_mismatch'});continue
        if engine not in DIALECT or not report.get('engine_version') or not report.get('cases'):
            rejected.append({'report':report_name,'reason':'invalid_or_empty_engine_report'});continue
        ids={c['card_id'] for c in report['cases']}
        for cid in ids:
            if (cid,DIALECT[engine]) not in by_key:raise ValueError('Engine report refers to unknown card')
            tests=[c for c in report['cases'] if c['card_id']==cid]
            by_key[(cid,DIALECT[engine])].setdefault('execution_evidence',[]).append({
                'engine':engine,'engine_version':report['engine_version'],'report':report_name,
                'report_sha256':hashlib.sha256(file.read_bytes()).hexdigest(),
                'stage':report['stage'],'case_ids':[c['case_id'] for c in tests],
                'outputs':sorted({o for c in tests for o in c['outputs']}),
                'status':'pass' if all(c['status']=='pass' for c in tests) else 'fail'})
        reports.append(report_name)
    coverage.update(profile_bundle_sha256=digest,accepted_reports=reports,rejected_reports=rejected)
    (folder/'conformance-matrix.json').write_text(json.dumps(coverage,indent=2)+'\n')
    return coverage


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--bundle',default='recipes/out');ap.add_argument('--reports');a=ap.parse_args()
    result=collect(a.bundle,a.reports)
    print(f'{len(result["accepted_reports"])} matching reports; {len(result["rejected_reports"])} stale/invalid reports excluded; {len(result["matrix"])} card/dialect rows')
