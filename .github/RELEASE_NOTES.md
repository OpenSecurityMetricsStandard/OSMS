OSMS 0.9.2 is a public maintainer draft with corrections to the 0.9.1 audit baseline.
The maintainer may develop and publish 0.x releases before the Review Board starts.
Formal board review will use a separately named baseline and timetable.

- 327 metric cards; all 47 card fields remain available in the generated export.
- Corrected detection-period selection, median/P90, validated mitigation, composite
  input checks, penalty identity checks and database Green/confidence constraints.
- Seven changed card definitions use card version 0.9.2; unchanged cards retain
  card version 0.9.1. All cards identify the containing OSMS version as 0.9.2.
- Six explicit threshold profiles resolve gaps, overlaps and boundary precedence.
- Unimplemented recipe templates return an explicit mapping-required result.
- Findings retain category, severity, card IDs, fix commits and verification evidence.

Migration: supply nullable `mitigated_at` and a current period-end validation status
for STD-016; migrate existing reference databases and consumers of recipe/status
values. Schema identifier: `https://opensecuritymetrics.org/schema/0.9.2/osms-card.schema.json`.
The schema is included in this source release; that identifier does not establish
that the website endpoint has been deployed. Website integration remains F-28.

Validation covers structural checks on 327 cards, targeted regressions and numeric
fixtures for eight cards. Full mathematical conformance of all cards, confidence
production, normalization and risk profiles remain open work. This release does
not claim Board approval or ISO conformity.

See `review/RELEASE_0.9.2.md`, `review/REMEDIATION.md` and the linked GitHub findings
for detailed changes, verification scope and remaining work.

Download verification: put `SHA256SUMS.txt` next to the ZIP and run
`sha256sum -c SHA256SUMS.txt`. `MANIFEST-SHA256.txt` covers every included tracked
source file. The archive includes catalog, schema, code, tests and review records.

Specification and catalog: CC BY 4.0; code: MIT. See LICENSE, LICENSE-CODE and NOTICE.
