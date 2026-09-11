# Pre-board hardening candidate

This candidate retains the eight existing dialects. All 327 cards have an explicit
calculation profile: 207 canonical quotients, 119 prepared-observation profiles and
SOC-003's incident snapshot. Production source adapters and empirical validity are
separate from arithmetic implementation.

## Review material

Run `python recipes/gen_recipes.py --emit-candidates --out recipes/out`, collect
matching reports with `recipes/ci/collect_profile_reports.py`, then run
`python tools/build_board_packet.py`. The Recipe CI evidence job also performs
these steps and publishes `preboard-review-packet`.

The packet contains 327 individual card dossiers, a review matrix, all 1,149 mapping
associations with card-specific context, and a SHA-256 manifest. It includes every
output's contract, independent examples, exact runtime evidence when available,
and concrete questions about populations, gates and decision relevance. A generated
dossier or structural check does not count as an independent semantic review.
Reviewer and decision fields remain empty until the work takes place.

## Changes and regression protection

- Added 111 independently specified companion output oracles. Missing result keys
  now fail even when the expected value is null. Integer competition ranks require
  exact equality. SPL's text transport explicitly encodes null as `__OSMS_NULL__`;
  clients decode that marker as null. Arithmetic and threshold evaluation precede
  that transport conversion.
- `tools/preboard_mutations.py` introduces 837 in-memory faults in actual generated
  calculations and verifies that the independent fixtures detect them. It covers
  operand swaps, duplicate acceptance, missing contract checks, denominator states,
  percentile choice, fixed weights and confidence/composite gates. It is a defined
  fault set, not a claim that every possible defect is detectable.
- Contract identities now bind scope, input definitions, confidence requirements,
  thresholds, direction and decision/version-break rules. Regenerate prepared
  inputs after a contract hash changes; retain old versions for historical replay.
- Corrected four NIST CSF 2.0 associations: DET-012 and DET-014 remove nonexistent
  `RS.IM`, EXP-001 uses `PR.AA` instead of `PR.AC`, and RES-002 removes duplicated
  `RC.RP`. Each affected card advances to 0.9.2. Arithmetic remains unchanged.
  Category identifiers are checked against [NIST CSF 2.0, Appendix A, Table 1](https://nvlpubs.nist.gov/nistpubs/CSWP/NIST.CSWP.29.pdf).
  Identifier existence does not establish that a metric satisfies a requirement.
- `reference/source_to_decision.py` executes two synthetic examples: incident source
  selection to SOC-004, and control observations to STD-006. It retains reconciled
  populations, lineage, a mandatory confidence override and historical replay.
- `reference/preboard_sensitivity.py` checks explicit weight counterfactuals, zero
  risk ties and normalization boundaries. Illustrative anchors do not replace
  approved local risk appetite.

## Runtime scope and capacity

Kusto now has a pinned native functional CI job. It executes the same independent
fixtures as the other engines, including incident snapshots and invalid inputs.
It does not certify Sentinel/Defender ingestion or production performance. Use the
report for the exact source bundle; earlier green reports cannot verify later code.

`recipes/ci/desktop_runner.py` provides native verification entry points for installed
Microsoft Excel and a disposable local Analysis Services instance. These adapters
must themselves be exercised on those environments before their reports can support
compatibility. Local request-generation tests are not native execution evidence.

| Population / engine | Supported scope in this candidate |
|---|---|
| STD-002a / Python and DuckDB | Full 99,999, 100,000 and 100,001 draw populations executed; reporting eligibility starts at 100,000 |
| Prepared ES\|QL export | At most 10,000 records; count/schema/snapshot/warning checks; exact Python reduction |
| Prepared SPL | At most 10,000 records for this bounded exact profile |
| Generated spreadsheet template | At most 99,999 input rows; explicit capacity and overflow gate |
| Prepared KQL | Declared maximum 1,048,576 observations; array truncation and completeness gates; routine functional fixtures do not constitute a maximum-size benchmark |

STD-002a cannot meet its reporting minimum using the bounded SPL/ES export or the
current spreadsheet template. Use a complete Python/SQL population for that report;
do not divide draws into separately computed percentile batches. No tested upper
production capacity is asserted for Python/SQL beyond the recorded experiments.
`tools/preboard_capacity.py` records the nine specified boundary checks, including
rejection of a 10,001-row ES population exported as only 10,000 rows. Its ES response
checks are reducer tests, separately identified from native ES execution.

## Evidence that still requires real execution or participants

| Finding | Prepared here | Remaining acceptance evidence |
|---|---|---|
| F-03 / #4 | Independent percentile outputs, invalid cases and native Kusto runner | Microsoft Excel and DAX native reports for the exact candidate and declared outputs |
| F-06 / #7 | Every composite output has an oracle; gate/weight mutations | Microsoft Excel and DAX native composite/gate reports |
| F-23 / #24 | Synthetic sensitivity, capacity, population and replay tests | Actual pilot observations, stability, lagged outcomes and case-mix assessment |
| F-26 / #27 | Proposed charter and candidate-specific decision templates | Actual adoption, members, timetable and applicable review gates |
| F-27 / #28 | 1,149 triaged associations; 762 source-bound desk assessments and strict review binding | 387 remaining substantive assessments plus actual reviewer decisions; see [F-27 assessment](framework/F27_ASSESSMENT.md) |
| F-28 / #29 | Full export and `tools/verify_website_contract.py` | Externally handled deployment, retained artifacts, version match and actual browser behavior |
| F-32 / #33 | 327 dossiers and expertise/priority coverage plan | Actual independent reviewer assignments, conflict checks and recorded review coverage |

No issue is closed by the existence of this packet. Stable promotion requires the
formal process in `REVIEW_PROCESS.md`. Public status should state only findings,
impact, evidence, source versions and decisions needed by implementers.
