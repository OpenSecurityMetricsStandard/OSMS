# SPDX-License-Identifier: MIT
"""Contract tests: retry safety, evidence semantics and no implicit decisions."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('github_review_import', ROOT / 'tools/github_review_import.py')
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class FakeGitHub:
    def __init__(self):
        self.records = []
        self.writes = []
        self.fail_after_creation = None
        self.label_records = []
        self.prs = []

    def issues(self):
        return copy.deepcopy(self.records)

    def api(self, path, payload=None, paginate=False):
        if payload is None:
            if path.startswith('labels?'):
                return copy.deepcopy(self.label_records)
            if path.startswith('pulls?'):
                return copy.deepcopy(self.prs)
            raise AssertionError(path)
        self.writes.append((path, copy.deepcopy(payload)))
        if path == 'labels':
            self.label_records.append(copy.deepcopy(payload))
            return payload
        if path == 'pulls':
            record = {**payload, 'number': 200, 'state': 'open', 'html_url': 'https://example.invalid/pr/200'}
            self.prs.append(record)
            return record
        if path != 'issues':
            raise AssertionError('Unexpected mutation: ' + path)
        number = len(self.records) + 40
        record = {**payload, 'number': number, 'state': 'open',
                  'html_url': f'https://example.invalid/issues/{number}'}
        self.records.append(record)
        if self.fail_after_creation == len(self.records):
            raise RuntimeError('Simulated response loss after successful creation')
        return copy.deepcopy(record)


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.data = M.read_json(ROOT / 'review/github-findings.json')
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)
        self.client = FakeGitHub()

    def tearDown(self):
        self.temp.cleanup()

    def test_manifest_matches_catalog_ids_and_fix_status(self):
        M.validate_manifest(self.data)
        import yaml
        catalog = yaml.safe_load((ROOT / 'catalog/osms-catalog.yaml').read_text(encoding='utf-8'))
        cards = catalog if isinstance(catalog, list) else catalog['cards']
        self.assertEqual(set(self.data['known_card_ids']), {c['id'] for c in cards})
        candidates = {f['id'] for f in self.data['findings'] if f['fix_commit']}
        self.assertEqual(candidates, {'F-05', 'F-08', 'F-16'})

    def test_reject_unknown_card_duplicate_id_and_false_fix(self):
        for mutation in ('card', 'duplicate', 'fix', 'decision'):
            data = copy.deepcopy(self.data)
            if mutation == 'card':
                data['findings'][0]['cards'].append('OSMS-XX-000')
            elif mutation == 'duplicate':
                data['findings'][1]['id'] = 'F-01'
            elif mutation == 'fix':
                data['findings'][0]['fix_commit'] = data['remediation_commit']
            else:
                data['findings'][0]['review_decision'] = 'accepted'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                M.validate_manifest(data)

    def test_second_run_preserves_closed_issue_and_human_edits(self):
        with patch('builtins.print'):
            first = M.sync_issues(self.client, self.data, self.path / 'receipt.json')
            self.client.records[0]['state'] = 'closed'
            self.client.records[0]['body'] += '\nHuman verification: retained.'
            self.client.records[0]['labels'].append('decision:accepted')
            before = copy.deepcopy(self.client.records)
            second = M.sync_issues(self.client, self.data, self.path / 'receipt.json')
        self.assertEqual(len(self.client.writes), 32)
        self.assertEqual(self.client.records, before)
        self.assertEqual(first['issues']['F-01']['number'], 40)
        self.assertEqual(second['issues']['F-01']['state'], 'closed')
        self.assertEqual(second['issues']['F-32']['action'], 'reused')

    def test_lost_response_resumes_without_duplicate_issue(self):
        self.client.fail_after_creation = 9
        with patch('builtins.print'):
            with self.assertRaises(RuntimeError):
                M.sync_issues(self.client, self.data, self.path / 'receipt.json')
            self.client.fail_after_creation = None
            result = M.sync_issues(self.client, self.data, self.path / 'receipt.json')
        self.assertEqual(len(self.client.records), 32)
        self.assertEqual(len(self.client.writes), 32)
        self.assertEqual(result['issues']['F-09']['action'], 'reused')

    def test_ambiguous_markers_or_manual_title_block_creation(self):
        f = self.data['findings'][0]
        record = {'number': 40, 'title': M.issue_title(f), 'body': M.render_issue(self.data, f)}
        for records in ([record, {**record, 'number': 41}],
                        [{**record, 'body': 'Manually filed finding'}]):
            with self.subTest(records=len(records)), self.assertRaises(ValueError):
                M.index_issues(self.data, records)

    def test_labels_are_unique_and_existing_definitions_preserved(self):
        for f in self.data['findings']:
            labels = M.issue_labels(f)
            self.assertEqual(sum(x.startswith('cat:') for x in labels), 1)
            self.assertEqual(sum(x.startswith('severity:') for x in labels), 1)
            self.assertFalse(any(x.startswith('decision:') for x in labels))
        existing = {'name': 'severity:critical', 'color': '111111', 'description': 'Maintainer definition'}
        self.client.label_records = [existing.copy()]
        M.ensure_labels(self.client, self.data)
        count = len(self.client.writes)
        M.ensure_labels(self.client, self.data)
        self.assertEqual(len(self.client.writes), count)
        self.assertEqual(self.client.label_records[0], existing)

    def test_pr_is_draft_without_closing_keywords_and_reused(self):
        with patch('builtins.print'):
            receipt = M.sync_issues(self.client, self.data, self.path / 'receipt.json')
            pr = M.ensure_pr(self.client, self.data, receipt, 'main')
            M.ensure_pr(self.client, self.data, receipt, 'main')
        self.assertTrue(pr['draft'])
        self.assertNotRegex(pr['body'], r'(?i)\b(close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#\d+')
        self.assertEqual(sum(path == 'pulls' for path, _ in self.client.writes), 1)
        self.assertIn('| F-32 | #71 |', pr['body'])

    def test_cross_repo_website_commit_is_not_invented(self):
        f = next(f for f in self.data['findings'] if f['id'] == 'F-28')
        self.assertIsNone(f['website_fix_commit'])
        self.assertIsNone(f['fix_commit'])
        text = M.render_issue(self.data, f)
        self.assertIn('Claude', text)
        self.assertIn('Teilfix', text)
        self.assertIn('47 Kartenfelder', text)

    def test_api_pagination_and_json_preserve_unicode_newlines(self):
        client = M.GitHub(self.data['repository'])
        with patch.object(M, 'run', return_value='[[{"number":1}],[{"number":2}]]') as runner:
            self.assertEqual([i['number'] for i in client.api('issues', paginate=True)], [1, 2])
            self.assertIn('--paginate', runner.call_args.args[0])
        with patch.object(M, 'run', return_value='{}') as runner:
            payload = {'body': 'Prüfung\n`literal` $(never a shell command)'}
            client.api('issues', payload)
            self.assertEqual(json.loads(runner.call_args.kwargs['stdin']), payload)

    def test_default_preview_needs_no_git_gh_or_network(self):
        (self.path / 'review').mkdir()
        M.write_json(self.path / 'review/github-findings.json', self.data)
        with patch.object(M, 'run', side_effect=AssertionError('Network/process prohibited')):
            with patch('builtins.print'):
                self.assertEqual(M.main(['--package-dir', str(self.path)]), 0)
        self.assertEqual(len(list((self.path / 'issue-preview').glob('F-*.md'))), 32)


if __name__ == '__main__':
    unittest.main()
