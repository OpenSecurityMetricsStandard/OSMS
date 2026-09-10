#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Preview or publish the OSMS audit handoff. Python 3.10+; apply needs git and gh.

Default: local preview only. --apply publishes the bundled branch, creates missing
labels/issues and a draft PR. Existing issues, labels and PRs are never overwritten.
No force push, merge, decision label, issue closure or automatic POST retry.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.parse import urlencode


CATEGORIES = {
    'card-contract': 'Card Contract', 'formula': 'Formula',
    'data-source': 'Data Source', 'data-confidence': 'Data Confidence',
    'taxonomy': 'Taxonomy', 'domain': 'Domain', 'decision-chain': 'Decision Chain',
    'evidence': 'Evidence', 'hierarchy': 'Helper / Parent / Child',
    'board-relevance': 'Board Relevance', 'implementation': 'Implementation',
    'language': 'Language',
}
STATUSES = {
    'open': 'Open', 'partial': 'Partial',
    'decision-pending': 'Proposal implemented - decision pending',
    'verification-pending': 'Implemented - verification pending',
}
COMMIT_ROLES = {
    'candidate_fix': 'Fix-Kandidat; unabhängige Verifikation ausstehend',
    'partial_fix': 'Teilfix; vollständige Behebung ausstehend',
    'proposal': 'Entscheidungsvorschlag; fachliche Freigabe ausstehend',
    'context': 'Kontext/Dokumentation; kein Fix-Nachweis',
}
SHA = re.compile(r'^[0-9a-f]{40}$')


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_json(path, data):
    path = Path(path)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


def validate_manifest(data):
    if data['schema_version'] != 1 or data['repository'] != 'OpenSecurityMetricsStandard/OSMS':
        raise ValueError('Unsupported manifest version or unexpected target repository')
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', data['audit_id']):
        raise ValueError('Invalid audit ID')
    if not re.fullmatch(r'audit/[A-Za-z0-9_-]+', data['branch']):
        raise ValueError('Only an audit branch may be published')
    for key in ('base_commit', 'remediation_commit'):
        if not SHA.fullmatch(data[key]):
            raise ValueError(f'Invalid {key}')
    expected = {f'F-{n:02d}' for n in range(1, 33)}
    findings = data['findings']
    if len(findings) != 32 or {f['id'] for f in findings} != expected:
        raise ValueError('Exactly one record for each F-01 through F-32 is required')
    known = set(data['known_card_ids'])
    if len(known) != 327:
        raise ValueError('Expected the audited 327-card ID inventory')
    for f in findings:
        if f['category'] not in CATEGORIES or f['severity'] not in {'critical', 'major', 'minor'}:
            raise ValueError(f"Invalid category/severity: {f['id']}")
        if f['implementation_status'] not in STATUSES or not set(f['cards']) <= known:
            raise ValueError(f"Invalid status/card IDs: {f['id']}")
        if f['review_decision'] is not None or f['verification_status'] != 'pending':
            raise ValueError('This importer records proposals, not approval or closure')
        for key in ('title', 'observation', 'impact', 'action', 'acceptance', 'implementation_note'):
            if not isinstance(f[key], str) or not f[key].strip():
                raise ValueError(f"Missing {key}: {f['id']}")
        for ref in f['commit_references']:
            if not SHA.fullmatch(ref['sha']) or ref['role'] not in COMMIT_ROLES:
                raise ValueError(f"Invalid commit reference: {f['id']}")
        candidates = [r['sha'] for r in f['commit_references'] if r['role'] == 'candidate_fix']
        if f['fix_commit'] != (candidates[0] if candidates else None):
            raise ValueError(f"Fix field must agree with candidate evidence: {f['id']}")
        if candidates and f['implementation_status'] != 'verification-pending':
            raise ValueError(f"Partial/open finding cannot claim a full fix: {f['id']}")
    website = next(f for f in findings if f['id'] == 'F-28')
    if website['website_fix_commit'] is not None or 'external' not in website['workstream']:
        raise ValueError('Website work is handled externally; its commit is not yet known')


