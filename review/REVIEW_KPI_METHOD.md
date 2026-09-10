# Review KPI calculation method 0.2

`tools/review_kpis.py` is read-only. It outputs JSON or Markdown and does not post
messages. GitHub issue, comment and event pagination is complete; PR records are
excluded. API failures stop collection instead of silently returning partial totals.

```bash
python tools/review_kpis.py --repo OpenSecurityMetricsStandard/OSMS \
  --exclude YOUR_MAINTAINER_LOGIN --save-snapshot review-snapshot.json --markdown
python tools/review_kpis.py --snapshot review-snapshot.json --exclude YOUR_MAINTAINER_LOGIN
```

The snapshot shape is `{ "issues": [...], "comments_complete": true,
"events_complete": true, "snapshot_at": "ISO-8601" }`. Issues retain the GitHub
REST fields plus `comments_data` and `events`. Preserve the snapshot hash and code
version with published numbers. Different GitHub accounts may belong to one person;
resolve aliases before interpreting distinct accounts as distinct persons. Exclude
maintainers explicitly. Bots are excluded automatically. Imported non-GitHub records
need deduplication and author identity mapping; raw manual totals are rejected because
they cannot establish decisions, coverage or complete denominators.

- K-01 counts external finding authors and commenters. Comments inherit the card
  references of their finding; a touch is evidence of participation, not substantive
  technical approval. The tool covers finding issues, not every project discussion.
- K-03 requires one recognized category label. Unknown/conflicting labels are
  reported as limitations. K-04/05 use catalog IDs (including helper suffixes),
  external participation and the actual catalog/P0 denominators.
- K-06 ends at the first event where exactly one recognized category and severity
  are simultaneously present. Unlabel events are respected. The calendar is UTC,
  Monday–Friday, 24 elapsed hours per weekday; repeat `--holiday YYYY-MM-DD` for
  nonworking dates. This explicit convention is not an office-hours model. Missing
  event history gives unavailable; untriaged issues are shown separately from the
  median and must not disappear from the operational assessment.
- K-07 only accepts one of accepted/rejected/deferred/accepted-risk. Pending,
  breaking, unknown and conflicting decisions do not count. K-08 remains open
  critical findings; incomplete severity labels prevent an unconditional freeze claim.
- K-09 is unavailable until an explicit board record is supplied through `--board`.
  That JSON contains `charter_ref`, `members` (`id`, `active`, `evidence_ref`) and
  `sessions` (`id`, `status`, `evidence_ref`). Count distinct active members and held
  sessions with evidence. A count is not an approval or a validation of quorum rules.
  Empty charter references, ambiguous identities/statuses and missing evidence for
  counted memberships or sessions reject the supplied Board dataset.

The tool deliberately does not calculate an automatic overall go/no-go. The board
charter, completeness of sources and the final gate combination remain decisions
for the published review process.
