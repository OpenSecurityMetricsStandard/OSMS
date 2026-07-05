<!-- Paste this section into REVIEW_PROCESS.md -->

## Review KPIs — we measure our own review

OSMS is a metrics standard, so its public review is itself governed by OSMS-style
metrics: each KPI has a formula, a source, thresholds and a triggered decision.
Numbers are published weekly in the "Review Status" discussion and become part of
the public Review Board Summary at freeze.

**Review window:** 6 July – 15 August 2026 (40 days) · **Checkpoint 1:** 25 July ·
**Checkpoint 2:** 22 August · **Freeze target:** 30 August 2026

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

**Go/no-go rule:** if K-01, K-02 and K-09 miss their thresholds at Checkpoint 2,
the review is extended and the freeze date moves. OSMS 1.0 will not be frozen on
schedule against its own evidence.

**How findings are counted:** open a
[Review Finding issue](../../issues/new/choose) (category and severity are
mandatory dropdowns) or use the review form / review@opensecuritymetrics.org for
non-GitHub submissions. Triage adds `cat:*` and `severity:*` labels within five
working days; Review Board decisions add `decision:*` labels. The weekly numbers
are produced by `tools/review_kpis.py`.
