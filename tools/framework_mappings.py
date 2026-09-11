#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate source-bound mapping assessments separately from actual approvals."""
import argparse
from collections import Counter
from datetime import date
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
import yaml

ROOT = Path(__file__).resolve().parents[1]
RELATIONSHIPS = {'supports_measurement_of', 'partial_support', 'informative_topic_association', 'no_claim'}
BINDINGS = ('card_id', 'card_version', 'source_card_sha256', 'source_reference_sha256')


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


@lru_cache(maxsize=1)
def identifiers():
    return yaml.safe_load((ROOT/'catalog/framework-identifiers.yaml').read_text(encoding='utf-8'))['frameworks']


def validate_identifiers(reference):
    """Check complete versioned identifiers, without inferring semantic support."""
    if 'NIST CSF 2.0' not in reference:
        return {'status': 'not_checked', 'category_ids': []}
    spec = identifiers()['nist_csf_2_0']
    tail = reference.split('2.0', 1)[1].strip(' ,/:')
    tokens = re.split(r'[,/:\s]+', tail) if tail else []
    known = set(spec['category_ids']) | set(spec.get('subcategory_ids', [])) | {'GV','ID','PR','DE','RS','RC'}
    unknown = set(tokens)-known
    if unknown:
        raise ValueError('Unknown CSF 2.0 identifiers: '+', '.join(sorted(unknown)))
    if len(tokens) != len(set(tokens)):
        raise ValueError('Duplicate CSF identifier in one association')
    categories = [t for t in tokens if '.' in t]
    return {'status': 'category_ids_checked' if categories else 'function_level_only',
            'category_ids': categories, 'element_ids': tokens, 'source': spec['source'], 'locator': spec['locator']}


def stated_edition(reference):
    # Bare control numbers (CIS Controls 7) and regulation numbers are not editions.
    match = re.search(r':(20\d{2})\b|\b(?:v|Rev\.?\s*)(\d+(?:\.\d+)*)\b|\b(?:CSF|ZTMM) (2\.0)\b', reference)
    return next((v for v in match.groups() if v), None) if match else None


def require_text(record, *fields):
    for name in fields:
        if not isinstance(record.get(name), str) or not record[name].strip():
            raise ValueError('Missing mapping field '+name)


def check_date(value):
    require_text({'date': value}, 'date')
    parsed = date.fromisoformat(value)
    if parsed > date.today():
        raise ValueError('Future mapping decision date')


def binding(record, entry):
    for name in BINDINGS:
        if record.get(name) != entry[name]:
            raise ValueError('Stale or misidentified mapping '+entry['mapping_id']+' '+name)
    if record.get('conformity_claim', False) is not False:
        raise ValueError('A mapping does not establish conformity')
    if 'source_reference' in record and record['source_reference'] != entry['source_reference']:
        raise ValueError('Changed source text with unchanged reference hash')


def assessment_hash(record):
    return digest(record)


def cited_elements(framework, reference):
    if framework == 'NIST CSF':
        return validate_identifiers(reference)['element_ids']
    if framework == 'CIS Controls':
        tail = reference.split(':', 1)[1] if ':' in reference else re.sub(r'^CIS Controls?\s*', '', reference)
        return re.findall(r'\d+', tail)
    if framework == 'NIST SP 800-53':
        return re.findall(r'\b[A-Z]{2}(?:-\d+)?\b', reference.split('800-53', 1)[1])
    if framework == 'NIST AI RMF':
        tail = reference.split(':', 1)[1].strip() if ':' in reference else ''
        tokens = [t.upper() for t in re.split(r'[,/\s]+', tail)] if tail else []
        if set(tokens)-{'GOVERN', 'MAP', 'MEASURE', 'MANAGE'} or len(tokens) != len(set(tokens)):
            raise ValueError('Unknown or duplicate AI RMF function citation')
        return tokens
    if framework == 'OWASP SAMM' and re.search(r'\bVerification\b', reference):
        return ['Verification']
    if framework == 'NIST PQC':
        return ['FIPS-'+n for n in re.findall(r'\d+', reference)]
    return []