def marker(data, finding):
    return f"<!-- osms-audit:{data['audit_id']}:{finding['id']} -->"


def issue_title(f):
    return f"[{f['id']}] {f['title']}"


def issue_labels(f):
    return ['finding', 'triage', 'audit:2026-09-10', f"cat:{f['category']}",
            f"severity:{f['severity']}", f"status:{f['implementation_status']}"]


def render_issue(data, f):
    repo_url = f"https://github.com/{data['repository']}"
    refs = '\n'.join(f"- {COMMIT_ROLES[r['role']]}: [{r['sha']}]({repo_url}/commit/{r['sha']})"
                     for r in f['commit_references'])
    sources = '\n'.join(f'- [{p}]({u})' for p, u in zip(f['files'], f['sources']))
    cards = ', '.join(f['cards']) or 'Übergreifend; keine einzelne Karte'
    website = ''
    if f['id'] == 'F-28':
        website = '\n### Website-Nachweis\n\nDie Website-Umsetzung wird extern bearbeitet.\n\n- [ ] Website-Fix-Commit/PR ergänzen, bei separatem Repository mit vollständiger URL.\n- [ ] Alle 47 Kartenfelder des Exports mit der Website abgleichen.\n- [ ] Sichtbare Katalog-/Schema-Version und Deployment-Nachweis ergänzen.\n'
    return f"""{marker(data, f)}
### Audit Finding ID

{data['audit_id']} / {f['id']} — GitHub-Issue-Nummer wird separat vergeben.

### Category

{CATEGORIES[f['category']]}

### Severity

{f['severity']} (Triage-Vorschlag; ursprüngliches Audit: {f['audit_severity']}).
Die Übersetzung Hoch → critical, Mittel → major, Niedrig → minor verwendet die
vorhandenen Review-Prioritäten. Keine CVSS-Bewertung oder Boardentscheidung.

### Card ID(s)

{cards}

### Audited baseline

OSMS {data['version']}; [{data['base_commit']}]({repo_url}/tree/{data['base_commit']}).
Die folgende Beobachtung beschreibt diese Ausgangsbasis, nicht pauschal den heutigen Stand.

### Finding

{f['observation']}

### Impact

{f['impact']}

### Proposed change

{f['action']}

### Acceptance criteria

- [ ] {f['acceptance']}
- [ ] Verifikation mit geprüftem Commit, Umgebung, Ergebnis und prüfender Person dokumentiert.
- [ ] Review-Disposition mit Begründung, zuständiger Person und Datum dokumentiert.

### Implementation status

{STATUSES[f['implementation_status']]}

{f['implementation_note']}

### Fix commit(s)

{refs}

Ein Teilfix, Vorschlag oder Dokumentations-Commit ist keine vollständige Erledigung.
Bei Squash/Rebase den resultierenden Commit ergänzen; den ursprünglichen Nachweis erhalten.

### Verification and remaining work

Lokale Prüfungen und ihre Grenzen: [VALIDATION.md]({repo_url}/blob/{data['remediation_commit']}/review/VALIDATION.md).
Ursprünglicher Audit-Probeverweis: `{f['tests'] or 'siehe Beobachtung/Quelldateien'}`
(kein neuer Testlauf durch den Issue-Import).
Noch keine unabhängige Finding-Abnahme oder Boardfreigabe dokumentiert.

### Workstream / dependencies

{f['workstream']}. Vorgeschlagene Fachrolle: {f['owner']}.
Abhängige Audit-IDs: {f['depends'] or 'keine ausdrücklich erfasst'}.
{website}
### Sources at audited baseline

{sources}

### Review disposition

Offen. Dieser Import vergibt keine `decision:*`-Labels und schließt keine Issues.
"""


def preview(data, directory):
    directory.mkdir(parents=True, exist_ok=True)
    for f in data['findings']:
        (directory / f"{f['id']}.md").write_text(render_issue(data, f), encoding='utf-8')
    print(f"Preview: {len(data['findings'])} issue bodies in {directory}")
    print(f"Target: {data['repository']} | branch: {data['branch']}")
    print('Apply: preserve commits, create missing labels/issues, create one draft PR.')
    print('Existing issue content/states and existing label definitions are preserved.')


