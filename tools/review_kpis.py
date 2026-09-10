#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read-only review KPIs with paginated GitHub input and reproducible snapshots.

K-06: elapsed UTC weekdays (24 hours/day), excluding supplied holidays.
K-09: recorded board evidence; membership is never inferred from GitHub.
"""
import argparse
import json
import re
import statistics
import subprocess
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

CATS = ['card-contract', 'formula', 'data-source', 'data-confidence', 'taxonomy', 'domain',
        'decision-chain', 'evidence', 'hierarchy', 'board-relevance', 'implementation', 'language']
DECISIONS = {'accepted', 'rejected', 'deferred', 'accepted-risk'}
SEVERITIES = {'critical', 'major', 'minor', 'editorial'}
ID_PATTERN = r'(?<![A-Za-z0-9_-])[A-Z]{2,4}-\d{3}[a-z]?(?![A-Za-z0-9_-])'


def parse_dt(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Timestamps must include a UTC offset')
    return result.astimezone(timezone.utc)


def labels(issue):
    return {x if isinstance(x, str) else x['name'] for x in issue.get('labels', [])}


def one_label(issue, prefix, allowed):
    values = {x.split(':', 1)[1] for x in labels(issue) if x.startswith(prefix + ':')}
    return next(iter(values)) if len(values) == 1 and values <= allowed else None


def final_decision(issue):
    # pending, breaking, unknown and conflicting decisions do not count.
    return one_label(issue, 'decision', DECISIONS)


def load_catalog_ids(path):
    import yaml
    root = Path(path)
    files = [root] if root.is_file() else sorted({*root.rglob('*.yaml'), *root.rglob('*.yml')})
    ids, p0 = set(), set()
    for file in files:
        doc = yaml.safe_load(file.read_text(encoding='utf-8')) or {}
        cards = doc if isinstance(doc, list) else doc.get('cards', [])
        for card in cards:
            if isinstance(card, dict) and card.get('id'):
                ids.add(card['id'])
                if card.get('priority') == 'P0':
                    p0.add(card['id'])
    if not ids:
        raise ValueError(f'No catalog cards loaded from {path}')
    return ids, p0


def working_days(start, end, holidays=()):
    if end < start:
        raise ValueError('Triage timestamp precedes submission')
    total = 0.0
    while start < end:
        midnight = datetime.combine(start.date() + timedelta(days=1), time(), timezone.utc)
        stop = min(midnight, end)
        if start.weekday() < 5 and start.date().isoformat() not in holidays:
            total += (stop - start).total_seconds() / 86400
        start = stop
    return total


def triage_time(issue, holidays=()):
    active = set()
    for event in sorted(issue.get('events', []), key=lambda e: (e['created_at'], e.get('id', 0))):
        name = event.get('label', {}).get('name')
        if event.get('event') == 'labeled' and name:
            active.add(name)
        elif event.get('event') == 'unlabeled':
            active.discard(name)
        state = {'labels': list(active)}
        if one_label(state, 'cat', set(CATS)) and one_label(state, 'severity', SEVERITIES):
            return working_days(parse_dt(issue.get('created_at') or issue['createdAt']),
                                parse_dt(event['created_at']), holidays)
    return None


def evaluate(snapshot, all_ids, p0_ids, exclude=(), holidays=(), id_pattern=ID_PATTERN):
    excluded = {x.lower() for x in exclude}
    issues = [i for i in snapshot['issues'] if 'pull_request' not in i]
    reviewers, touched = set(), set()
    categories = {c: 0 for c in CATS}
    unknown_categories = unknown_severities = 0
    durations, open_critical, critical_major, cm_decided, decided = [], 0, 0, 0, 0
    events_complete = snapshot.get('events_complete', False)

    def external(record):
        author = record.get('user') or record.get('author') or {}
        login = author.get('login', '').lower()
        return login if login and login not in excluded and author.get('type') != 'Bot' and not login.endswith('[bot]') else None

    for issue in issues:
        context = (issue.get('title') or '') + '\n' + (issue.get('body') or '')
        for record in [issue, *issue.get('comments_data', [])]:
            login = external(record)
            if login:
                reviewers.add(login)
                # External comments inherit their finding's card references.
                touched.update(re.findall(id_pattern, context + '\n' + (record.get('body') or '')))
        cat = one_label(issue, 'cat', set(CATS))
        if cat:
            categories[cat] += 1
        else:
            unknown_categories += 1
        severity = one_label(issue, 'severity', SEVERITIES)
        unknown_severities += severity is None
        is_decided = final_decision(issue) is not None
        decided += is_decided
        if severity in {'critical', 'major'}:
            critical_major += 1
            cm_decided += is_decided
        open_critical += severity == 'critical' and issue['state'].lower() == 'open'
        if events_complete:
            duration = triage_time(issue, holidays)
            if duration is not None:
                durations.append(duration)

    def coverage(population):
        return {'touched': len(touched & population), 'total': len(population),
                'percent': 100 * len(touched & population) / len(population) if population else None}

    board = snapshot.get('board')
    quorum = None if board is None else {
        'sessions_held': len({s['id'] for s in board.get('sessions', []) if s.get('status') == 'held' and s.get('evidence_ref')}),
        'active_members': len({m['id'] for m in board.get('members', []) if m.get('active') is True and m.get('evidence_ref')}),
        'charter_ref': board.get('charter_ref'),
    }
    return {
        'method_version': 'review-kpis-0.2', 'snapshot_at': snapshot.get('snapshot_at'),
        'calendar': {'timezone': 'UTC', 'working_days': 'Monday-Friday, 24 hours/day', 'holidays': sorted(holidays)},
        'K-01': len(reviewers), 'K-02': len(issues), 'K-03': categories,
        'K-04': coverage(p0_ids), 'K-05': coverage(all_ids),
        'K-06': {'median_working_days': statistics.median(durations) if durations else None,
                  'triaged': len(durations) if events_complete else None,
                  'untriaged': len(issues) - len(durations) if events_complete else None},
        'K-07': {'decided': decided, 'total': len(issues), 'critical_major_decided': cm_decided,
                  'critical_major_total': critical_major},
        'K-08': open_critical, 'K-09': quorum,
        'limitations': {'comments_complete': snapshot.get('comments_complete', False),
                        'events_complete': events_complete, 'unknown_categories': unknown_categories,
                        'unknown_severities': unknown_severities, 'external_form_submissions': 'not included'},
    }


def api_pages(endpoint):
    result = subprocess.run(['gh', 'api', endpoint, '--paginate', '--slurp'],
                            check=True, capture_output=True, text=True)
    pages = json.loads(result.stdout)
    return [item for page in pages for item in page]


def collect(repo, no_triage=False):
    issues = [i for i in api_pages(f'repos/{repo}/issues?labels=finding&state=all&per_page=100')
              if 'pull_request' not in i]
    for issue in issues:
        endpoint = f"repos/{repo}/issues/{issue['number']}"
        issue['comments_data'] = api_pages(endpoint + '/comments?per_page=100')
        if not no_triage:
            issue['events'] = api_pages(endpoint + '/events?per_page=100')
    return {'issues': issues, 'comments_complete': True, 'events_complete': not no_triage,
            'snapshot_at': datetime.now(timezone.utc).isoformat()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo')
    parser.add_argument('--catalog', default='catalog/osms-catalog.yaml')
    parser.add_argument('--snapshot', help='Offline JSON input instead of GitHub')
    parser.add_argument('--save-snapshot', help='Save exact input for reproduction')
    parser.add_argument('--board', help='JSON with members, sessions and charter_ref')
    parser.add_argument('--exclude', nargs='*', default=[])
    parser.add_argument('--holiday', action='append', default=[], help='Non-working UTC date YYYY-MM-DD')
    parser.add_argument('--id-pattern', default=ID_PATTERN)
    parser.add_argument('--no-triage', action='store_true')
    parser.add_argument('--markdown', action='store_true')
    parser.add_argument('--extra-findings', type=int, default=0)
    parser.add_argument('--extra-reviewers', type=int, default=0)
    args = parser.parse_args()
    if not args.snapshot and not args.repo:
        parser.error('Provide --repo or --snapshot')
    if args.extra_findings or args.extra_reviewers:
        parser.error('Import individual findings and deduplicated authors into --snapshot; manual totals cannot establish decisions or coverage.')
    for holiday in args.holiday:
        datetime.strptime(holiday, '%Y-%m-%d')
    snapshot = json.loads(Path(args.snapshot).read_text()) if args.snapshot else collect(args.repo, args.no_triage)
    if args.no_triage:
        snapshot['events_complete'] = False
    if args.board:
        snapshot['board'] = json.loads(Path(args.board).read_text())
    if args.save_snapshot:
        Path(args.save_snapshot).write_text(json.dumps(snapshot, indent=2) + '\n')
    result = evaluate(snapshot, *load_catalog_ids(args.catalog), args.exclude, args.holiday, args.id_pattern)
    if args.markdown:
        print('| KPI | Observed value |\n|---|---|')
        for key, value in result.items():
            if key.startswith('K-'):
                print(f"| {key} | {json.dumps(value, sort_keys=True) if value is not None else 'unavailable'} |")
        print('\nLimitations: ' + json.dumps(result['limitations']))
        print('\nCalendar: ' + json.dumps(result['calendar']))
    else:
        print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
