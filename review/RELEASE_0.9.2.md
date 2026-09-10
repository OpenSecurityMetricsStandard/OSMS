# OSMS 0.9.2 — maintainer draft

Prepared on 2026-09-10 under the maintainer's instruction to continue correcting
and improving OSMS before the Review Board starts. Responsible maintainer:
Nico Wiegand. Technical verification: Codex, automated checks and source inspection;
no personal manual test or independent board vote is attributed to the maintainer.

The 0.x development authority is defined in [REVIEW_PROCESS.md](../REVIEW_PROCESS.md).
This version may be merged and published without a Review Board vote. The catalog
retains `release_phase: working_draft` and `board_approved: false`; `v0.9.2` is a
valid tag. The release workflow publishes it as a public GitHub prerelease.
The repository version identifies prepared source; the GitHub release page is the
publication record. Preparation or a merge alone is not publication of a release.

## Changes and migration

The baseline is published OSMS 0.9.1, commit
`747cd28fb0b6728ebadbe6c477722d166b5b40b5`. The substantive correction is
`06fa2b5d837602cdba89d07dafba1f027d76b1a2`; the SPL fixture adapter correction is
`bd8fc0314a21ffa9e3228f79dbdac8562db4ab70`. Their history is preserved by the PR
merge rather than a squash. PR [#2](https://github.com/OpenSecurityMetricsStandard/OSMS/pull/2)
records subsequent release-preparation and merge commits.

The containing catalog and all card `osms_version` fields identify 0.9.2.
Only the seven changed definitions advance `card_version` to 0.9.2:
STD-005, STD-012, STD-015, STD-016, STD-019, STD-055 and SOC-063.
The other 320 definitions retain card version 0.9.1. The unchanged principles and
card taxonomy keep their independent component version 0.9.1. Recipe metadata,
reference seed rows and the readiness catalog reference follow the containing
catalog version. Generated metadata derives that version instead of hard-coding it.

The six boundary choices in [METHOD_DECISIONS.md](METHOD_DECISIONS.md) are adopted
for this maintainer draft and remain open to later versioned improvements.
STD-016 requires the nullable `mitigated_at` input and current validation at the
period-end snapshot. Reopened treatments with revoked validation cannot count as
success. Existing loaders/databases require the migrations described in
[CONTRACTS.md](../recipes/CONTRACTS.md).

The schema URI identifies 0.9.2. Its bytes are in `schema/osms-card.schema.json`;
website availability is not inferred from the URI. The website work is handled externally and remains
tracked separately as [F-28 / #29](https://github.com/OpenSecurityMetricsStandard/OSMS/issues/29).

## Finding dispositions

The following findings meet the stated repository acceptance criteria and are
accepted for this maintainer draft. GitHub records actual closure and the exact
verified commit after the final CI checks; it is the current lifecycle record.

| Finding | GitHub issue | Disposition and evidence |
|---|---|---|
| F-05 | [#6](https://github.com/OpenSecurityMetricsStandard/OSMS/issues/6) | Verified: timely remediation/mitigation, late and missing dates, unvalidated and reopened cases; Python and both SQL dialect snippets on DuckDB; targeted spreadsheet cases and positive live-engine fixtures. Existing installation migration and exhaustive engine conformance remain distinct implementation work. |
| F-08 | [#9](https://github.com/OpenSecurityMetricsStandard/OSMS/issues/9) | Verified: unknown confidence, n/a, provisional validity and negative denominators are rejected; exact operational 69.99/70 and board-reporting 84.99/85 boundaries are exercised against the reference database. |
| F-18 | [#19](https://github.com/OpenSecurityMetricsStandard/OSMS/issues/19) | Maintainer choices adopted for all six affected cards; disjoint threshold branches, critical overrides, zero baselines and unknown confidence have executable boundary regressions. |

F-16 / [#17](https://github.com/OpenSecurityMetricsStandard/OSMS/issues/17) has a
verified fix for unsafe unchanged skeletons. Its broader acceptance criterion also
requires complete period/mapping validation for concrete recipes; that part remains
open with F-04/F-07/F-20. Its open state is due to that work, not lack of a board.
The other findings retain their stated remaining criteria. No blanket closure,
risk acceptance or `decision:*` board labels are created by this release.

The original `review/github-findings.json` and first section of `VALIDATION.md`
are preserved as audit/import snapshots. Current dispositions live in GitHub and
`REMEDIATION.json`; they do not rewrite the original defect observations.

## Verification scope

Run the pinned Python 3.12 regression suite, full catalog/schema/export checks,
formula audit, reference demo, readiness gate and recipe gates on the release
source. PR checks record the exact head and results. The previous correction head
`bd8fc0314a21ffa9e3228f79dbdac8562db4ab70` passed both
[Catalog CI](https://github.com/OpenSecurityMetricsStandard/OSMS/actions/runs/34468512947)
and [Recipe CI](https://github.com/OpenSecurityMetricsStandard/OSMS/actions/runs/34468513016),
including Splunk 9.4/10.2, Elasticsearch 8.17.4 and LibreOffice jobs. These historical
runs are not substituted for checking the new 0.9.2 commit.

The numeric fixture set covers eight of 327 cards. Empty/blocked checks cover 277
snippets per applicable dialect. KQL analysis is not native Kusto execution;
PostgreSQL-flavored snippets on DuckDB are not PostgreSQL runtime certification.
Unknown confidence production, comprehensive normalization/risk profiles, full
per-card/per-output conformance, transitive locks and website deployment remain
open. Four catalog warnings remain visible; see [VALIDATION.md](VALIDATION.md).

## Publication

After the tested source is on main, create tag `v0.9.2` on that exact commit and
publish a prerelease titled "OSMS v0.9.2 - Maintainer draft" with
`.github/RELEASE_NOTES.md`. A tag push or a GitHub `release.published` event runs
the release validation and attaches the source ZIP and both checksum manifests.
Stable 1.0 promotion remains a separate future governance decision. No old tag or
published 0.9.1 asset is replaced.