def run(args, cwd=None, stdin=None):
    env = {**os.environ, 'GH_HOST': 'github.com', 'GH_PROMPT_DISABLED': '1',
           'GIT_TERMINAL_PROMPT': '0', 'GH_PAGER': 'cat'}
    result = subprocess.run(args, cwd=cwd, input=stdin, capture_output=True,
                            text=True, encoding='utf-8', env=env)
    if result.returncode:
        raise RuntimeError(f"{args[0]} failed ({result.returncode}): {result.stderr.strip()}")
    return result.stdout.strip()


class GitHub:
    def __init__(self, repository):
        self.repository = repository

    def api(self, path, payload=None, paginate=False):
        args = ['gh', 'api', '--hostname', 'github.com',
                f'repos/{self.repository}/{path}'.rstrip('/')]
        if paginate:
            args += ['--paginate', '--slurp']
        if payload is not None:
            args += ['--method', 'POST', '--input', '-']
        value = json.loads(run(args, stdin=None if payload is None else json.dumps(payload)))
        return [item for page in value for item in page] if paginate else value

    def issues(self):
        return [i for i in self.api('issues?state=all&per_page=100', paginate=True)
                if 'pull_request' not in i]


def index_issues(data, issues):
    indexed = {}
    for f in data['findings']:
        candidates = [i for i in issues if marker(data, f) in (i.get('body') or '')]
        unmarked = [i for i in issues if re.match(r'^\[(?:Finding\]\s*\[)?' +
                    re.escape(f['id']) + r'\]', i['title']) and i not in candidates]
        if len(candidates) > 1 or unmarked:
            raise ValueError(f"Ambiguous existing {f['id']}; reconcile markers before import")
        if candidates:
            indexed[f['id']] = candidates[0]
    return indexed


def desired_labels(data):
    labels = {
        'finding': ('1F3A5F', 'OSMS review finding'),
        'triage': ('C9CDD4', 'Awaiting maintainer triage'),
        'audit:2026-09-10': ('5319E7', 'OSMS audit baseline 2026-09-10'),
        'severity:critical': ('B60205', 'Blocks the 1.0 freeze'),
        'severity:major': ('D93F0B', 'Must be decided before freeze'),
        'severity:minor': ('FBCA04', 'Editorial / low impact'),
    }
    labels.update({f'cat:{key}': ('0E8A16', value) for key, value in CATEGORIES.items()})
    labels.update({f'status:{key}': ('D4C5F9', value) for key, value in STATUSES.items()})
    return labels


def ensure_labels(client, data):
    existing = {x['name'] for x in client.api('labels?per_page=100', paginate=True)}
    for name, (color, description) in desired_labels(data).items():
        if name not in existing:
            client.api('labels', {'name': name, 'color': color, 'description': description})


def sync_issues(client, data, receipt_path):
    existing = index_issues(data, client.issues())
    receipt = {'repository': data['repository'], 'audit_id': data['audit_id'], 'issues': {}}
    for f in data['findings']:
        issue = existing.get(f['id'])
        action = 'reused' if issue else 'created'
        if not issue:
            # One POST only. On ambiguous failure, stop; a subsequent invocation
            # re-reads ALL issue pages/states and reuses the durable audit marker.
            issue = client.api('issues', {'title': issue_title(f),
                'body': render_issue(data, f), 'labels': issue_labels(f)})
        receipt['issues'][f['id']] = {'number': issue['number'], 'url': issue['html_url'],
                                    'state': issue['state'], 'action': action}
        write_json(receipt_path, receipt)
        print(f"{f['id']} -> #{issue['number']} ({action}, {issue['state']})")
    return receipt