def inventory(cards, reviews, assessments=None, sources=None):
    entries = {}
    for card in cards:
        for reference in card['framework_mapping']:
            ref_hash = hashlib.sha256(reference.encode()).hexdigest()
            key = card['id']+':'+ref_hash[:16]
            if key in entries:
                raise ValueError('Duplicate framework association '+key)
            entries[key] = {'mapping_id': key, 'card_id': card['id'], 'card_version': card['card_version'],
                'source_card_sha256': digest(card), 'source_reference': reference, 'source_reference_sha256': ref_hash,
                'edition_stated': stated_edition(reference), 'relationship': 'not_assessed',
                'assessment_status': 'untriaged', 'review_status': 'unreviewed', 'approval_status': 'pending',
                'rationale': None, 'evidence_ref': None, 'reviewer': None, 'decision_date': None,
                'conformity_claim': False, 'identifier_validation': validate_identifiers(reference)}
    seen = set()
    for record in assessments or []:
        key = record.get('mapping_id')
        if key not in entries or key in seen:
            raise ValueError('Unknown or duplicate mapping assessment '+str(key))
        seen.add(key)
        entry = entries[key]
        binding(record, entry)
        require_text(record, 'rationale', 'scope_limit', 'assessment_date', 'framework', 'reference')
        if record['reference'] != entry['source_reference']:
            raise ValueError('Assessed reference does not match its source binding')
        check_date(record['assessment_date'])
        if record.get('assessment_status') not in ('assessed', 'blocked'):
            raise ValueError('Unknown assessment status')
        if record.get('approval_status') != 'pending' or record.get('reviewer') is not None:
            raise ValueError('An assessment cannot manufacture approval or reviewer identity')
        if record.get('assessment_status') == 'blocked':
            if record.get('relationship') != 'not_assessed':
                raise ValueError('Blocked assessment cannot claim a relationship')
            require_text(record, 'blocker', 'next_action')
        else:
            if record.get('relationship') not in RELATIONSHIPS:
                raise ValueError('Unknown assessed relationship')
            require_text(record, 'edition', 'edition_basis', 'source_id', 'source_locator')
            if record['edition_basis'] not in ('explicit_source_edition', 'selected_review_baseline'):
                raise ValueError('Unknown edition basis')
            if record['edition_basis'] == 'explicit_source_edition' and record['edition'] != entry['edition_stated']:
                raise ValueError('Edition is not explicitly stated by the source reference')
            if record['edition_basis'] == 'selected_review_baseline':
                require_text(record, 'edition_selection_rationale')
            source = (sources or {}).get(record['source_id'])
            if not source or source.get('edition') != record['edition']:
                raise ValueError('Unknown or mismatched source edition')
            if source.get('framework') != record['framework']:
                raise ValueError('Source framework identity mismatch')
            ref = entry['source_reference']
            if not (re.match(r'^CIS Controls?\b', ref) if record['framework']=='CIS Controls'
                    else ref.startswith(record['framework'])):
                raise ValueError('Evidence describes a different cited framework')
            if record.get('source_metadata_sha256') != digest(source):
                raise ValueError('Stale source metadata')
            required = source.get('element_ids', [])
            for name in ('supported_elements', 'unsupported_elements'):
                if not isinstance(record.get(name), list) or len(record[name]) != len(set(record[name])):
                    raise ValueError('Missing or duplicate assessed elements')
            if set(record['supported_elements']) & set(record['unsupported_elements']):
                raise ValueError('Contradictory element disposition')
            if set(record['supported_elements'])-set(required):
                raise ValueError('Unknown supported source element')
            if record['relationship'] == 'no_claim' and record['supported_elements']:
                raise ValueError('No-claim relationship has supported elements')
            if record['relationship'] != 'no_claim' and not record['supported_elements']:
                raise ValueError('Relationship lacks supported elements')
            if record['relationship'] == 'supports_measurement_of' and record['unsupported_elements']:
                raise ValueError('Unsupported elements require partial support')
            cited = cited_elements(record['framework'], ref)
            if record.get('cited_elements') != cited:
                raise ValueError('Cited elements changed or omitted')
            def within(element, parent):
                return element == parent or element.startswith(parent+'.') or element.startswith(parent+'-')
            proposed = record.get('proposed_elements_outside_citation', [])
            if (not isinstance(proposed, list) or len(proposed) != len(set(proposed))
                    or set(proposed)-set(required)
                    or set(proposed) & set(record['supported_elements'])
                    or any(any(within(e, p) for p in cited) for e in proposed)):
                raise ValueError('Invalid replacement element outside the original citation')
            if cited:
                if any(not any(within(e, p) for p in cited) for e in record['supported_elements']):
                    raise ValueError('Proposed replacement cannot masquerade as the original citation')
                unsupported = [p for p in cited if not any(within(e, p) for e in record['supported_elements'])]
                if record['unsupported_elements'] != unsupported:
                    raise ValueError('Unmeasured cited elements omitted from disposition')
            entry['evidence_ref'] = source['url']
        entry.update({k: v for k, v in record.items() if k not in (
            'review_status', 'decision_date', 'review_record_ref', 'evidence_ref', 'source_reference',
            'edition_stated', 'identifier_validation', 'assessment_sha256')})
        entry['assessment_sha256'] = assessment_hash(record)
        # Never copy an authority assertion from an input assessment.
        entry['review_status'] = 'unreviewed'
        entry['approval_status'] = 'pending'
        entry['conformity_claim'] = False
    reviewed = set()
    for review in reviews:
        key = review.get('mapping_id')
        if key not in entries or key in reviewed:
            raise ValueError('Unknown or duplicate mapping review '+str(key))
        entry = entries[key]
        binding(review, entry)
        if entry['assessment_status'] != 'assessed':
            raise ValueError('Approval requires a completed assessment')
        if review.get('assessment_sha256') != entry['assessment_sha256']:
            raise ValueError('Approval is not bound to the current assessment')
        require_text(review, 'reviewer', 'decision_date', 'review_record_ref', 'rationale', 'decision')
        check_date(review['decision_date'])
        if review['decision'] not in ('approve', 'reject'):
            raise ValueError('Unknown review disposition')
        # Review references must be public, durable OSMS review records.
        if not re.fullmatch(r'https://github\.com/OpenSecurityMetricsStandard/OSMS/(?:pull|issues)/\d+(?:#[A-Za-z0-9_-]+)?', review['review_record_ref']):
            raise ValueError('Review requires an OSMS issue or pull request evidence record')
        reviewed.add(key)
        entry.update(reviewer=review['reviewer'], decision_date=review['decision_date'],
                     review_record_ref=review['review_record_ref'], review_rationale=review['rationale'],
                     review_status='reviewed', approval_status='approved' if review['decision']=='approve' else 'rejected')
    values = list(entries.values())
    return {'schema_version':'2.0', 'conformity_claim':False, 'mapping_count':len(values),
        'triaged_count':len(seen), 'assessed_count':sum(e['assessment_status']=='assessed' for e in values),
        'not_assessed_count':sum(e['assessment_status']!='assessed' for e in values),
        'reviewed_count':len(reviewed), 'approved_count':sum(e['approval_status']=='approved' for e in values),
        'relationship_counts':dict(sorted(Counter(e['relationship'] for e in values).items())),
        'blocker_counts':dict(sorted(Counter(e['blocker'] for e in values if e.get('blocker')).items())),
        'mappings':values}


