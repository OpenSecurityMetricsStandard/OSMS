# Assurance calculation profiles

These profiles implement repository-defined mechanics for the maintainer draft.
They provide no external source authenticity, organizational risk-appetite values,
empirical pilot evidence or Board approval.

| Function in assurance.py | Inputs and mandatory evidence | Result |
|---|---|---|
| `confidence` | Exactly five check populations, integer passed/eligible counts, check-definition versions, scope/period and evidence, explicit mandatory-failure lists | Five numeric dimension scores, STD-011 weighted score and noncompensable Green eligibility gates |
| `normalize` | Card/output/unit/version, measured raw value, fixed good/bad or band anchors, version and evidence | Recomputed [0,100] posture plus raw value and profile hash |
| `weighted_components` | Exact component set and versions, frozen nonnegative weights, normalization hashes, period/scope and evidence | Independently rebuilt contributions and weighted score/average |
| `dsps` | All 14 raw child outputs, exact normalization profiles, weights, context and both version-bound penalties | Rebuilt STD-001 score, clipping after penalties, full contribution/profile evidence |
| `wilson_interval` | Unweighted independent probability sample, successes/trials, confidence level and selection note | Wilson score interval; other sampling designs return not_applicable |
| `portfolio_risk` | Complete joint annual-loss draws, unique IDs, explicit scenarios, generator/dependence/horizon/currency/control-credit profile | Portfolio mean, arithmetic P50, nearest-rank P90 and appetite exceedance probability |
| `rank_services` | Unique service/asset risk rows, explicit service population, versioned BIA/dependency multipliers and evidence | Recomputed raw priorities, maximum-scaled display scores and stable ranking |

## Confidence profile dq-checks/1

Each dimension is `100 * passed / eligible`. Freeze the eligible population and
check definitions before evaluation. Completeness checks required field/record
presence against the expected inventory; freshness checks reporting SLAs; source
authority checks the approved source register; consistency checks defined identity,
classification, unit and timestamp invariants; reconciliation checks raw-to-report
agreement. Different dimensions may have different check units, which their
versioned definitions identify. No population may be reduced to only passing rows.

Weights are STD-011's 0.25/0.25/0.20/0.15/0.15. Missing dimensions, zero eligible
basis, missing evidence or invalid counts cannot become default scores. The
mandatory-failure lists are derived from actual validity checks: unavailable source,
unknown/unapproved source or profile, unresolved duplicate identities, wrong
scope/period, invalid units/types, missing lineage or unreconciled source totals
are noncompensable for the affected evaluation. A high aggregate never overrides
those failures. Green eligibility requires no mandatory failure, a complete basis
and >=70 operational / >=85 management confidence. Other card gates still apply.

Confidence measures evidence/data quality. It is not a probability that the KPI is
correct and is not a statistical confidence interval. A Wilson interval requires
an appropriate sampling design; 1/1 and 1000/1000 have different lower bounds.
Convenience samples, correlated/weighted observations, censuses and unknown
selection mechanisms require their own methods; an interval does not repair bias.

## Risk and ranking scope

The risk reducer preserves supplied joint scenarios: it sums losses within a draw,
then calculates portfolio distribution outputs. It never adds marginal P90s or
silently assumes independence. The tests demonstrate identical marginal means with
different dependence producing different portfolio tails. Distribution fitting,
generation quality, scenario overlap and evidence supporting control credit remain
explicit model obligations. No generated sample is represented as a real pilot.

STD-003 ranking derives service priorities from independent asset risk inputs. It
preserves raw values, scales against the declared population maximum, orders by raw
priority descending and service ID ascending, and assigns equal values equal
competition ranks. Missing entities, duplicates, wrong contexts or unsupported
multipliers fail. A zero maximum is a known all-zero population, not missing input.

## Drilldown dimensions

`drill_engine.py::Card` parses both comma-separated and middle-dot-separated axes.
All 50 distinct declared axes have explicit SQLite query mappings. Additional axes
use the documented `AXIS_ATTRIBUTES` canonical JSON fields in evidence rows. Their
source adapters must populate those fields and retain lineage; missing dimensions
remain visible as NULL groups. Criticality is a separate canonical field from
incident severity. Group-by availability does not certify source completeness or
all card-level reconciliation. Unknown caller-supplied axes still fail.

The open ordinal reference vocabulary is in [RUBRICS.md](RUBRICS.md). The 12 cards
that referred to a separate guide now point there and advance their changed
card definitions where needed. Organization-specific anchors are explicitly
versioned inputs, never invented defaults or private dependencies.
