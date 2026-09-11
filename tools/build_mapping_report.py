#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Render a reproducible F-27 review summary from the bound mapping register."""
import argparse
from collections import Counter
from pathlib import Path
import yaml
from framework_mappings import ROOT, repository_inventory


def render():
    r=repository_inventory();sources=yaml.safe_load((ROOT/'catalog/framework-sources.yaml').read_text())['sources']
    lines=['# F-27 — Source-bound framework relationship assessments',
        f'{r["mapping_count"]:,} source associations; **{r["assessed_count"]} desk assessments, {r["not_assessed_count"]} not assessed, {r["reviewed_count"]} actual reviews and {r["approved_count"]} approvals. F-27 remains open.**',
        'The latest remediation adds 186 assessments to the previous 762. The catalog reference strings remain the original source; narrowing and withdrawal are explicit proposals. No certification, legal conformity, publisher endorsement or Board approval is granted.',
        '## Relationship inventory','| Proposed relationship | Records |','|---|---:|']
    lines += [f'| `{k}` | {v} |' for k,v in r['relationship_counts'].items()]
    lines += ['','## Primary-source baselines',
        'Selected baselines are explicit choices, not assertions of the original author’s intended edition or the latest consolidated instrument. Metadata hashes bind descriptions; actual document hashes are separately identified where bytes were retrieved.',
        '| Source / selected edition | Assessed associations | Evidence scope |','|---|---:|---|']
    counts=Counter(x['source_id'] for x in r['mappings'] if x['assessment_status']=='assessed')
    for key,count in sorted(counts.items(),key=lambda x:(sources[x[0]]['framework'],x[0])):
        s=sources[key];lines.append(f'| [{s["framework"]} — {s["edition"]}]({s["url"]}) | {count} | '+s['evidence_scope'].replace('|',' / ')+' |')
    lines += ['','## Material limits',
        '- DORA, NIS2, GDPR and the AI Act are compared to their original Official Journal texts. Entity/role scope, national transposition, amendments and later delegated/implementing acts require their own applicability assessment. ENISA guidance is nonbinding and does not apply identically to every NIS2 entity.',
        '- The 83 ISO/IEC 27004:2016 associations use only the public abstract. No unseen clause, unpublished successor or ISO/IEC 27001:2022 equivalence is claimed.',
        '- ATT&CK 19.2 is bound to an immutable STIX collection and actual bytes hash. Current data components and detection strategies remain distinct from deprecated legacy data sources. Collection/type references are topic associations; organization-specific coverage needs selected object IDs and executed evidence.',
        '- KEV uses the pinned 2026.09.10 snapshot. EPSS uses the documented model v2026.06.15 baseline; no daily score snapshot or actual OSMS data ingestion is claimed. Forecast probabilities, known exploitation and observed local compromise remain distinct. Severity-weighted products and sums are indices, not calibrated loss or organization-level probabilities.',
        '- Compound references retain every cited part. TPR-011 supports a register facet of DORA Article 28, not Article 30 contracts; PRI-001 does not substantiate actual Article 33 notifications; STD-001a uses KEV but no EPSS input. Autonomous AI closure does not demonstrate Articles 13/14 of the AI Act.',
        '- SOC-080 uses an actually-exploited-or-KEV/EPSS-high proxy target. If the same inputs set priority, apparent accuracy can be circular; independent future exploitation outcomes need separate pilot validation.',
        '','## Remaining assessment requirements','| Requirement | Associations |','|---|---:|']
    lines += [f'| `{k}` | {v} |' for k,v in r['blocker_counts'].items()]
    lines += ['','The 201 outstanding associations comprise 180 authorized standard-clause comparisons, 12 CISA ZTMM primary-text assessments, seven insufficiently identified publications/local policies, one EBA guidance comparison and one unresolved CTID/Atomic source. The generated `source-evidence-queue.md` groups procurement work; every card still needs its own semantic decision.',
        '','## Review and correction workflow',
        '1. Inspect the card formula, population, decision and exact reference together with the selected source text.',
        '2. Review supported, unsupported and proposed replacement elements separately. The generated packet includes each source assessment in its card dossier and produces `mapping-withdrawal-proposals.json`.',
        '3. Record an actual responsible reviewer, date, rationale and durable OSMS issue/PR evidence. Bind the decision to the current card, reference and assessment hashes in `catalog/framework-mapping-reviews.yaml`.',
        '4. Apply approved catalog changes with version/trend-break handling and update dependent records. Generating a proposal does not apply it or count as its approval.',
        '','```sh',
        'python tools/framework_mappings.py --require-triaged --out framework-mapping-register.json',
        'python tools/build_mapping_report.py --check',
        '# These completion gates must currently fail while evidence/reviews are absent:',
        'python tools/framework_mappings.py --require-assessed --out framework-mapping-register.json',
        'python tools/framework_mappings.py --require-reviewed --out framework-mapping-register.json',
        '```',
        'Accounting, assessment, actual review and approval have separate counters. The validator checks record consistency, not reviewer identity or the truth of an assessment.',
        '',f'Catalog SHA-256: `{r["source_catalog_sha256"]}`. The generated register also binds source descriptions, assessment records, policy and validation code. Actual CI results belong to the checked commit; this generated summary does not invent a test result.',
        '','## Proposed withdrawals or reassignments',
        f'All {r["relationship_counts"].get("no_claim",0)} entries below remain proposals. A missing direct measurement relationship does not mean the topic can never provide useful organizational context.',
        '| Card | Original reference | Proposed elements outside citation |','|---|---|---|']
    for x in r['mappings']:
        if x['relationship']=='no_claim':lines.append(f'| {x["card_id"]} | {x["source_reference"]} | '+(', '.join(x.get('proposed_elements_outside_citation',[])) or 'No replacement asserted')+' |')
    return '\n'.join(lines)+'\n'


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',default=str(ROOT/'review/framework/F27_ASSESSMENT.md'));ap.add_argument('--check',action='store_true');a=ap.parse_args()
    result=render();p=Path(a.out)
    if a.check:
        if not p.exists() or p.read_text(encoding='utf-8')!=result:raise SystemExit('F-27 summary is stale; regenerate it')
        print('F-27 summary matches the source register')
    else:p.write_text(result,encoding='utf-8');print('F-27 summary generated')
