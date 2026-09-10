# GitHub audit finding import

The versioned source of the 32 audit records is `review/github-findings.json`.
`tools/github_review_import.py` renders their issue bodies and imports them through
GitHub CLI. The handoff package includes the same executable script, a Git bundle
and a checksum/head manifest, so the original remediation commit is preserved.

## Published commit identity

The direct GitHub connector creates new commit metadata. The published remediation
commit is `06fa2b5d837602cdba89d07dafba1f027d76b1a2`; its entire Git tree
`c89de48f3240053ecd869c1e56c79c1f335af4ca` is byte-identical to the reviewed local
commit `828621e44864fd76fbbf195d50d8b7ccfb795d0c`. Issue evidence uses
the published SHA. The original handoff ZIP/bundle predates this publication and
must not be applied to overwrite the published audit branch. For provenance, see
`review/PUBLICATION.json`.

## Record contract

| Field | Meaning |
|---|---|
| Audit ID + Finding ID | `2026-09-10 / F-01`; independent of the GitHub issue number |
| Category | Exactly one existing `cat:*` label; same vocabulary as the issue form |
| Severity | Exactly one `severity:*` label; proposed translation: Hoch → critical, Mittel → major, Niedrig → minor |
| Original audit severity | Preserved separately; priority translation requires maintainer triage, not a board vote |
| Card ID(s) | Exact IDs from the 327-card inventory; empty for cross-cutting findings |
| Audited baseline | Immutable original commit and file links |
| Implementation status | Open, partial, proposal pending decision, or implemented pending verification |
| Fix commit(s) | Full SHA with a role: candidate fix, partial fix, proposal or context only |
| Acceptance and verification | Observable criteria, tested commit, environment, result and verifier |
| Review disposition | Separate authorized decision, rationale, person and date |

F-05, F-08 and F-16 have an implementation candidate at
`06fa2b5d837602cdba89d07dafba1f027d76b1a2`; their initial import status was open pending verification.
Live GitHub dispositions and `review/RELEASE_0.9.2.md` record subsequent verification.
The import JSON and original validation log are historical snapshots, not a
requirement to keep a verified issue open or wait for the Review Board.
Other code changes are partial fixes or proposals. Documentation of an unresolved
method/governance question is explicitly marked as context rather than a fix.
No `decision:*` label is assigned by the importer.

F-28 records that website implementation is handled externally.
The repository export/schema is a partial fix. Add the actual website commit URL,
47-field comparison and deployment evidence when available; if the frontend lives
in another repository, use a full cross-repository URL.

## Preview and import

Python 3.10+ is sufficient for the importer; no Python packages are required.
The numerical OSMS validation environment remains Python 3.12 with pinned check
dependencies. Publishing needs Git, GitHub CLI and an authenticated account with
write access to the repository, Issues and pull requests. The token must permit
the included workflow-file changes; authentication is handled by GitHub CLI.

From the repository, render without any network access:

```bash
python tools/github_review_import.py --dry-run
```

From the extracted handoff package:

```bash
python OSMS_GitHub_Import.py --dry-run
python OSMS_GitHub_Import.py --apply
```

The apply command creates a dedicated `publish-worktree` clone, verifies the
bundle, publishes `audit/remediation-2026-09-10`, checks all linked commits on
GitHub, creates missing labels, imports missing issues and creates one draft PR
against the repository's current default branch. It writes the actual
`F-ID → issue number/URL` mapping and PR URL to `github-import-result.json`.
It does not merge or release the draft, overwrite an existing checkout, force-push,
close issues, update existing label definitions or overwrite human issue edits.

If the exact commits have already been published, the repository tool can import
issues alone with `--apply --issues-only`. That mode does not create a branch or PR.

## Repeatability and recovery

Issue identity is the hidden body marker
`<!-- osms-audit:2026-09-10:F-01 -->`, not the title or the GitHub issue number.
All issue pages and states are read; pull requests are excluded. A second run
reuses matching issues, including closed ones, without changing their content,
labels or state. A changed local record does **not** overwrite an existing issue;
maintain live issues intentionally after import.

A lost response after creation stops the command without retrying the POST. On
the next run the issue is found by its marker. Completed steps remain in place.
Duplicate markers or matching titles without a marker stop the import: reconcile
the existing issue and add the exact marker to the intended record before retrying.
Do not run two imports from separate machines at the same time: GitHub does not
provide an atomic uniqueness constraint for audit IDs. A local lock prevents
simultaneous invocations in one package directory. After a hard kill, confirm the
previous process has ended and inspect GitHub before removing a stale lock file.

A divergent/newer remote audit branch is preserved and the script stops. Reconcile
that branch manually; do not use force-push as a recovery step. A failed initial
clone may leave a partial `publish-worktree`; keep it for inspection and retry from
a fresh extracted package directory. A branch-rule or credential rejection also
stops the command; use an authorized account or the repository's normal PR process.

The PR references issues without closing keywords. Merge alone does not establish
that every acceptance criterion is met. Prefer a merge commit when preserving
the cited SHA matters; after squash/rebase, record the resulting commit as well.
The new issue form becomes the default only once its branch has been merged.

## Triage and review metrics

The importer sets category/severity labels explicitly. GitHub issue-form dropdown
answers do not themselves apply those dynamic labels. For later manually submitted
findings, maintainers must apply the corresponding labels and remove `triage`
when reviewed. No automatic labeling workflow is added here.

These 32 imported audit records are input to the review, not 32 independent board
reviews. `tools/review_kpis.py` counts GitHub authors/comments, so exclude the
importing account where appropriate (`--exclude ACTUAL_LOGIN`) when reporting
external participation. This also excludes that account's other contributions;
it is not a per-issue provenance model. Do not infer board membership or votes
from imported issue activity. The importer does not prefill board assignments,
reviewer identities, charter decisions or a milestone deadline.

## Validation of the importer

Ten local contract tests cover the exact catalog IDs, invalid records and false
fix claims, a second import preserving human edits/closed issues, resumption after
a successful write with a lost response, duplicate detection, label preservation,
draft PR references without auto-closing, F-28 ownership/evidence, paginated JSON
transport and a default preview without network/process access.

```bash
python -m unittest discover -s tests -p test_github_review_import.py -v
```

These tests simulate GitHub responses. They do not establish that an authenticated
live import has run or that GitHub permissions/CI/branch rules will accept it.
The existing remediation validation record is `review/VALIDATION.md`.
The combined local suite passed on 2026-09-10: 42 tests (32 remediation tests and
10 import tests). Existing file-handle ResourceWarnings in the formula audit were
visible; they did not fail the run.

GitHub reference: [Linking a pull request to an issue](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/linking-a-pull-request-to-an-issue),
[GitHub CLI API pagination and JSON input](https://cli.github.com/manual/gh_api).
