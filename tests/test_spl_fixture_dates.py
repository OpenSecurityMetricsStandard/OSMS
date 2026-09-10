# SPDX-License-Identifier: MIT
import unittest
from recipes.ci.spl_fixture import rows_for_spl


class SplFixtureDateTests(unittest.TestCase):
    def test_missing_treatment_dates_stay_absent(self):
        fixture = {'fields': {'resolved_at': 'date', 'mitigated_at': 'date'},
                   'rows': [{'resolved_at': None, 'mitigated_at': None,
                             'mitigation_validated': False, 'id': 'untreated'}]}
        self.assertEqual(rows_for_spl(fixture),
                         [{'mitigation_validated': False, 'id': 'untreated'}])
        self.assertIn('resolved_at', fixture['rows'][0])

    def test_valid_mitigation_keeps_exact_utc_timestamp(self):
        fixture = {'fields': {'resolved_at': 'date', 'mitigated_at': 'date'},
                   'rows': [{'resolved_at': None, 'mitigated_at': '1970-01-02T00:00:00Z',
                             'mitigation_validated': True}]}
        self.assertEqual(rows_for_spl(fixture),
                         [{'mitigated_at': 86400, 'mitigation_validated': True}])

    def test_non_null_invalid_date_is_rejected(self):
        for invalid in ('not-a-date', '', '2026-02-30T00:00:00Z'):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                rows_for_spl({'fields': {'mitigated_at': 'date'},
                              'rows': [{'mitigated_at': invalid}]})


if __name__ == '__main__':
    unittest.main()
