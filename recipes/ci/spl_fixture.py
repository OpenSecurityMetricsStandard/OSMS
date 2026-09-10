# SPDX-License-Identifier: MIT
"""Convert fixture dates for Splunk without inventing treatment timestamps."""
import datetime as dt


def epoch(iso):
    return int(dt.datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ")
               .replace(tzinfo=dt.timezone.utc).timestamp())


def rows_for_spl(fixture):
    """Omit absent dates from HEC indexed fields; preserve valid UTC dates.

    A missing resolved_at or mitigated_at must remain absent, not become epoch
    zero and appear to prove timely treatment. Malformed non-null dates still
    fail validation. Other field values retain their existing representation.
    """
    out = []
    for source in fixture['rows']:
        row = {}
        for key, value in source.items():
            if fixture['fields'].get(key) == 'date':
                if value is None:
                    continue
                value = epoch(value)
            row[key] = value
        out.append(row)
    return out