def pr_body(data, receipt):
    rows = '\n'.join(f"| {f['id']} | #{receipt['issues'][f['id']]['number']} | "
                     f"{STATUSES[f['implementation_status']]} |" for f in data['findings'])
    return f"""<!-- osms-audit-pr:{data['audit_id']} -->
The audited OSMS draft contains calculation, data-validity and verification gaps
that can produce misleading security metrics. This candidate corrects selected
defects, blocks unfinished recipes and records the remaining method decisions.

It also adds a structured issue form and a repeatable import of all 32 findings.
Implementation, verification and board disposition remain distinct. Category and
severity labels are proposed triage. No board approval is claimed.

Remediation commit: {data['remediation_commit']}
Audited base: {data['base_commit']}

F-28: Website implementation is handled externally. This PR supplies the repository export/schema
part; the website commit and deployment evidence must be recorded separately.

Local remediation evidence and limitations: `review/VALIDATION.md`.
Import verification: `review/GITHUB_IMPORT.md`. Remote CI has not yet been observed
by this importer. Review the six proposed threshold changes and remaining method
decisions in `review/METHOD_DECISIONS.md`; this is a working draft.

Related findings (references only; no automatic closing keywords):

| Audit ID | GitHub issue | Implementation at handoff |
|---|---|---|
{rows}

Before accepting: inspect CI and independently verify the applicable acceptance
criteria. Merge alone does not close or approve these findings. Prefer a merge
commit to preserve cited SHAs; if squashing/rebasing, add resulting commit links
to each affected issue. Keep unresolved findings open.
"""


def ensure_pr(client, data, receipt, base):
    query = urlencode({'state': 'all', 'head': data['repository'].split('/')[0] + ':' +
                       data['branch'], 'base': base, 'per_page': 100})
    existing = client.api('pulls?' + query, paginate=True)
    key = f"<!-- osms-audit-pr:{data['audit_id']} -->"
    ours = [p for p in existing if key in (p.get('body') or '')]
    if len(ours) > 1 or (existing and len(ours) != len(existing)):
        raise ValueError('Existing PR needs manual reconciliation; no PR was overwritten')
    if ours:
        print(f"Existing PR preserved ({ours[0]['state']}): {ours[0]['html_url']}")
        return ours[0]
    return client.api('pulls', {'title': 'OSMS audit remediation and structured finding tracking',
        'head': data['branch'], 'base': base, 'draft': True, 'body': pr_body(data, receipt)})


def git(args, cwd=None):
    # Per-command helper only: no global config mutation and no token extraction.
    return run(['git', '-c', 'credential.helper=', '-c',
                'credential.helper=!gh auth git-credential', *args], cwd=cwd)


def publish_bundle(data, package):
    metadata = read_json(package / 'handoff.json')
    bundle = package / 'OSMS.bundle'
    if hashlib.sha256(bundle.read_bytes()).hexdigest() != metadata['bundle_sha256']:
        raise ValueError('Bundle checksum mismatch')
    head = metadata['head_commit']
    if not SHA.fullmatch(head) or metadata['branch'] != data['branch']:
        raise ValueError('Unexpected bundle head or branch')
    worktree = package / 'publish-worktree'
    remote = f"https://github.com/{data['repository']}.git"
    if not worktree.exists():
        git(['clone', '--no-checkout', remote, str(worktree)])
        # The dedicated clone is owned by this importer, never an existing user checkout.
        (worktree / '.git' / 'osms-import-owner').write_text(data['audit_id'], encoding='utf-8')
    ownership = worktree / '.git' / 'osms-import-owner'
    if not ownership.exists() or ownership.read_text(encoding='utf-8') != data['audit_id']:
        raise ValueError('publish-worktree is not owned by this importer; choose a fresh package directory')
    if git(['remote', 'get-url', 'origin'], worktree) != remote:
        raise ValueError('Unexpected remote in dedicated publishing clone')
    # A no-checkout clone initially reports deletions; checkout only on first import.
    initialized = worktree / '.git' / 'osms-import-initialized'
    if initialized.exists() and git(['status', '--porcelain'], worktree):
        raise ValueError('Publishing clone contains local edits; preserve them before proceeding')
    git(['bundle', 'verify', str(bundle)], worktree)
    heads = git(['bundle', 'list-heads', str(bundle)], worktree).splitlines()
    if f"{head} refs/heads/{data['branch']}" not in heads:
        raise ValueError('Declared head is absent from bundle')
    git(['fetch', str(bundle), f"refs/heads/{data['branch']}"], worktree)
    git(['merge-base', '--is-ancestor', data['remediation_commit'], head], worktree)
    git(['checkout', '--detach', head], worktree)
    initialized.write_text(head, encoding='utf-8')
    remote_refs = git(['ls-remote', '--heads', 'origin', f"refs/heads/{data['branch']}"], worktree)
    if remote_refs:
        remote_head = remote_refs.split()[0]
        if remote_head == head:
            print('Branch already published; preserving it.')
            return head
        git(['fetch', 'origin', data['branch']], worktree)
        # Refuse to overwrite any divergent or newer branch; never force-push.
        git(['merge-base', '--is-ancestor', remote_head, head], worktree)
    git(['push', 'origin', f"{head}:refs/heads/{data['branch']}"], worktree)
    return head


