# Recipe execution contracts — remediation candidate

This is the OSMS 0.9.2 maintainer draft, developed from OSMS 0.9.1. Generation does not verify a
recipe. The numeric fixture count is a subset of the 327 cards; empty execution,
a parser check and a positive arithmetic example are different forms of evidence.

## Input and result contract

- Freeze the scope, period, source snapshot, card version, adapter version, weight
  and normalization profiles before evaluation. Preserve them with the result.
- Reporting periods use `[period_start, period_end)`. An as-of confirmation may
  occur at `period_end`. Normalize event timestamps to one timezone before running
  a recipe; never mix local naive timestamps from different timezones.
- Feed one canonical row per event/measure/component ID. Deduplication, source
  authenticity and completeness must be checked by the adapter and logged; a join
  must not silently multiply findings. The current snippets do not implement a
  universal ingestion validator.
- A proportion uses a numerator subset. General quotients, rates, efficiency and
  capacity ratios may exceed 1 or 100%. Their units, scale, aggregation and
  denominator validity come from the individual card. `calculation_type` alone
  does not establish these semantics.
- Distinguish measured zero, not applicable, missing input, invalid input,
  provisional result and mapping required. `None`/SQL `NULL` in a recipe is a
  numeric sentinel; an evaluation wrapper must retain the reason and input counts.
- Unknown confidence cannot establish Green. Operational Green requires confidence
  >=70; board Green requires >=85, plus valid inputs and the card's other gates.
  No numeric confidence production formula or statistical confidence interval is
  implied by these thresholds.
- Round for display only. Reconciliation compares raw values; counts are exact.
  Per-output precision and relative/absolute tolerances still need comprehensive
  versioned profiles for all cards.

## Corrections implemented here

**SOC-002:** select by `detected_at`, require confirmation by the as-of date and
exclude negative durations. P50 is the arithmetic median, including even n; P90
is the exact nearest rank. The supplementary weighted average uses P1/P2/other
weights 4/2/1, as already specified by the card. SQL, Python, KQL, SPL and Excel
snippets were updated. The DAX display implements P90 only and identifies sibling
outputs as outstanding. KQL rejects truncated percentile arrays. ES|QL is blocked:
`VALUES` deduplicates durations, so it cannot preserve the percentile population.
A real engine test of a multiset-safe replacement is still required.

**STD-016, card 0.9.2:** add nullable `mitigated_at` to the minimum input
contract. Count a finding once when either treatment date is on/before due and
`validation_status` is validated in the period-end snapshot. The validation must
substantiate that treatment; a ticket closure alone is insufficient. A reopened
finding whose treatment validation is no longer effective must have a nonvalidated
period-end status (for example `reopened`); retained historical validation must not
be passed as current validation. Such a row remains in the due-date cohort and
contributes zero to the numerator. Both dates
missing never counts, including in Excel and DAX. This is an adapter migration:
existing loaders must supply `mitigated_at`, with null when no mitigation exists.
The other 47 card fields remain intact; this is one additional input column,
not a new top-level card field.

**STD-068/069/075:** Python/SQL validate exactly the expected component IDs,
finite 0–100 scores and finite nonnegative weights summing to one. Excel checks
individual IDs and numeric cells. Candidate SPL/KQL/ES|QL guards were updated but
have positive-fixture execution evidence in the supplementary validation record;
comprehensive adversarial engine coverage remains open; ES|QL distinct cardinality is not an exact
identity proof. Weight/profile version binding remains an adapter requirement.

**STD-001:** require each penalty ID exactly once; reject negative, missing or
out-of-cap penalties and invalid leaf scores. The default 14 leaf weights remain
unchanged. Period binding, child normalization and version manifests are not yet
fully implemented by these snippets; do not infer board-grade DSPS assurance from
the positive example.

## Incomplete templates

The generator keeps incomplete logic under `templates`, for further implementation.
Its displayed `dialects` return a mapping-required sentinel or raise
`NotImplementedError`. They cannot return a plausible metric from `TRUE` hooks.
Duration templates with unresolved period/unit contracts are included here.
Their arithmetic examples are retained in `template-fixtures.json`, separately
from the numeric candidate fixtures; the lower candidate fixture count is explicit.

`coverage.json` states the current populations. `verification.status` starts at
`not_run` (or `candidate`) and is never promoted by generation. Engine claims must
refer to the exact recipe/catalog hashes and disclose output and negative-case
coverage. The website export now contains every original card field plus `mechanic`.
Deployment and website UI/schema migration are separate work; neither happened here.

## Reference engine scope

`reference/drill_engine.py` checks arithmetic and reference identity. Its
`card_contract_validated` is false: it does not validate all minimum-data fields,
full input provenance, source authenticity, statistical methods or risk models.
The synthetic 13-type demo illustrates mechanics; it is not the DSPS formula or a
327-card conformance suite. Ranking now reports `not_implemented` instead of
claiming that sorting its own output is independent verification.

STD-005 uses independently verified reduction and cost amounts in attributes.
Other Unit Cost adapters remain explicitly unimplemented. Historical lookup is
bound to the card version in the supplied catalog; supply that historical catalog
when inspecting older versions. The current view only returns current definitions.
The schema is a fresh-database reference; existing installations need a reviewed
migration for reporting context/validity columns and changed view status values.

## Primary technical sources

- [Kusto isfinite](https://learn.microsoft.com/en-us/kusto/query/isfinite-function):
  guards both infinity and NaN.
- [ES|QL aggregation reference](https://www.elastic.co/docs/reference/query-languages/esql/functions-operators/aggregation-functions):
  `VALUES` deduplicates; distinct-count estimates cannot establish exact cardinality.

## Additional execution profiles

[EXECUTION_PROFILES.md](EXECUTION_PROFILES.md) defines the separate canonical-input
layer, SOC-003 output semantics and its two-stage ES|QL protocol. Numeric profile
validity is distinct from source-adapter completion and Green eligibility.
[ASSURANCE_PROFILES.md](../reference/ASSURANCE_PROFILES.md) defines the numerical
confidence production, noncompensable gates, normalization, DSPS recomputation,
uncertainty, joint-risk and ranking primitives. Open ordinal rubrics are available
in [RUBRICS.md](../reference/RUBRICS.md). These are versioned maintainer-draft rules.