def repository_inventory():
    cards = yaml.safe_load((ROOT/'catalog/osms-catalog.yaml').read_text(encoding='utf-8'))['cards']
    reviews = yaml.safe_load((ROOT/'catalog/framework-mapping-reviews.yaml').read_text(encoding='utf-8'))['reviews']
    assessments = yaml.safe_load((ROOT/'catalog/framework-mapping-assessments.yaml').read_text(encoding='utf-8'))['assessments']
    sources = yaml.safe_load((ROOT/'catalog/framework-sources.yaml').read_text(encoding='utf-8'))['sources']
    result = inventory(cards, reviews, assessments, sources)
    result['source_files_sha256'] = {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in (
        'catalog/osms-catalog.yaml', 'catalog/framework-mapping-assessments.yaml',
        'catalog/framework-mapping-reviews.yaml', 'catalog/framework-sources.yaml', 'catalog/framework-identifiers.yaml',
        'catalog/framework-mapping-policy.yaml', 'tools/framework_mappings.py')}
    result['source_catalog_sha256'] = result['source_files_sha256']['catalog/osms-catalog.yaml']
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True)
    parser.add_argument('--require-triaged', action='store_true')
    parser.add_argument('--require-reviewed', action='store_true')
    args = parser.parse_args()
    report = repository_inventory()
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print('; '.join(f'{report[k]} {k}' for k in ('mapping_count','triaged_count','assessed_count','not_assessed_count','reviewed_count','approved_count')))
    if args.require_triaged and report['triaged_count'] != report['mapping_count']:
        raise SystemExit(1)
    if args.require_reviewed and report['reviewed_count'] != report['mapping_count']:
        raise SystemExit(1)