def apply(data, package, issues_only=False):
    for executable in ('gh', 'git'):
        if not shutil.which(executable):
            raise RuntimeError(f'Install {executable} first; see ANLEITUNG.md')
    client = GitHub(data['repository'])
    repo = client.api('')
    if repo.get('archived') or not repo.get('has_issues') or not repo.get('permissions', {}).get('push'):
        raise ValueError('Repository must be writable, unarchived and have Issues enabled')
    index_issues(data, client.issues())  # Reconcile before any remote writes.
    if not issues_only:
        publish_bundle(data, package)
    # All commit links must be resolvable on GitHub before issues are created.
    for sha in {data['base_commit'], data['remediation_commit'],
                *(r['sha'] for f in data['findings'] for r in f['commit_references'])}:
        if client.api(f'commits/{sha}')['sha'] != sha:
            raise ValueError(f'Remote commit cannot be verified: {sha}')
    ensure_labels(client, data)
    receipt_path = package / 'github-import-result.json'
    receipt = sync_issues(client, data, receipt_path)
    if not issues_only:
        pr = ensure_pr(client, data, receipt, repo['default_branch'])
        receipt['pull_request'] = {'number': pr['number'], 'url': pr['html_url'], 'state': pr['state']}
        write_json(receipt_path, receipt)
        print(f"Draft PR (or preserved existing PR): {pr['html_url']}")
    print(f'Receipt: {receipt_path}')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    default = Path(__file__).resolve().parent
    if default.name == 'tools':
        default = default.parent
    parser.add_argument('--package-dir', type=Path, default=default)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--dry-run', action='store_true', help='Local preview only (default)')
    mode.add_argument('--apply', action='store_true', help='Publish branch, missing issues/labels and draft PR')
    parser.add_argument('--issues-only', action='store_true', help='With --apply, import only after commits are published')
    args = parser.parse_args(argv)
    package = args.package_dir.resolve()
    data = read_json(package / 'review' / 'github-findings.json')
    validate_manifest(data)
    preview(data, package / 'issue-preview')
    if not args.apply:
        print('No network request or GitHub write was made. Use --apply to publish.')
        return 0
    lock = package / 'github-import.lock'
    # Prevent accidental simultaneous local runs. After a hard kill, inspect the
    # receipt and GitHub state before removing this lock. GitHub has no atomic
    # uniqueness constraint for audit IDs: do not run from two machines at once.
    try:
        lock.touch(exist_ok=False)
    except FileExistsError as exc:
        raise RuntimeError('Import lock exists; confirm no other import is running') from exc
    try:
        apply(data, package, args.issues_only)
    finally:
        lock.unlink()
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, RuntimeError, KeyError, OSError) as error:
        print(f'STOP: {error}', file=sys.stderr)
        print('Completed steps remain intact. Resolve the cause and rerun; existing markers are reused.', file=sys.stderr)
        sys.exit(1)
