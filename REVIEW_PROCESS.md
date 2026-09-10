# Review Process

OSMS 0.9.x is in public review. Anyone can submit findings - no GitHub
account required.

**How to submit:** open a
[Review Finding issue](https://github.com/OpenSecurityMetricsStandard/OSMS/issues/new/choose)
(category and severity are mandatory dropdowns), or send your finding to
<review@opensecuritymetrics.org>. Triage adds category and severity labels
within five working days; Review Board decisions are recorded as
`decision:*` labels on the issue.

## Maintainer development before formal board review

While the Review Board is being assembled, the maintainer may correct the
standard, adopt documented method choices for a 0.x draft, merge verified changes,
close resolved findings and publish new 0.x versions. None of these actions
requires a Review Board vote. A plain version tag such as `v0.9.2` is permitted;
the catalog keeps its explicit draft phase and the GitHub release is a public
prerelease titled "Maintainer draft". A published draft is available to readers;
it is not an unpublished GitHub release draft.

Close a finding when its acceptance criteria are met and its fix commit, test
evidence, verifier, responsible maintainer, date and disposition are recorded.
Automated verification must be identified as such. Use `status:verified` and
`maintainer:accepted` for that disposition. Keep `decision:*` for the later formal
board process so maintainer closure does not inflate the board decision KPI.
Incomplete criteria remain open with specific remaining work; the absence of a
board is not itself a technical blocker.

At formal review start, identify an immutable candidate version and commit, then
adopt the charter, timetable and review gates. Subsequent changes remain possible
with versioned change records. The board/quorum/freeze gates below concern that
formal process and stable 1.0 promotion, not ordinary 0.x development releases.

## Review KPIs — we measure our own review

OSMS is a metrics standard, so its public review is itself governed by OSMS-style
metrics: each KPI has a formula, a source, thresholds and a triggered decision.
Numbers are published weekly in the "Review Status" discussion and become part of
the public Review Board Summary at freeze.

**Schedule status:** the July/August 2026 dates below are the historical plan.
The board is being assembled; adopt a new candidate baseline and timetable before
formal board review. No completed review or approval is implied.

| # | KPI | Formula / source | CP1 (25 Jul) | CP2 (22 Aug) | Freeze target | Triggered decision |
|---|---|---|---|---|---|---|
| K-01 | Active external reviewers | Distinct persons with ≥1 finding or comment (GitHub + review form) | ≥ 4 | ≥ 8 | ≥ 10 | Below threshold → targeted outreach wave / extend review |
| K-02 | Findings total | Count of finding issues + form submissions (cumulative) | ≥ 10 | ≥ 25 | ≥ 40 | Too few → assign targeted card-review tasks |
| K-03 | Findings by category | Distribution across the 12 categories (labels) | monitor | monitor | — | Cluster → focused Review Board session |
| K-04 | Card coverage, P0 cards | % of P0 cards with ≥1 external review touch | — | ≥ 60 % | 100 % | Gaps → assign cards to board members |
| K-05 | Card coverage, overall | % of all 327 cards with ≥1 touch | — | ≥ 15 % | ≥ 30 % | Same; focus on the 137 truth-layer/steering cards |
| K-06 | Median triage time | Submission → category + severity label set | ≤ 5 wd | ≤ 5 wd | ≤ 5 wd | Exceeded → increase weekly triage slot |
| K-07 | Decision rate | % of findings with accepted / rejected / deferred / accepted-risk | — | ≥ 50 % | 100 % crit+major, ≥ 90 % overall | Open items → postpone freeze |
| K-08 | Open critical findings | Count of open findings labelled severity:critical | — | — | **0** | > 0 → freeze blocker |
| K-09 | Review Board quorum | Sessions held / active members | charter live | ≥ 3 active | ≥ 1 session, ≥ 3 active | Quorum missed → postpone freeze |

**Candidate gate clarification:** the board must adopt the final gate combination.
The previous AND wording is unresolved and must not be used as automatic approval.
Proposed rule: each mandatory gate must pass; missing evidence remains unresolved.
A calendar target cannot override missing review evidence.

**How findings are counted:** open a
[Review Finding issue](https://github.com/OpenSecurityMetricsStandard/OSMS/issues/new/choose) (category and severity are
mandatory dropdowns) or use the review form / review@opensecuritymetrics.org for
non-GitHub submissions. Triage adds `cat:*` and `severity:*` labels within five
working days; Review Board decisions add `decision:*` labels. The weekly numbers
are produced by `tools/review_kpis.py`.

Measurement implementation and limitations: [Review KPI method 0.2](review/REVIEW_KPI_METHOD.md).
